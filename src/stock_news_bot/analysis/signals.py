from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from ..models import Signal


def compute_signals(
    *,
    report_date: date,
    current_rows: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
    lookback_days: int,
    min_signal_count: int,
    surge_ratio_threshold: float,
) -> list[Signal]:
    history_by_key_date: dict[tuple[str, str], dict[date, int]] = defaultdict(dict)
    start_date = report_date - timedelta(days=lookback_days)

    for row in history_rows:
        row_date = _parse_date(row.get("date", ""))
        if not row_date or row_date >= report_date or row_date < start_date:
            continue
        key = (row.get("entity_type", ""), row.get("entity_id", ""))
        history_by_key_date[key][row_date] = int(row.get("count") or 0)

    signals: list[Signal] = []
    for row in current_rows:
        current_count = int(row.get("count") or 0)
        if current_count < min_signal_count:
            continue
        key = (row.get("entity_type", ""), row.get("entity_id", ""))
        previous_counts = history_by_key_date.get(key, {})
        average_previous = sum(previous_counts.values()) / max(lookback_days, 1)
        surge_ratio = current_count / max(average_previous, 1.0)
        consecutive_days = _consecutive_days(report_date, previous_counts)
        reason = _reason(current_count, surge_ratio, consecutive_days, lookback_days, surge_ratio_threshold)

        signals.append(
            Signal(
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                label=row["label"],
                current_count=current_count,
                source_count=int(row.get("source_count") or 0),
                average_previous=round(average_previous, 2),
                surge_ratio=round(surge_ratio, 2),
                consecutive_days=consecutive_days,
                reason=reason,
            )
        )

    return sorted(
        signals,
        key=lambda item: (item.surge_ratio >= surge_ratio_threshold, item.consecutive_days, item.current_count),
        reverse=True,
    )


def _consecutive_days(report_date: date, previous_counts: dict[date, int]) -> int:
    days = 1
    cursor = report_date - timedelta(days=1)
    while previous_counts.get(cursor, 0) > 0:
        days += 1
        cursor -= timedelta(days=1)
    return days


def _reason(
    current_count: int,
    surge_ratio: float,
    consecutive_days: int,
    lookback_days: int,
    surge_ratio_threshold: float,
) -> str:
    reasons: list[str] = []
    if surge_ratio >= surge_ratio_threshold:
        reasons.append(f"聲量約為近{lookback_days}日均值的{surge_ratio:.1f}倍")
    if consecutive_days >= 2:
        reasons.append(f"連續{consecutive_days}日出現")
    if not reasons:
        reasons.append(f"今日提及{current_count}次")
    return "；".join(reasons)


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
