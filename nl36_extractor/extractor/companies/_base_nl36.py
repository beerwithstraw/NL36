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
# Period keyword → canonical period key
# ---------------------------------------------------------------------------
_PERIOD_KEYWORDS: List[Tuple[str, str]] = [
    # More specific patterns first (PY checks must come before CY to avoid
    # "for the corresponding quarter" matching "for the quarter")
    ("for the corresponding",           "py_qtr"),
    ("up to the corresponding",         "py_ytd"),
    ("upto the corresponding",          "py_ytd"),
    # CY patterns
    ("for the quarter",                 "cy_qtr"),
    ("upto the quarter",                "cy_ytd"),
    ("up to the quarter",               "cy_ytd"),
    ("for the period ended",            "cy_ytd"),   # YTD-only fallback
    ("upto the period",                 "cy_ytd"),
]

# Metric keyword → canonical metric key
_METRIC_KEYWORDS: List[Tuple[str, str]] = [
    ("no. of policies",  "policies"),
    ("no of policies",   "policies"),
    ("policies",         "policies"),
    ("premium",          "premium"),
]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def resolve_company_name(company_key: str, pdf_path: str, fallback: str) -> str:
    """Return display name from registry, else fallback."""
    return COMPANY_DISPLAY_NAMES.get(company_key, fallback)


def detect_period_columns(table) -> Dict[int, Tuple[str, str]]:
    """
    Scan the first 4 rows to identify the period header row (r1) and
    metric header row (r2), then return:
        {col_idx: (period_key, metric_key)}

    period_key ∈ {"cy_qtr", "cy_ytd", "py_qtr", "py_ytd"}
    metric_key ∈ {"policies", "premium"}

    Returns empty dict if detection fails.
    """
    period_row_idx = None
    metric_row_idx = None

    for ri in range(min(5, len(table))):
        row = table[ri]
        row_text = " ".join((c or "") for c in row).lower()
        if period_row_idx is None and any(kw in row_text for kw, _ in _PERIOD_KEYWORDS):
            period_row_idx = ri
        if metric_row_idx is None and any(kw in row_text for kw, _ in _METRIC_KEYWORDS):
            metric_row_idx = ri

    if period_row_idx is None or metric_row_idx is None:
        logger.warning("detect_period_columns: could not find period/metric header rows")
        return {}

    period_row = table[period_row_idx]
    metric_row = table[metric_row_idx]

    # Build col → period: span-fill (last non-None period applies forward)
    col_to_period: Dict[int, str] = {}
    current_period: Optional[str] = None
    for ci, cell in enumerate(period_row):
        if ci < 2:  # skip Sl.No and label columns
            continue
        if cell:
            norm = cell.lower().replace("\n", " ").strip()
            for kw, pk in _PERIOD_KEYWORDS:
                if kw in norm:
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
            norm = cell.lower().replace("\n", " ").replace("_", "").replace("-", "").strip()
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


def detect_channel_rows(table, label_col: int = 1) -> Dict[int, str]:
    """
    Scan table rows and return {row_idx: channel_key} for every row whose
    label (col `label_col`) matches a known CHANNEL_ALIASES entry.

    Rows 0-2 (headers) are always skipped.
    Blank label rows are skipped.
    """
    result: Dict[int, str] = {}
    for ri, row in enumerate(table):
        if ri < 3:
            continue
        if label_col >= len(row):
            continue
        label = (row[label_col] or "").strip()
        if not label:
            continue
        norm = normalise_text(label)
        channel_key = CHANNEL_ALIASES.get(norm)
        if channel_key:
            result[ri] = channel_key
        else:
            logger.debug(f"detect_channel_rows r{ri}: no alias for '{norm}'")
    return result


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
    label_col: int = 1,
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

                col_map = detect_period_columns(table)
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
