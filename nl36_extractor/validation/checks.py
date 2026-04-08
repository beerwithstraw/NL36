"""
Validation Checks for NL-36 Distribution of Business via Intermediaries.

Checks:
  1. GRAND_TOTAL_IDENTITY — Grand Total = Total (A) + Business outside India (B)
     For each of the 8 metric-period fields.
  2. COMPLETENESS — mandatory channels present with non-None data.
"""

import csv
import logging
from dataclasses import dataclass, asdict
from typing import List, Optional

from extractor.models import NL36Extract, NL36ChannelRow
from config.company_registry import COMPLETENESS_IGNORE

logger = logging.getLogger(__name__)

IDENTITY_TOLERANCE = 3.0

# Mandatory channels that must be present for the extract to be complete.
_MANDATORY_CHANNELS = {"total_channel", "grand_total"}

# The 8 field names on NL36ChannelRow.
_PERIOD_METRIC_FIELDS = [
    "cy_qtr_policies", "cy_qtr_premium",
    "cy_ytd_policies", "cy_ytd_premium",
    "py_qtr_policies", "py_qtr_premium",
    "py_ytd_policies", "py_ytd_premium",
]


@dataclass
class ValidationResult:
    company: str
    quarter: str
    year: str
    channel: str        # channel_key or "ALL"
    field: str          # e.g. "cy_ytd_premium"
    check_name: str
    status: str         # PASS, WARN, FAIL
    expected: Optional[float]
    actual: Optional[float]
    delta: Optional[float]
    note: str


def _by_key(channels: List[NL36ChannelRow], key: str) -> Optional[NL36ChannelRow]:
    for ch in channels:
        if ch.channel_key == key:
            return ch
    return None


def run_validations(extractions: List[NL36Extract]) -> List[ValidationResult]:
    results = []
    for ext in extractions:
        results.extend(_check_grand_total_identity(ext))
        results.extend(_check_completeness(ext))
    return results


def _check_grand_total_identity(ext: NL36Extract) -> List[ValidationResult]:
    """Grand Total = Total (A) + Business outside India (B), for each field."""
    results = []
    total_row = _by_key(ext.channels, "total_channel")
    boi_row   = _by_key(ext.channels, "business_outside_india")
    gt_row    = _by_key(ext.channels, "grand_total")

    if gt_row is None or total_row is None:
        return results

    for field in _PERIOD_METRIC_FIELDS:
        gt_val    = getattr(gt_row, field)
        total_val = getattr(total_row, field)
        boi_val   = getattr(boi_row, field) if boi_row else None

        if gt_val is None or total_val is None:
            continue

        expected = total_val + (boi_val or 0.0)
        delta = abs(gt_val - expected)
        status = "PASS" if delta <= IDENTITY_TOLERANCE else "FAIL"
        results.append(ValidationResult(
            company=ext.company_name,
            quarter=ext.quarter,
            year=ext.year,
            channel="grand_total",
            field=field,
            check_name="GRAND_TOTAL_IDENTITY",
            status=status,
            expected=expected,
            actual=gt_val,
            delta=delta,
            note="",
        ))

    return results


def _check_completeness(ext: NL36Extract) -> List[ValidationResult]:
    """Mandatory channels must have at least one non-None value."""
    results = []
    ignore = set(COMPLETENESS_IGNORE.get(ext.company_key, []))
    present_keys = {ch.channel_key for ch in ext.channels}

    for ch_key in _MANDATORY_CHANNELS:
        if ch_key in ignore:
            continue
        ch_row = _by_key(ext.channels, ch_key)
        has_data = ch_row is not None and any(
            getattr(ch_row, f) is not None for f in _PERIOD_METRIC_FIELDS
        )
        if not has_data:
            results.append(ValidationResult(
                company=ext.company_name,
                quarter=ext.quarter,
                year=ext.year,
                channel=ch_key,
                field="ALL",
                check_name="COMPLETENESS",
                status="FAIL",
                expected=None,
                actual=None,
                delta=None,
                note=f"Channel '{ch_key}' is missing or all-None",
            ))

    return results


def write_validation_report(results: List[ValidationResult], output_path: str):
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "company", "quarter", "year", "channel", "field",
            "check_name", "status", "expected", "actual", "delta", "note",
        ])
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))
    logger.info(f"Validation report saved to {output_path}")
