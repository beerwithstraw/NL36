"""
Base utilities for NL-36 Distribution of Business via Intermediaries parsers.

NL-36 table structure (Bajaj reference, 23r × 10c):
  r0  — blank / title row (skip)
  r1  — period span headers: "For the Quarter" | None | "Upto the Quarter" | …
  r2  — metric sub-headers: "No. of Policies" | "Premium (Rs.Lakhs)" | …
  r3… — channel data rows: col 0 = Sl.No (may be blank), col 1 = label
  rN  — blank separator (skip)
  rN+ — Total (A), Business outside India (B), Grand Total (A+B)

Column layout (fixed across all NL-36 companies):
  col 0: Sl.No
  col 1: Channel label
  col 2: CY Qtr  — Policies
  col 3: CY Qtr  — Premium
  col 4: CY YTD  — Policies
  col 5: CY YTD  — Premium
  col 6: PY Qtr  — Policies
  col 7: PY Qtr  — Premium
  col 8: PY YTD  — Policies
  col 9: PY YTD  — Premium
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

from extractor.models import NL36ChannelRow, NL36Extract
from extractor.normaliser import clean_number, normalise_text
from config.channel_registry import CHANNEL_ALIASES, CHANNEL_DISPLAY_NAMES
from config.company_registry import COMPANY_DISPLAY_NAMES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Period header patterns (regex-based, ordered most-specific first)
# ---------------------------------------------------------------------------
_PERIOD_LABEL_MAP: List[Tuple[re.Pattern, str]] = [
    # PY patterns — must come before generic CY patterns
    (re.compile(r"up\s+to\s+the\s+corresponding\s+quarter\s+of\s+the\s+previous\s+year", re.IGNORECASE), "py_ytd"),
    (re.compile(r"upto\s+the\s+corresponding\s+quarter\s+of\s+the\s+previous\s+year", re.IGNORECASE), "py_ytd"),
    (re.compile(r"for\s+the\s+corresponding\s+quarter\s+of\s+the\s+previous\s+year", re.IGNORECASE), "py_qtr"),
    (re.compile(r"for\s+the\s+corresponding", re.IGNORECASE), "py_qtr"),
    (re.compile(r"up\s+to\s+the\s+corresponding", re.IGNORECASE), "py_ytd"),
    (re.compile(r"upto\s+the\s+corresponding", re.IGNORECASE), "py_ytd"),
    # CY standard
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

# Metric keyword → canonical metric key
_METRIC_KEYWORDS: List[Tuple[str, str]] = [
    ("no. of policies",  "policies"),
    ("no of policies",   "policies"),
    ("policies",         "policies"),
    ("premium",          "premium"),
]

# ---------------------------------------------------------------------------
# Skip patterns — rows to ignore entirely during channel detection
# ---------------------------------------------------------------------------
_SKIP_PATTERNS = [
    re.compile(r"^\d+$"),
    re.compile(r"^sl\.?\s*no", re.IGNORECASE),
    re.compile(r"^s\.?\s*no", re.IGNORECASE),
    re.compile(r"^sr\.?\s*no", re.IGNORECASE),
    re.compile(r"^channels?$", re.IGNORECASE),
    re.compile(r"^intermediar", re.IGNORECASE),
    re.compile(r"^particulars$", re.IGNORECASE),
    re.compile(r"^form\s+nl[-\s]?36", re.IGNORECASE),
    re.compile(r"^nl-36", re.IGNORECASE),
    re.compile(r"^note", re.IGNORECASE),
    re.compile(r"^date\s+of\s+upload", re.IGNORECASE),
    re.compile(r"^report\s+version", re.IGNORECASE),
    re.compile(r"^business\s+acquisition\s+through", re.IGNORECASE),  # header row
    re.compile(r"(?:insurance|assurance)\s+company\s+limited", re.IGNORECASE),
    re.compile(r".*\*+\s*$", re.DOTALL),                              # footnote markers
    re.compile(r"^\(i\)\s*$", re.IGNORECASE),                         # lone footnote refs
    re.compile(r"^\(ii\)\s*\w*$", re.IGNORECASE),
]


def _fy_quarter_patterns(fy_year: str) -> List[Tuple[re.Pattern, str]]:
    """
    Build FY-year-aware period patterns for date-based headers.

    Accepts '2026' (4-digit FY end) or '202526' (6-digit pipeline year_code).

    Matches:
      'For the Quarter Ended Dec 31, 2025'  → cy_qtr
      'Upto the Quarter Ended Dec 31, 2025' → cy_ytd
      'For the Quarter Ended Dec 31, 2024'  → py_qtr
      'Upto the Quarter Ended Dec 31, 2024' → py_ytd
      'For Q3 2025-26'                      → cy_qtr  (Magma/Navi style)
      'Upto Q3 2025-26'                     → cy_ytd
      'Upto Q3 2024-25'                     → py_ytd
    """
    if not fy_year or not str(fy_year).isdigit():
        return []
    fy_year = str(fy_year)
    if len(fy_year) == 6:
        fy_start = int(fy_year[:4])
    elif len(fy_year) == 4:
        fy_start = int(fy_year) - 1
    else:
        return []
    py_start = fy_start - 1
    fy_suffix = str(fy_start)[-2:]
    py_suffix = str(py_start)[-2:]

    cy_yr = rf"(?:\b{fy_start}\b|-\s*{fy_suffix}(?!\d))"
    py_yr = rf"(?:\b{py_start}\b|-\s*{py_suffix}(?!\d))"

    return [
        # FY-quarter "For Q3 2025-26" / "Upto Q3 2025-26" style (Magma/Navi)
        (re.compile(rf"for\s+q\d[\s\S]*?{fy_start}-\d{{2}}", re.IGNORECASE), "cy_qtr"),
        (re.compile(rf"(?:upto|up\s+to)\s+q\d[\s\S]*?{fy_start}-\d{{2}}", re.IGNORECASE), "cy_ytd"),
        (re.compile(rf"for\s+q\d[\s\S]*?{py_start}-\d{{2}}", re.IGNORECASE), "py_qtr"),
        (re.compile(rf"(?:upto|up\s+to)\s+q\d[\s\S]*?{py_start}-\d{{2}}", re.IGNORECASE), "py_ytd"),
        # "For the period ended YYYY" = YTD (ZUNO style) — must come before quarter patterns
        (re.compile(rf"for\s+the\s+period\s+ended[\s\S]{{0,80}}{cy_yr}", re.IGNORECASE), "cy_ytd"),
        (re.compile(rf"for\s+the\s+period\s+ended[\s\S]{{0,80}}{py_yr}", re.IGNORECASE), "py_ytd"),
        # Date-based "For the Quarter Ended Dec 31, YYYY" (with "Ended")
        (re.compile(rf"for\s+the\s+quarter\s+ended[\s\S]{{0,80}}{cy_yr}", re.IGNORECASE), "cy_qtr"),
        (re.compile(rf"(?:upto|up\s+to)\s+the\s+quarter\s+ended[\s\S]{{0,80}}{cy_yr}", re.IGNORECASE), "cy_ytd"),
        (re.compile(rf"for\s+the\s+quarter\s+ended[\s\S]{{0,80}}{py_yr}", re.IGNORECASE), "py_qtr"),
        (re.compile(rf"(?:upto|up\s+to)\s+the\s+quarter\s+ended[\s\S]{{0,80}}{py_yr}", re.IGNORECASE), "py_ytd"),
        # Date-based without "Ended": "For the Quarter December 31, YYYY"
        (re.compile(rf"for\s+the\s+quarter[\s\S]{{0,80}}{cy_yr}", re.IGNORECASE), "cy_qtr"),
        (re.compile(rf"(?:upto|up\s+to)\s+the\s+quarter[\s\S]{{0,80}}{cy_yr}", re.IGNORECASE), "cy_ytd"),
        (re.compile(rf"for\s+the\s+quarter[\s\S]{{0,80}}{py_yr}", re.IGNORECASE), "py_qtr"),
        (re.compile(rf"(?:upto|up\s+to)\s+the\s+quarter[\s\S]{{0,80}}{py_yr}", re.IGNORECASE), "py_ytd"),
    ]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def resolve_company_name(company_key: str, pdf_path: str, fallback: str) -> str:
    """Return display name from registry, else fallback."""
    return COMPANY_DISPLAY_NAMES.get(company_key, fallback)


def detect_period_columns(table, fy_year: str = "") -> Dict[int, Tuple[str, str]]:
    """
    Scan the first 7 rows to identify the period header row and metric
    sub-header row, then return:
        {col_idx: (period_key, metric_key)}

    period_key ∈ {"cy_qtr", "cy_ytd", "py_qtr", "py_ytd"}
    metric_key ∈ {"policies", "premium"}

    fy_year: fiscal year string (e.g. '2026' or '202526').  When provided,
    date-based headers like 'For the Quarter Ended Dec 31, 2025' and
    FY-quarter headers like 'Upto Q3 2025-26' are correctly split CY vs PY.

    Returns empty dict if detection fails.
    """
    # FY-specific patterns prepended so they take priority over generic ones
    combined_label_map = _fy_quarter_patterns(fy_year) + _PERIOD_LABEL_MAP

    period_row_idx = None
    metric_row_idx = None

    for ri in range(min(7, len(table))):
        row = table[ri]
        row_text = " ".join((c or "") for c in row)
        if period_row_idx is None and any(p.search(row_text) for p, _ in combined_label_map):
            period_row_idx = ri
        if metric_row_idx is None and any(kw in row_text.lower() for kw, _ in _METRIC_KEYWORDS):
            metric_row_idx = ri

    if period_row_idx is None or metric_row_idx is None:
        logger.warning("detect_period_columns: could not find period/metric header rows")
        return {}

    period_row = table[period_row_idx]
    metric_row = table[metric_row_idx]

    # Build col → period: span-fill (last matched period applies forward to None cells)
    col_to_period: Dict[int, str] = {}
    current_period: Optional[str] = None
    for ci, cell in enumerate(period_row):
        if ci < 2:  # skip Sl.No and label columns
            continue
        if cell and str(cell).strip():
            cell_text = str(cell).strip()
            for pattern, pk in combined_label_map:
                if pattern.search(cell_text):
                    current_period = pk
                    break
        if current_period:
            col_to_period[ci] = current_period

    # Build col → metric
    col_to_metric: Dict[int, str] = {}
    for ci, cell in enumerate(metric_row):
        if ci < 2:
            continue
        if cell:
            norm = str(cell).lower().replace("\n", " ").replace("_", "").replace("-", "").strip()
            for kw, mk in _METRIC_KEYWORDS:
                if kw in norm:
                    col_to_metric[ci] = mk
                    break

    # Combine
    result: Dict[int, Tuple[str, str]] = {}
    for ci, period in col_to_period.items():
        if ci in col_to_metric:
            result[ci] = (period, col_to_metric[ci])

    if not result:
        logger.warning("detect_period_columns: no columns resolved")
    else:
        logger.debug(f"detect_period_columns: {result}")

    return result


def detect_channel_rows(table, label_col: int = -1) -> Dict[int, str]:
    """
    Scan table rows and return {row_idx: channel_key} for every row whose
    label matches a known CHANNEL_ALIASES entry.

    If label_col == -1 (default), auto-detects the best label column by
    trying columns 0-6 and picking whichever yields the most matches.

    Header rows, blank rows, and rows matching _SKIP_PATTERNS are ignored.
    """
    ncols = max(len(r) for r in table) if table else 0

    def _scan_col(col: int) -> Dict[int, str]:
        found: Dict[int, str] = {}
        seen: set = set()
        for ri, row in enumerate(table):
            if col >= len(row):
                continue
            raw = (row[col] or "").strip()
            if not raw:
                continue
            if any(p.match(raw) for p in _SKIP_PATTERNS):
                continue
            norm = normalise_text(raw)
            if not norm:
                continue
            channel_key = CHANNEL_ALIASES.get(norm)
            if channel_key and channel_key not in seen:
                found[ri] = channel_key
                seen.add(channel_key)
            elif not channel_key:
                logger.debug(f"detect_channel_rows col={col} r{ri}: no alias for '{norm}'")
        return found

    if label_col >= 0:
        return _scan_col(label_col)

    # Auto-detect: pick column with most matches
    best: Dict[int, str] = {}
    for col in range(min(7, ncols)):
        candidate = _scan_col(col)
        if len(candidate) > len(best):
            best = candidate
            logger.debug(f"detect_channel_rows: best col now {col} ({len(best)} matches)")
    return best


def extract_nl36_grid(
    table,
    channel_rows: Dict[int, str],
    col_map: Dict[int, Tuple[str, str]],
) -> List[NL36ChannelRow]:
    """
    For each (row_idx, channel_key) in channel_rows, read the 8 data
    columns specified by col_map and build an NL36ChannelRow.
    """
    rows: List[NL36ChannelRow] = []

    for row_idx, channel_key in channel_rows.items():
        if row_idx >= len(table):
            continue
        row = table[row_idx]

        fields = {
            "cy_qtr_policies": None, "cy_qtr_premium": None,
            "cy_ytd_policies": None, "cy_ytd_premium": None,
            "py_qtr_policies": None, "py_qtr_premium": None,
            "py_ytd_policies": None, "py_ytd_premium": None,
        }

        for ci, (period, metric) in col_map.items():
            if ci >= len(row):
                continue
            val = clean_number(row[ci])
            field_name = f"{period}_{metric}"
            fields[field_name] = val

        rows.append(NL36ChannelRow(channel_key=channel_key, **fields))
        logger.debug(f"  {channel_key}: {fields}")

    return rows


def parse_header_driven_nl36(
    pdf_path: str,
    company_key: str,
    fallback_name: str,
    quarter: str = "",
    year: str = "",
    label_col: int = -1,
) -> NL36Extract:
    """
    One-shot NL-36 extractor for standard-layout PDFs.

    Works when:
    - The NL-36 table is the only (or first) table on the NL-36 page(s).
    - Period headers are in r1, metric sub-headers in r2.
    - Channel labels are in col 1 (default).
    - All 4 periods are columns in a single table.
    """
    logger.info(f"parse_header_driven_nl36: {pdf_path}")
    company_name = resolve_company_name(company_key, pdf_path, fallback_name)

    extract = NL36Extract(
        source_file=Path(pdf_path).name,
        company_key=company_key,
        company_name=company_name,
        form_type="NL36",
        quarter=quarter,
        year=year,
    )

    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                logger.warning(f"P{pi}: no tables found")
                continue

            for ti, table in enumerate(tables):
                if not table or len(table) < 4:
                    continue

                col_map = detect_period_columns(table, fy_year=year)
                if not col_map:
                    logger.warning(f"P{pi} T{ti}: detect_period_columns failed")
                    continue

                channel_rows = detect_channel_rows(table, label_col=label_col)
                if not channel_rows:
                    logger.warning(f"P{pi} T{ti}: detect_channel_rows found nothing")
                    continue

                new_rows = extract_nl36_grid(table, channel_rows, col_map)
                extract.channels.extend(new_rows)
                logger.info(f"P{pi} T{ti}: extracted {len(new_rows)} channel rows")

    logger.info(
        f"Extraction complete: {len(extract.channels)} channel rows total"
    )
    return extract
