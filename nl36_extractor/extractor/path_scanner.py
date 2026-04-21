"""
path_scanner.py — Walks folder structure and returns ScanResult list.

Expected folder layout:
  <base_path>/
    FY2026/
      Q3/
        NL36/
          NL36_BajajGeneral.pdf
          ...
        Consolidated/
          BAJAJ_CONSOLIDATED.pdf
          ...
"""

import hashlib
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config.company_registry import COMPANY_MAP

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    pdf_path: str
    company_key: str
    company_raw: str
    quarter: str
    fiscal_year: str
    year_code: str
    source_type: str    # "direct" or "consolidated"
    file_hash: str


def _fy_to_year_code(fiscal_year: str) -> str:
    try:
        y = int(fiscal_year.replace("FY", ""))
        return f"20{str(y-1)[-2:]}{str(y)[-2:]}"
    except (ValueError, IndexError):
        logger.warning(f"Could not parse fiscal year: {fiscal_year}")
        return ""


def _extract_company_key(filename: str) -> Optional[tuple]:
    name = filename
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    parts = re.split(r"[_\-]", name)
    for length in range(1, len(parts) + 1):
        suffix_parts = parts[len(parts) - length:]
        candidate = "".join(suffix_parts).lower().replace(" ", "")
        company_raw = "_".join(suffix_parts)
        for key in sorted(COMPANY_MAP.keys(), key=len, reverse=True):
            norm_key = key.lower().replace("_", "").replace("-", "").replace(" ", "")
            if norm_key == candidate or norm_key in candidate:
                return (COMPANY_MAP[key], company_raw)
    logger.warning(f"Could not match company from filename: {filename}")
    return None


def _file_hash(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_quarters(quarters_config) -> List[str]:
    if quarters_config in ("all", ["all"]):
        return ["Q1", "Q2", "Q3", "Q4"]
    if isinstance(quarters_config, list):
        return [str(q).strip() for q in quarters_config]
    return ["Q1", "Q2", "Q3", "Q4"]


def scan(config: Dict[str, Any]) -> List[ScanResult]:
    """Walk the folder structure and return all NL-36 PDFs to process."""
    base_path = os.path.expanduser(config.get("base_path", "").strip())
    fiscal_years = config.get("fiscal_years", [])
    quarters = _resolve_quarters(config.get("quarters", "all"))

    if not base_path:
        raise ValueError("base_path is not set in extraction_config.yaml")
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"base_path does not exist: {base_path}")

    results: List[ScanResult] = []

    for fy in fiscal_years:
        fy_path = os.path.join(base_path, str(fy))
        if not os.path.isdir(fy_path):
            logger.warning(f"Fiscal year folder not found, skipping: {fy_path}")
            continue

        year_code = _fy_to_year_code(str(fy))

        for quarter in quarters:
            q_path = os.path.join(fy_path, quarter)
            if not os.path.isdir(q_path):
                continue

            direct_companies: set = set()

            # --- Scan NL36/ subfolder (direct PDFs) ---
            nl36_path = os.path.join(q_path, "NL36")
            if os.path.isdir(nl36_path):
                for fname in os.listdir(nl36_path):
                    if not fname.lower().endswith(".pdf"):
                        continue
                    result = _extract_company_key(fname)
                    if not result:
                        continue
                    company_key, company_raw = result
                    pdf_path = os.path.join(nl36_path, fname)
                    results.append(ScanResult(
                        pdf_path=os.path.abspath(pdf_path),
                        company_key=company_key,
                        company_raw=company_raw,
                        quarter=quarter,
                        fiscal_year=str(fy),
                        year_code=year_code,
                        source_type="direct",
                        file_hash=_file_hash(pdf_path),
                    ))
                    direct_companies.add(company_key)

            # --- Scan Consolidated/ subfolder ---
            consol_path = os.path.join(q_path, "Consolidated")
            if config.get("consolidated_mode", "dynamic") != "skip" and os.path.isdir(consol_path):
                for fname in os.listdir(consol_path):
                    if not fname.lower().endswith(".pdf"):
                        continue
                    result = _extract_company_key(fname)
                    if result is None:
                        continue
                    company_key, company_raw = result
                    if company_key in direct_companies:
                        continue
                    pdf_path = os.path.join(consol_path, fname)
                    results.append(ScanResult(
                        pdf_path=os.path.abspath(pdf_path),
                        company_key=company_key,
                        company_raw=company_raw,
                        quarter=quarter,
                        fiscal_year=str(fy),
                        year_code=year_code,
                        source_type="consolidated",
                        file_hash=_file_hash(pdf_path),
                    ))

    n_direct = sum(1 for r in results if r.source_type == "direct")
    n_consol = sum(1 for r in results if r.source_type == "consolidated")
    logger.info(f"Scan complete: {len(results)} PDFs found ({n_direct} direct, {n_consol} consolidated)")
    return results
