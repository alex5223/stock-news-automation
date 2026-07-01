from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from .pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect daily stock news and produce a signal report.")
    parser.add_argument("--config", default="config/sources.yaml", help="Path to the YAML config file.")
    parser.add_argument("--date", help="Report date in YYYY-MM-DD. Defaults to today in config timezone.")
    parser.add_argument("--dry-run", action="store_true", help="Collect and render without writing outputs.")
    parser.add_argument("--log-level", default="INFO", help="Python logging level.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(name)s - %(message)s",
    )
    load_dotenv()

    result = run_pipeline(Path(args.config), report_date=args.date, dry_run=args.dry_run)
    print(f"Report date: {result.report_date}")
    print(f"Collected items: {result.item_count}")
    print(f"Entity rows: {result.entity_count}")
    if result.report_path:
        print(f"Report written: {result.report_path}")
    if result.snapshot_path:
        print(f"Snapshot written: {result.snapshot_path}")
    if not result.report_path and not result.snapshot_path and result.report_markdown:
        print(result.report_markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
