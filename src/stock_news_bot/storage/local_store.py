from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from ..models import SourceItem


ENTITY_HEADERS = ["date", "entity_type", "entity_id", "label", "industry", "count", "source_count", "evidence"]


class LocalStore:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.sources_dir = self.data_dir / "sources"
        self.reports_dir = self.data_dir / "reports"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def save_sources(self, report_date: date, items: list[SourceItem]) -> Path:
        path = self.sources_dir / f"{report_date.isoformat()}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item.to_record(), ensure_ascii=False, default=str) + "\n")
        return path

    def upsert_entity_rows(self, report_date: date, rows: list[dict[str, Any]]) -> Path:
        path = self.data_dir / "daily_entities.csv"
        existing = []
        if path.exists():
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                existing = [row for row in reader if row.get("date") != report_date.isoformat()]

        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ENTITY_HEADERS)
            writer.writeheader()
            for row in existing:
                writer.writerow({header: row.get(header, "") for header in ENTITY_HEADERS})
            for row in rows:
                writer.writerow({header: row.get(header, "") for header in ENTITY_HEADERS})
        return path

    def load_entity_history(self) -> list[dict[str, str]]:
        path = self.data_dir / "daily_entities.csv"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def save_report(self, report_date: date, markdown: str) -> Path:
        path = self.reports_dir / f"{report_date.isoformat()}.md"
        path.write_text(markdown, encoding="utf-8")
        return path
