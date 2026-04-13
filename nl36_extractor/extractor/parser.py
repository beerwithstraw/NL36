"""
NL-36 parser entry point.

Routes to dedicated parsers via DEDICATED_PARSER registry.
"""

import logging

from config.company_registry import DEDICATED_PARSER, COMPANY_DISPLAY_NAMES
from extractor.models import NL36Extract

logger = logging.getLogger(__name__)


def parse_pdf(
    pdf_path: str,
    company_key: str,
    quarter: str = "",
    year: str = "",
) -> NL36Extract:
    """Parse an NL-36 PDF and return an NL36Extract."""
    logger.info(f"Parsing PDF: {pdf_path} for company: {company_key}")

    dedicated_func_name = DEDICATED_PARSER.get(company_key)
    if dedicated_func_name:
        from extractor.companies import PARSER_REGISTRY
        dedicated_func = PARSER_REGISTRY.get(dedicated_func_name)
        if dedicated_func:
            logger.info(f"Routing to dedicated parser: {dedicated_func_name}")
            return dedicated_func(pdf_path, company_key, quarter, year)
        else:
            logger.error(f"Dedicated parser '{dedicated_func_name}' not in PARSER_REGISTRY")

    # No dedicated parser — fall back to the generic header-driven parser.
    logger.info(f"No dedicated parser for {company_key} — using generic header-driven fallback")
    from extractor.companies._base_nl36 import parse_header_driven_nl36
    fallback_name = COMPANY_DISPLAY_NAMES.get(company_key, str(company_key).title())
    return parse_header_driven_nl36(pdf_path, company_key, fallback_name, quarter=quarter, year=year)
