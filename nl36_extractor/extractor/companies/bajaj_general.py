"""
Parser for Bajaj Allianz General Insurance Company Limited (NL-36).

PDF Structure: 1 page, 1 table (23r × 10c).
  r0  — blank
  r1  — period span headers (4 periods)
  r2  — metric sub-headers (Policies | Premium per period)
  r3–r18 — 16 channel rows (col 0 = Sl.No, col 1 = label)
  r19 — blank
  r20 — Total (A)
  r21 — Business outside India (B)
  r22 — Grand Total (A+B)

CY/PY: detected from r1 period text.
  "For the Quarter"           → cy_qtr (cols 2-3)
  "Upto the Quarter"          → cy_ytd (cols 4-5)
  "For the corresponding..."  → py_qtr (cols 6-7)
  "Up to the corresponding…"  → py_ytd (cols 8-9)

Metrics per column pair: col even = Policies, col odd = Premium.
parse_header_driven_nl36() handles all of the above automatically.
"""

import logging

from extractor.companies._base_nl36 import parse_header_driven_nl36

logger = logging.getLogger(__name__)

_FALLBACK_NAME = "Bajaj Allianz General Insurance Company Limited"


def parse_bajaj_general(
    pdf_path: str,
    company_key: str,
    quarter: str = "",
    year: str = "",
):
    logger.info(f"Parsing Bajaj Allianz NL-36 PDF: {pdf_path}")
    return parse_header_driven_nl36(
        pdf_path,
        company_key,
        _FALLBACK_NAME,
        quarter=quarter,
        year=year,
    )
