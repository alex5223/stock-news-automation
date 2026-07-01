from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


def save_daily_snapshot(date_value: str | date, data: dict[str, Any], history_dir: Path = Path("data/history")) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    date_text = date_value.isoformat() if isinstance(date_value, date) else date_value
    path = history_dir / f"{date_text}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def load_entity_history_from_snapshots(history_dir: str | Path = Path("data/history")) -> list[dict[str, str]]:
    path = Path(history_dir)
    if not path.exists():
        return []

    rows: list[dict[str, str]] = []
    for snapshot_path in sorted(path.glob("*.json")):
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        snapshot_date = str(payload.get("date") or snapshot_path.stem)
        for entity in payload.get("entities", []) or []:
            if not isinstance(entity, dict):
                continue
            row = {key: _stringify(value) for key, value in entity.items()}
            row.setdefault("date", snapshot_date)
            rows.append(row)
    return rows


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)
