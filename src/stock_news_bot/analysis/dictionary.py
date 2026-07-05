from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..models import EntityMention


@dataclass(frozen=True)
class StockEntry:
    ticker: str
    name: str
    short_name: str
    aliases: tuple[str, ...]
    industry: str
    market: str

    @property
    def display_name(self) -> str:
        return self.short_name or self.name


class StockDictionary:
    def __init__(self, entries: Iterable[StockEntry]):
        self.entries = tuple(entries)
        self._entries_by_ticker = {entry.ticker: entry for entry in self.entries}
        self._alias_index = self._build_alias_index(self.entries)

    @classmethod
    def from_csv(cls, path: str | Path) -> "StockDictionary":
        entries: list[StockEntry] = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                ticker = (row.get("ticker") or "").strip()
                name = (row.get("name") or "").strip()
                short_name = (row.get("short_name") or "").strip()
                canonical_name = short_name or name
                if not ticker or not canonical_name:
                    continue
                aliases = _dedupe_aliases(
                    [ticker, name, short_name, *((row.get("aliases") or "").split("|"))]
                )
                entries.append(
                    StockEntry(
                        ticker=ticker,
                        name=name or canonical_name,
                        short_name=short_name,
                        aliases=tuple(aliases),
                        industry=(row.get("industry") or "").strip(),
                        market=(row.get("market") or "").strip(),
                    )
                )
        return cls(entries)

    def get(self, ticker: str) -> StockEntry | None:
        return self._entries_by_ticker.get(ticker)

    def match(self, text: str) -> dict[str, EntityMention]:
        text = text or ""
        spans_by_ticker: dict[str, list[tuple[int, int, str]]] = {}

        for alias, entry in self._alias_index:
            pattern = _alias_pattern(alias)
            for found in pattern.finditer(text):
                span = (found.start(), found.end())
                spans = spans_by_ticker.setdefault(entry.ticker, [])
                if _overlaps_existing(span, spans):
                    continue
                spans.append((span[0], span[1], alias))

        mentions: dict[str, EntityMention] = {}
        for ticker, spans in spans_by_ticker.items():
            entry = self._entries_by_ticker[ticker]
            evidence = tuple(sorted({alias for _, _, alias in spans}))
            mentions[ticker] = EntityMention(
                entity_type="stock",
                entity_id=ticker,
                label=f"{entry.display_name}({ticker})",
                count=len(spans),
                industry=entry.industry,
                evidence=evidence,
            )
        return mentions

    @staticmethod
    def _build_alias_index(entries: tuple[StockEntry, ...]) -> list[tuple[str, StockEntry]]:
        pairs: list[tuple[str, StockEntry]] = []
        for entry in entries:
            for alias in entry.aliases:
                pairs.append((alias, entry))
        return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def count_industry_terms(text: str, industry_terms: dict[str, list[str]]) -> dict[str, EntityMention]:
    mentions: dict[str, EntityMention] = {}
    for industry, terms in industry_terms.items():
        spans: list[tuple[int, int, str]] = []
        for term in sorted(set(terms), key=len, reverse=True):
            if not term:
                continue
            pattern = _alias_pattern(term)
            for found in pattern.finditer(text or ""):
                span = (found.start(), found.end())
                if _overlaps_existing(span, spans):
                    continue
                spans.append((span[0], span[1], term))
        if spans:
            evidence = tuple(sorted({term for _, _, term in spans}))
            mentions[industry] = EntityMention(
                entity_type="industry",
                entity_id=industry,
                label=industry,
                count=len(spans),
                evidence=evidence,
            )
    return mentions


def summarize_entity_counts(
    item_mentions: Iterable[dict[str, EntityMention]],
) -> tuple[Counter[str], Counter[str]]:
    counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for mentions in item_mentions:
        for entity_id, mention in mentions.items():
            counts[entity_id] += mention.count
            source_counts[entity_id] += 1
    return counts, source_counts


def _dedupe_aliases(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    aliases: list[str] = []
    for value in values:
        alias = (value or "").strip()
        if not alias or alias.casefold() in seen:
            continue
        seen.add(alias.casefold())
        aliases.append(alias)
    return aliases


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if alias.isdigit():
        return re.compile(rf"(?<!\d){escaped}(?!\d)", re.IGNORECASE)
    if alias.isascii() and re.match(r"^[A-Za-z0-9_.-]+$", alias):
        return re.compile(rf"(?<![A-Za-z0-9_.-]){escaped}(?![A-Za-z0-9_.-])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def _overlaps_existing(span: tuple[int, int], existing: list[tuple[int, int, str]]) -> bool:
    start, end = span
    for old_start, old_end, _ in existing:
        if max(start, old_start) < min(end, old_end):
            return True
    return False
