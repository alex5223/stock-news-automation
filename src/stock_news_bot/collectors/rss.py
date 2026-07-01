from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from typing import Any

import feedparser
from dateutil import parser as date_parser

from ..models import SourceItem

LOGGER = logging.getLogger(__name__)


TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def collect_rss(feeds: list[dict[str, Any]], since: datetime, until: datetime | None = None) -> list[SourceItem]:
    items: list[SourceItem] = []
    since_utc = since.astimezone(timezone.utc)
    until_utc = until.astimezone(timezone.utc) if until else None

    for feed in feeds:
        url = (feed.get("url") or "").strip()
        if not url:
            continue
        name = feed.get("name") or url
        parsed = feedparser.parse(url)
        if parsed.bozo:
            LOGGER.warning("RSS parse warning for %s: %s", name, parsed.bozo_exception)

        for entry in parsed.entries:
            published_at = _entry_datetime(entry)
            if published_at and published_at < since_utc:
                continue
            if until_utc and published_at and published_at > until_utc:
                continue

            title = _clean_text(entry.get("title", ""))
            link = entry.get("link", "")
            summary = _entry_text(entry)
            if not title and not summary:
                continue

            items.append(
                SourceItem(
                    source_type="rss",
                    source_name=name,
                    title=title,
                    url=link,
                    published_at=published_at,
                    text=summary,
                    external_id=entry.get("id", link),
                    author=entry.get("author", ""),
                    metadata={"category": feed.get("category", "")},
                )
            )
    return items


def _entry_datetime(entry: Any) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(attr)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc)

    for attr in ("published", "updated", "created"):
        value = entry.get(attr)
        if not value:
            continue
        try:
            parsed = date_parser.parse(value)
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _entry_text(entry: Any) -> str:
    chunks: list[str] = []
    if entry.get("summary"):
        chunks.append(entry.get("summary", ""))
    for content in entry.get("content", []) or []:
        value = content.get("value")
        if value:
            chunks.append(value)
    return _clean_text(" ".join(chunks))


def _clean_text(value: str) -> str:
    without_tags = TAG_RE.sub(" ", html.unescape(value or ""))
    return SPACE_RE.sub(" ", without_tags).strip()
