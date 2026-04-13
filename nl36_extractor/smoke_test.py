"""
smoke_test.py — NL-36 PDF batch smoke tester.

Scans every PDF in the configured NL36 folder, extracts all tables, and
reports:
  - Unrecognised channel row labels (candidates for alias expansion)
  - Unrecognised / missing period-column headers
  - Company keys not in COMPANY_MAP
  - Per-file channel coverage summary
  - Which period-metric columns were detected per file

Usage:
  cd nl36_extractor
  python3 smoke_test.py
"""

import os
import re
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pdfplumber
import yaml

from config.company_registry import COMPANY_MAP, COMPANY_DISPLAY_NAMES
from config.channel_registry import CHANNEL_ALIASES, CHANNEL_ORDER
from extractor.normaliser import normalise_text

logging.basicConfig(level=logging.WARNING, format="%(levelname)-5s | %(message)s")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "extraction_config.yaml")
with open(CONFIG_PATH) as f:
    cfg = yaml.safe_load(f)

BASE_PATH = os.path.expanduser(cfg["base_path"])
PDF_DIR = os.path.join(BASE_PATH, "FY2026", "Q3", "NL36")

# ---------------------------------------------------------------------------
# Period column header patterns (scan up to 7 rows, 7 cols)
# ---------------------------------------------------------------------------
_PERIOD_LABEL_MAP = [
    (re.compile(r"up\s+to\s+the\s+corresponding\s+quarter\s+of\s+the\s+previous\s+year", re.IGNORECASE), "py_ytd"),
    (re.compile(r"upto\s+the\s+corresponding\s+quarter\s+of\s+the\s+previous\s+year", re.IGNORECASE), "py_ytd"),
    (re.compile(r"for\s+the\s+corresponding\s+quarter\s+of\s+the\s+previous\s+year", re.IGNORECASE), "py_qtr"),
    (re.compile(r"for\s+the\s+corresponding", re.IGNORECASE), "py_qtr"),
    (re.compile(r"up\s+to\s+the\s+corresponding", re.IGNORECASE), "py_ytd"),
    (re.compile(r"upto\s+the\s+corresponding", re.IGNORECASE), "py_ytd"),
    (re.compile(r"upto\s+the\s+quarter|up\s+to\s+the\s+quarter", re.IGNORECASE), "cy_ytd"),
    (re.compile(r"for\s+the\s+quarter", re.IGNORECASE), "cy_qtr"),
    # N-month variants
    (re.compile(r"for\s+the\s+(?:9|nine)\s+months?\s+ended.{0,80}previous\s+year", re.IGNORECASE | re.DOTALL), "py_ytd"),
    (re.compile(r"for\s+the\s+(?:9|nine)\s+months?\s+ended", re.IGNORECASE), "cy_ytd"),
    (re.compile(r"for\s+the\s+(?:3|three)\s+months?\s+ended.{0,80}previous\s+year", re.IGNORECASE | re.DOTALL), "py_qtr"),
    (re.compile(r"for\s+the\s+(?:3|three)\s+months?\s+ended", re.IGNORECASE), "cy_qtr"),
    # Period ended / YTD fallback
    (re.compile(r"for\s+the\s+period\s+ended", re.IGNORECASE), "cy_ytd"),
    (re.compile(r"upto\s+the\s+period", re.IGNORECASE), "cy_ytd"),
]

_METRIC_KEYWORDS = [
    (re.compile(r"no\.?\s+of\s+polic", re.IGNORECASE), "policies"),
    (re.compile(r"premium", re.IGNORECASE), "premium"),
]

_SKIP_PATTERNS = [
    re.compile(r"^\d+$"),
    re.compile(r"^sl\.?\s*no", re.IGNORECASE),
    re.compile(r"^s\.?\s*no", re.IGNORECASE),
    re.compile(r"^sr\.?\s*no", re.IGNORECASE),
    re.compile(r"^channels?$", re.IGNORECASE),
    re.compile(r"^intermediar", re.IGNORECASE),
    re.compile(r"^particulars", re.IGNORECASE),
    re.compile(r"^form\s+nl[-\s]?36", re.IGNORECASE),
    re.compile(r"^nl-36", re.IGNORECASE),
    re.compile(r"^note", re.IGNORECASE),
    re.compile(r"^date\s+of\s+upload", re.IGNORECASE),
    re.compile(r"^report\s+version", re.IGNORECASE),
    re.compile(r"(?:insurance|assurance)\s+company\s+limited", re.IGNORECASE),
    re.compile(r".*\*+\s*$", re.DOTALL),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _match_company(filename: str):
    name = filename.lower()
    if name.endswith(".pdf"):
        name = name[:-4]
    name_nospace = re.sub(r'[^a-z0-9]', '', name)
    for key in sorted(COMPANY_MAP.keys(), key=len, reverse=True):
        key_norm = re.sub(r'[^a-z0-9]', '', key.lower())
        if key_norm in name_nospace or key.lower() in name:
            return COMPANY_MAP[key]
    return None


def _scan_period_headers(table, max_rows=7):
    """Return (period_hits, metric_hits, unrecognised_header_cells)."""
    period_hits = []
    metric_hits = []
    unrecognised = []

    for ri in range(min(max_rows, len(table))):
        row = table[ri]
        for cell in row:
            if cell is None:
                continue
            t = str(cell).strip()
            if not t:
                continue
            matched_period = any(p.search(t) for p, _ in _PERIOD_LABEL_MAP)
            matched_metric = any(p.search(t) for p, _ in _METRIC_KEYWORDS)
            if matched_period:
                period_hits.append(t.replace("\n", " "))
            elif matched_metric:
                metric_hits.append(t.replace("\n", " "))
            elif any(kw in t.lower() for kw in ["quarter", "period", "previous", "upto", "up to", "premium", "polic", "ytd"]):
                unrecognised.append(t.replace("\n", " "))

    return period_hits, metric_hits, unrecognised


def _detect_period_columns(table, max_rows=7):
    """Return set of period keys detected from header rows."""
    detected = set()
    for ri in range(min(max_rows, len(table))):
        row = table[ri]
        row_text = " ".join(str(c) for c in row if c)
        for pattern, pk in _PERIOD_LABEL_MAP:
            if pattern.search(row_text):
                detected.add(pk)
    return detected


def _scan_channel_rows(table, max_cols=7):
    """
    Try label columns 0..max_cols-1.
    Returns (recognised, unrecognised, best_col).
    """
    best_col = None
    best_recognised = {}
    best_unrecognised = []

    ncols = max(len(r) for r in table) if table else 0
    for label_col in range(min(max_cols, ncols)):
        recognised = {}
        unrecognised = []
        seen = set()

        for ri, row in enumerate(table):
            if len(row) <= label_col:
                continue
            cell = row[label_col]
            if cell is None:
                continue
            raw = str(cell).strip()
            if not raw:
                continue
            if any(p.match(raw) for p in _SKIP_PATTERNS):
                continue
            norm = normalise_text(raw)
            if not norm:
                continue

            channel_key = CHANNEL_ALIASES.get(norm)
            if channel_key:
                if channel_key not in seen:
                    recognised[ri] = (raw, channel_key)
                    seen.add(channel_key)
            else:
                unrecognised.append((ri, raw, norm))

        if len(recognised) > len(best_recognised):
            best_recognised = recognised
            best_unrecognised = unrecognised
            best_col = label_col

    return best_recognised, best_unrecognised, best_col


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    pdfs = sorted(f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf"))
    print(f"\n{'='*70}")
    print(f"NL-36 SMOKE TEST — {PDF_DIR}")
    print(f"PDFs found: {len(pdfs)}")
    print(f"{'='*70}\n")

    all_unrecognised_channels: dict[str, list[str]] = {}
    all_unrecognised_headers: dict[str, list[str]] = {}
    unmapped_companies: list[str] = []

    for fname in pdfs:
        pdf_path = os.path.join(PDF_DIR, fname)
        company_key = _match_company(fname)

        print(f"--- {fname}")
        print(f"    company_key : {company_key or '** UNKNOWN **'}")
        if not company_key:
            unmapped_companies.append(fname)

        try:
            with pdfplumber.open(pdf_path) as pdf:
                all_recognised = {}
                file_unrecognised_channels = []
                file_unrecognised_headers = []
                tables_found = 0
                best_label_col = None
                all_period_keys = set()

                for page in pdf.pages:
                    tables = page.extract_tables()
                    if not tables:
                        continue
                    for table in tables:
                        if not table or len(table) < 3:
                            continue
                        ncols = max(len(r) for r in table) if table else 0
                        if ncols < 4:
                            continue
                        tables_found += 1

                        # Period header scan
                        period_hits, metric_hits, unrecog_hdrs = _scan_period_headers(table, max_rows=7)
                        file_unrecognised_headers.extend(unrecog_hdrs)
                        all_period_keys |= _detect_period_columns(table, max_rows=7)

                        # Channel row scan
                        recognised, unrecognised, label_col = _scan_channel_rows(table, max_cols=7)
                        if recognised:
                            all_recognised.update(recognised)
                            if best_label_col is None:
                                best_label_col = label_col
                        file_unrecognised_channels.extend(unrecognised)

                # Deduplicate
                seen_norms = set()
                deduped_channels = []
                for ri, raw, norm in file_unrecognised_channels:
                    if norm not in seen_norms:
                        seen_norms.add(norm)
                        deduped_channels.append((raw, norm))

                seen_hdrs = set()
                deduped_hdrs = []
                for h in file_unrecognised_headers:
                    hn = normalise_text(h)
                    if hn and hn not in seen_hdrs:
                        seen_hdrs.add(hn)
                        deduped_hdrs.append(h)

                period_status = f"[{', '.join(sorted(all_period_keys))}]" if all_period_keys else "[NONE DETECTED]"
                print(f"    tables: {tables_found}  |  label_col: {best_label_col}  |  channels: {len(all_recognised)}  |  periods: {period_status}")

                if all_recognised:
                    ch_names = ", ".join(v[1] for v in all_recognised.values())
                    print(f"    channels: {ch_names}")

                if deduped_channels:
                    print(f"    UNRECOGNISED CHANNEL LABELS ({len(deduped_channels)}):")
                    for raw, norm in deduped_channels:
                        print(f"      raw='{raw}'  norm='{norm}'")
                        all_unrecognised_channels.setdefault(norm, []).append(fname)

                if deduped_hdrs:
                    print(f"    UNRECOGNISED COLUMN HEADERS ({len(deduped_hdrs)}):")
                    for h in deduped_hdrs:
                        print(f"      '{h}'")
                        hn = normalise_text(h)
                        all_unrecognised_headers.setdefault(hn, []).append(fname)

                missing_periods = {"cy_qtr", "cy_ytd", "py_qtr", "py_ytd"} - all_period_keys
                if missing_periods:
                    print(f"    MISSING PERIODS: {sorted(missing_periods)}")

        except Exception as e:
            print(f"    ERROR: {e}")

        print()

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print(f"\n{'='*70}")
    print("SUMMARY — UNMAPPED COMPANIES")
    print(f"{'='*70}")
    if unmapped_companies:
        for f in unmapped_companies:
            print(f"  {f}")
    else:
        print("  (none)")

    print(f"\n{'='*70}")
    print("SUMMARY — UNRECOGNISED CHANNEL LABELS (alias candidates)")
    print(f"{'='*70}")
    if all_unrecognised_channels:
        for norm, files in sorted(all_unrecognised_channels.items()):
            print(f"  '{norm}'  ←  {', '.join(set(files))}")
    else:
        print("  (none)")

    print(f"\n{'='*70}")
    print("SUMMARY — UNRECOGNISED COLUMN HEADERS")
    print(f"{'='*70}")
    if all_unrecognised_headers:
        for norm, files in sorted(all_unrecognised_headers.items()):
            print(f"  '{norm}'  ←  {', '.join(set(files))}")
    else:
        print("  (none)")


if __name__ == "__main__":
    main()
