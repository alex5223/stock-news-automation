from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from dataclasses import asdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .analysis.dictionary import StockDictionary, count_industry_terms, summarize_entity_counts
from .analysis.llm import summarize_with_llm
from .analysis.signals import compute_signals
from .collectors.rss import collect_rss
from .collectors.youtube import collect_youtube
from .config import load_config
from .models import EntityMention, SourceItem
from .report import render_markdown
from .storage.local_store import LocalStore
from .storage.history import load_entity_history_from_snapshots, save_daily_snapshot
from .storage.sheets import export_to_sheets


@dataclass(frozen=True)
class PipelineResult:
    report_date: date
    item_count: int
    entity_count: int
    report_markdown: str
    report_path: Path | None
    snapshot_path: Path | None


def run_pipeline(config_path: Path, report_date: str | None = None, dry_run: bool = False) -> PipelineResult:
    config = load_config(config_path)
    timezone_name = config.get("run", {}).get("timezone", "Asia/Taipei")
    tz = ZoneInfo(timezone_name)
    now = datetime.now(tz)
    target_date = date.fromisoformat(report_date) if report_date else now.date()
    since, until = _window(config.get("run", {}), target_date, now, tz, explicit_date=bool(report_date))

    items = _collect_items(config, since, until)
    items = _dedupe_items(items)
    sorted_items = _sort_items(items)
    top_items = sorted_items[: int(config.get("run", {}).get("top_source_items", 20))]

    entity_rows = _analyze_entities(config.get("analysis", {}), sorted_items, target_date)
    local_config = config.get("storage", {}).get("local", {})
    local_store = LocalStore(local_config.get("data_dir", "data/runtime"))
    history_config = config.get("storage", {}).get("history", {})
    history_dir = history_config.get("history_dir", "data/history")
    history_rows = _merge_history_rows(
        local_store.load_entity_history(),
        load_entity_history_from_snapshots(history_dir),
    )

    analysis_config = config.get("analysis", {})
    signals = compute_signals(
        report_date=target_date,
        current_rows=entity_rows,
        history_rows=history_rows,
        lookback_days=int(config.get("run", {}).get("lookback_days", 5)),
        min_signal_count=int(analysis_config.get("min_signal_count", 2)),
        surge_ratio_threshold=float(analysis_config.get("surge_ratio_threshold", 2.0)),
    )

    llm_summary = summarize_with_llm(
        config=config.get("llm", {}),
        items=top_items,
        entity_rows=entity_rows,
        signals=signals,
    )
    report_markdown = render_markdown(
        report_date=target_date,
        since=since,
        until=until,
        items=sorted_items,
        entity_rows=entity_rows,
        signals=signals,
        llm_summary=llm_summary,
    )

    report_path: Path | None = None
    snapshot_path: Path | None = None
    if not dry_run:
        if local_config.get("enabled", True):
            local_store.save_sources(target_date, sorted_items)
            local_store.upsert_entity_rows(target_date, entity_rows)
            report_path = local_store.save_report(target_date, report_markdown)
        if history_config.get("enabled", True):
            snapshot_path = save_daily_snapshot(
                target_date,
                _snapshot_payload(
                    report_date=target_date,
                    generated_at=now,
                    timezone_name=timezone_name,
                    since=since,
                    until=until,
                    items=sorted_items,
                    entity_rows=entity_rows,
                    signals=signals,
                    llm_summary=llm_summary,
                    report_markdown=report_markdown,
                ),
                Path(history_dir),
            )
        export_to_sheets(
            config=config.get("storage", {}).get("sheets", {}),
            report_date=target_date,
            items=sorted_items,
            entity_rows=entity_rows,
            report_markdown=report_markdown,
        )

    return PipelineResult(
        report_date=target_date,
        item_count=len(sorted_items),
        entity_count=len(entity_rows),
        report_markdown=report_markdown,
        report_path=report_path,
        snapshot_path=snapshot_path,
    )


def _window(
    run_config: dict[str, Any],
    target_date: date,
    now: datetime,
    tz: ZoneInfo,
    *,
    explicit_date: bool,
) -> tuple[datetime, datetime]:
    if explicit_date or run_config.get("window", {}).get("mode") == "calendar_day":
        since = datetime.combine(target_date, time.min, tzinfo=tz)
        until = datetime.combine(target_date + timedelta(days=1), time.min, tzinfo=tz)
        if target_date == now.date():
            until = min(until, now)
        return since, until

    hours = int(run_config.get("window", {}).get("hours", 24))
    until = now
    since = until - timedelta(hours=hours)
    return since, until


def _collect_items(config: dict[str, Any], since: datetime, until: datetime) -> list[SourceItem]:
    items: list[SourceItem] = []
    rss_config = config.get("rss", {})
    if rss_config.get("enabled", False):
        items.extend(collect_rss(rss_config.get("feeds", []) or [], since, until))
    youtube_config = config.get("youtube", {})
    if youtube_config.get("enabled", False):
        items.extend(collect_youtube(youtube_config, since, until))
    return items


def _dedupe_items(items: list[SourceItem]) -> list[SourceItem]:
    seen: set[str] = set()
    deduped: list[SourceItem] = []
    for item in items:
        if item.fingerprint in seen:
            continue
        seen.add(item.fingerprint)
        deduped.append(item)
    return deduped


def _sort_items(items: list[SourceItem]) -> list[SourceItem]:
    return sorted(items, key=lambda item: item.published_at or datetime.min.replace(tzinfo=ZoneInfo("UTC")), reverse=True)


def _merge_history_rows(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    merged: list[dict[str, str]] = []
    for rows in groups:
        for row in rows:
            key = (row.get("date", ""), row.get("entity_type", ""), row.get("entity_id", ""))
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
    return merged


def _snapshot_payload(
    *,
    report_date: date,
    generated_at: datetime,
    timezone_name: str,
    since: datetime,
    until: datetime,
    items: list[SourceItem],
    entity_rows: list[dict[str, str]],
    signals: list[Any],
    llm_summary: str | None,
    report_markdown: str,
) -> dict[str, Any]:
    return {
        "date": report_date.isoformat(),
        "generated_at": generated_at.isoformat(),
        "window": {
            "since": since.isoformat(),
            "until": until.isoformat(),
            "timezone": timezone_name,
        },
        "counts": {
            "sources": len(items),
            "entities": len(entity_rows),
            "signals": len(signals),
        },
        "sources": [item.to_record() for item in items],
        "entities": entity_rows,
        "signals": [asdict(signal) for signal in signals],
        "llm_summary": llm_summary,
        "report_markdown": report_markdown,
    }


def _analyze_entities(analysis_config: dict[str, Any], items: list[SourceItem], report_date: date) -> list[dict[str, str]]:
    stock_dictionary = StockDictionary.from_csv(analysis_config.get("stock_alias_path", "data/tw_stocks_sample.csv"))
    industry_terms = analysis_config.get("industry_terms", {}) or {}

    stock_mentions_by_item: list[dict[str, EntityMention]] = []
    industry_mentions_by_item: list[dict[str, EntityMention]] = []
    stock_evidence: dict[str, set[str]] = {}
    industry_evidence: dict[str, set[str]] = {}

    for item in items:
        text = item.text_for_analysis()
        stock_mentions = stock_dictionary.match(text)
        industry_mentions = count_industry_terms(text, industry_terms)
        stock_mentions_by_item.append(stock_mentions)
        industry_mentions_by_item.append(industry_mentions)
        for entity_id, mention in stock_mentions.items():
            stock_evidence.setdefault(entity_id, set()).update(mention.evidence)
        for entity_id, mention in industry_mentions.items():
            industry_evidence.setdefault(entity_id, set()).update(mention.evidence)

    stock_counts, stock_source_counts = summarize_entity_counts(stock_mentions_by_item)
    industry_counts, industry_source_counts = summarize_entity_counts(industry_mentions_by_item)

    rows: list[dict[str, str]] = []
    rows.extend(
        _stock_rows(report_date, stock_dictionary, stock_counts, stock_source_counts, stock_evidence)
    )
    rows.extend(
        _industry_rows(report_date, industry_counts, industry_source_counts, industry_evidence)
    )
    return sorted(rows, key=lambda row: (row["entity_type"], int(row["count"])), reverse=True)


def _stock_rows(
    report_date: date,
    dictionary: StockDictionary,
    counts: Counter[str],
    source_counts: Counter[str],
    evidence: dict[str, set[str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for ticker, count in counts.most_common():
        entry = dictionary.get(ticker)
        if not entry:
            continue
        rows.append(
            {
                "date": report_date.isoformat(),
                "entity_type": "stock",
                "entity_id": ticker,
                "label": f"{entry.name}({ticker})",
                "industry": entry.industry,
                "count": str(count),
                "source_count": str(source_counts[ticker]),
                "evidence": "|".join(sorted(evidence.get(ticker, set()))),
            }
        )
    return rows


def _industry_rows(
    report_date: date,
    counts: Counter[str],
    source_counts: Counter[str],
    evidence: dict[str, set[str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for industry, count in counts.most_common():
        rows.append(
            {
                "date": report_date.isoformat(),
                "entity_type": "industry",
                "entity_id": industry,
                "label": industry,
                "industry": industry,
                "count": str(count),
                "source_count": str(source_counts[industry]),
                "evidence": "|".join(sorted(evidence.get(industry, set()))),
            }
        )
    return rows
