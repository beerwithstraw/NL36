"""
Dedicated parser for ECGC Limited (NL-36).

ECGC's PDF uses a corrupt CIDFont mapping that causes pdfminer/pdfplumber
to crash with 'dict object has no attribute decode'.  PyMuPDF's find_tables()
can still extract the table structure.

Font corruption also replaces leading digits in many numeric cells with
control characters, so those values cannot be recovered reliably.  Cells
that survive control-char stripping as a valid number are kept; truncated
ones are set to None.

ECGC only writes Credit Insurance (government-backed export credit).
Most distribution channels carry zero or near-zero business, so missing
values are expected and suppressed via COMPLETENESS_IGNORE.
"""

import logging
import re
from pathlib import Path

from extractor.models import NL36ChannelRow, NL36Extract
from config.company_registry import COMPANY_DISPLAY_NAMES

logger = logging.getLogger(__name__)

# PyMuPDF table row index → channel_key.
# Derived from the fixed ECGC NL-36 layout (verified against Q3 FY2026 PDF).
_ROW_CHANNEL_MAP = {
    4:  "agent",
    5:  "corporate_agent_bank",
    6:  "corporate_agent_other",
    7:  "broker",
    8:  "micro_agent",
    9:  "direct_selling",
    10: "common_service_centre",
    11: "insurance_marketing_firm",
    12: "point_of_sales",
    13: "misp_direct",
    14: "web_aggregator",
    15: "referral_arrangements",
    16: "other_channels",
    18: "total_channel",
    19: "business_outside_india",
    20: "grand_total",
}

# Column index → (period_key, metric_key)
# r3 header: cols 2-3 = cy_qtr, 4-5 = cy_ytd, 6-7 = py_qtr, 8-9 = py_ytd
_COL_MAP = {
    2: ("cy_qtr", "policies"),
    3: ("cy_qtr", "premium"),
    4: ("cy_ytd", "policies"),
    5: ("cy_ytd", "premium"),
    6: ("py_qtr", "policies"),
    7: ("py_qtr", "premium"),
    8: ("py_ytd", "policies"),
    9: ("py_ytd", "premium"),
}

# Pattern: a valid standalone number (digits, commas, spaces, one dot)
_VALID_NUMBER = re.compile(r"^\d[\d,. ]*$")


def _safe_number(raw):
    """Strip control characters and return float if the result is a clean number."""
    if raw is None:
        return None
    cleaned = re.sub(r"[\x00-\x1f]", "", str(raw)).strip()
    if not cleaned or not _VALID_NUMBER.match(cleaned):
        return None
    try:
        return float(cleaned.replace(",", "").replace(" ", ""))
    except ValueError:
        return None


def parse_ecgc(
    pdf_path: str,
    company_key: str,
    quarter: str = "",
    year: str = "",
) -> NL36Extract:
    """
    PyMuPDF-based extractor for ECGC NL-36.
    Falls back to an empty extract with a warning if the table cannot be read.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) not installed — cannot parse ECGC PDF")
        return _empty_extract(pdf_path, company_key, quarter, year,
                              "PyMuPDF not installed")

    company_name = COMPANY_DISPLAY_NAMES.get(company_key, "ECGC Limited")
    extract = NL36Extract(
        source_file=Path(pdf_path).name,
        company_key=company_key,
        company_name=company_name,
        form_type="NL36",
        quarter=quarter,
        year=year,
    )

    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        tabs = page.find_tables()
        if not tabs.tables:
            extract.extraction_warnings.append("PyMuPDF found no tables in ECGC PDF")
            return extract

        table = tabs.tables[0].extract()
        logger.info(f"parse_ecgc: {len(table)} rows × {len(table[0])} cols extracted via PyMuPDF")

    except Exception as exc:
        logger.error(f"parse_ecgc: PyMuPDF failed — {exc}")
        extract.extraction_errors.append(f"PyMuPDF extraction failed: {exc}")
        return extract

    # Warn that some numbers may be None due to font corruption
    extract.extraction_warnings.append(
        "ECGC PDF has a corrupt CIDFont — leading digits in some numeric cells "
        "could not be recovered and are set to None."
    )

    for ri, channel_key in _ROW_CHANNEL_MAP.items():
        if ri >= len(table):
            continue
        row = table[ri]

        fields = {
            "cy_qtr_policies": None, "cy_qtr_premium": None,
            "cy_ytd_policies": None, "cy_ytd_premium": None,
            "py_qtr_policies": None, "py_qtr_premium": None,
            "py_ytd_policies": None, "py_ytd_premium": None,
        }

        for ci, (period, metric) in _COL_MAP.items():
            if ci >= len(row):
                continue
            val = _safe_number(row[ci])
            fields[f"{period}_{metric}"] = val

        extract.channels.append(NL36ChannelRow(channel_key=channel_key, **fields))
        logger.debug(f"  {channel_key}: {fields}")

    logger.info(f"parse_ecgc: extracted {len(extract.channels)} channel rows")
    return extract


def _empty_extract(pdf_path, company_key, quarter, year, reason) -> NL36Extract:
    return NL36Extract(
        source_file=Path(pdf_path).name,
        company_key=company_key,
        company_name=COMPANY_DISPLAY_NAMES.get(company_key, "ECGC Limited"),
        form_type="NL36",
        quarter=quarter,
        year=year,
        extraction_errors=[reason],
    )
