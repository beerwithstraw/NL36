"""
Excel Writer for NL-36 Distribution of Business via Intermediaries.

Output: one row per (company, quarter, year, channel) with 8 data columns.
"""

import logging
from pathlib import Path
from typing import List, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from config.settings import MASTER_COLUMNS, NUMBER_FORMAT
from config.channel_registry import CHANNEL_DISPLAY_NAMES, CHANNEL_ORDER
from extractor.models import NL36Extract

logger = logging.getLogger(__name__)

_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
_CENTER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)

# Data columns (H onward) — match MASTER_COLUMNS order
_DATA_FIELDS = [
    "cy_qtr_policies", "cy_qtr_premium",
    "cy_ytd_policies", "cy_ytd_premium",
    "py_qtr_policies", "py_qtr_premium",
    "py_ytd_policies", "py_ytd_premium",
]


def save_workbook(
    extractions: List[NL36Extract],
    output_path: str,
    stats: Optional[dict] = None,
) -> None:
    """Write all extractions to the master Excel workbook."""
    # Load existing or create new
    try:
        wb = load_workbook(output_path)
    except (FileNotFoundError, Exception):
        wb = Workbook()
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

    # Ensure Master_Data sheet
    if "Master_Data" in wb.sheetnames:
        ws = wb["Master_Data"]
    else:
        ws = wb.create_sheet("Master_Data", 0)

    # Write header row
    for ci, col_name in enumerate(MASTER_COLUMNS, 1):
        cell = ws.cell(row=1, column=ci, value=col_name)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _CENTER_ALIGN

    ws.freeze_panes = "A2"

    # Determine next empty row (after any existing data)
    next_row = ws.max_row + 1 if ws.max_row > 1 else 2

    for ext in extractions:
        # Build channel lookup by key
        channel_map = {ch.channel_key: ch for ch in ext.channels}

        # Write rows in canonical CHANNEL_ORDER
        for ch_key in CHANNEL_ORDER:
            ch = channel_map.get(ch_key)
            if ch is None:
                continue  # channel not present in this PDF

            row_data = [
                ext.company_name,
                ext.company_key,
                ext.quarter,
                ext.year,
                ext.source_file,
                ch.channel_key,
                CHANNEL_DISPLAY_NAMES.get(ch.channel_key, ch.channel_key),
            ]
            for field in _DATA_FIELDS:
                row_data.append(getattr(ch, field))

            for ci, val in enumerate(row_data, 1):
                cell = ws.cell(row=next_row, column=ci, value=val)
                # Apply number format to data columns (H+)
                if ci >= 8 and val is not None:
                    cell.number_format = NUMBER_FORMAT

            next_row += 1

    # Auto-fit column widths (approximate)
    for col_cells in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col_cells), default=0)
        ws.column_dimensions[get_column_letter(col_cells[0].column)].width = min(max_len + 2, 40)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    logger.info(f"Workbook saved: {output_path}")


def write_validation_summary_sheet(report_path: str, workbook_path: str) -> None:
    """Append a Validation_Summary sheet to the workbook."""
    import csv
    from collections import Counter

    if not Path(report_path).exists():
        return

    counts: Counter = Counter()
    with open(report_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            counts[row.get("status", "UNKNOWN")] += 1

    wb = load_workbook(workbook_path)
    if "Validation_Summary" in wb.sheetnames:
        del wb["Validation_Summary"]
    ws = wb.create_sheet("Validation_Summary")

    ws.append(["Status", "Count"])
    for status in ["PASS", "WARN", "FAIL"]:
        ws.append([status, counts.get(status, 0)])

    wb.save(workbook_path)


def write_validation_detail_sheet(report_path: str, workbook_path: str) -> None:
    """Append a Validation_Detail sheet (FAILs and WARNs) to the workbook."""
    import csv

    if not Path(report_path).exists():
        return

    wb = load_workbook(workbook_path)
    if "Validation_Detail" in wb.sheetnames:
        del wb["Validation_Detail"]
    ws = wb.create_sheet("Validation_Detail")

    with open(report_path, newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        ws.append(headers)
        for row in reader:
            if row.get("status") in ("FAIL", "WARN"):
                ws.append([row.get(h, "") for h in headers])

    wb.save(workbook_path)
