"""
pipeline.py — NL-36 Distribution of Business via Intermediaries extraction pipeline.

Usage:
  python3 pipeline.py                           # incremental (default)
  python3 pipeline.py --force                   # re-extract everything
  python3 pipeline.py --force-company bajaj_allianz
  python3 pipeline.py --quarter Q3              # override config quarters
  python3 pipeline.py --dry-run
"""

import argparse
import logging
import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractor.path_scanner import scan
from extractor.processed_log import load as load_log, save as save_log
from extractor.processed_log import filter_unprocessed, mark_processed
from extractor.parser import parse_pdf
from validation.checks import run_validations, write_validation_report
from output.excel_writer import (
    save_workbook,
    write_validation_summary_sheet,
    write_validation_detail_sheet,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extraction_config.yaml")


def load_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_config(config: dict) -> None:
    for key in ("base_path", "master_sheet_path", "processed_log_path"):
        if not config.get(key, "").strip():
            raise ValueError(f"'{key}' is not set in extraction_config.yaml")


def main():
    parser = argparse.ArgumentParser(description="NL-36 Extraction Pipeline")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--force-company", nargs="+", default=None)
    parser.add_argument("--quarter", nargs="+", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config", type=str, default=CONFIG_PATH)
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        validate_config(config)
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    if args.quarter:
        config["quarters"] = args.quarter

    logger.info("Scanning folder structure...")
    try:
        scan_results = scan(config)
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    if not scan_results:
        logger.info("No NL-36 PDFs found. Check base_path and fiscal_years.")
        sys.exit(0)

    log_path = config["processed_log_path"]
    log_data = load_log(log_path)
    to_process = filter_unprocessed(
        scan_results, log_data,
        force=args.force,
        force_company=args.force_company,
    )

    if not to_process:
        logger.info("All files up-to-date. Use --force to re-extract.")
        sys.exit(0)

    if args.dry_run:
        logger.info(f"DRY RUN — would extract {len(to_process)} files:")
        for r in to_process:
            logger.info(f"  {r.company_key}  {r.fiscal_year} {r.quarter}  {r.pdf_path}")
        sys.exit(0)

    master_path = config["master_sheet_path"]
    succeeded = 0
    failed = 0
    failed_files = []
    all_extractions = []
    all_validation_results = []

    for result in to_process:
        logger.info(f"Extracting {result.company_key} {result.fiscal_year} {result.quarter}")
        try:
            extract = parse_pdf(
                result.pdf_path,
                result.company_key,
                result.quarter,
                result.year_code,
            )

            # No-op for NL36 (satisfies pipeline contract)
            extract.align_periods()

            validation_results = run_validations([extract])

            all_extractions.append(extract)
            all_validation_results.extend(validation_results)

            mark_processed(log_data, result, len(extract.channels))
            save_log(log_path, log_data)

            succeeded += 1
            logger.info(f"  Done: {result.company_key} — {len(extract.channels)} channels")

        except Exception as e:
            logger.error(f"  Failed: {result.company_key} — {e}", exc_info=True)
            failed += 1
            failed_files.append((result.pdf_path, str(e)))

    if all_extractions:
        logger.info(f"Writing master workbook to {master_path}")
        save_workbook(all_extractions, master_path)

        report_path = os.path.join(os.path.dirname(master_path), "validation_report.csv")
        write_validation_report(all_validation_results, report_path)
        write_validation_summary_sheet(report_path, master_path)
        write_validation_detail_sheet(report_path, master_path)
        logger.info(f"Validation report: {report_path}")

    logger.info("=" * 60)
    logger.info(f"Pipeline complete. Succeeded: {succeeded}, Failed: {failed}")
    if failed_files:
        for path, reason in failed_files:
            logger.info(f"  FAILED: {path} — {reason}")


if __name__ == "__main__":
    main()
