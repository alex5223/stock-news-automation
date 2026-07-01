from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests
from dateutil import parser as date_parser
from youtube_transcript_api import YouTubeTranscriptApi

from ..models import SourceItem

LOGGER = logging.getLogger(__name__)
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def collect_youtube(config: dict[str, Any], since: datetime, until: datetime | None = None) -> list[SourceItem]:
    if not config.get("enabled", False):
        return []

    api_key = os.getenv(config.get("api_key_env", "YOUTUBE_API_KEY"), "")
    if not api_key:
        LOGGER.warning("YouTube collection skipped because API key env var is missing.")
        return []

    max_results = int(config.get("max_results_per_query", 10))
    languages = list(config.get("transcript_languages", ["zh-Hant", "zh-TW", "zh", "en"]))
    items: list[SourceItem] = []
    seen_video_ids: set[str] = set()

    for query in config.get("queries", []) or []:
        items.extend(
            _search_videos(
                api_key=api_key,
                query=query,
                channel_id="",
                max_results=max_results,
                config=config,
                since=since,
                until=until,
                transcript_languages=languages,
                seen_video_ids=seen_video_ids,
            )
        )

    for channel in config.get("channels", []) or []:
        channel_id = (channel.get("id") or "").strip()
        if not channel_id:
            continue
        items.extend(
            _search_videos(
                api_key=api_key,
                query=channel.get("query", ""),
                channel_id=channel_id,
                max_results=max_results,
                config=config,
                since=since,
                until=until,
                transcript_languages=languages,
                seen_video_ids=seen_video_ids,
            )
        )

    return items


def _search_videos(
    *,
    api_key: str,
    query: str,
    channel_id: str,
    max_results: int,
    config: dict[str, Any],
    since: datetime,
    until: datetime | None,
    transcript_languages: list[str],
    seen_video_ids: set[str],
) -> list[SourceItem]:
    params: dict[str, Any] = {
        "key": api_key,
        "part": "snippet",
        "type": "video",
        "order": "date",
        "maxResults": min(max_results, 50),
        "publishedAfter": _rfc3339(since),
        "safeSearch": "none",
    }
    if until:
        params["publishedBefore"] = _rfc3339(until)
    if query:
        params["q"] = query
    if channel_id:
        params["channelId"] = channel_id
    if config.get("region_code"):
        params["regionCode"] = config["region_code"]
    if config.get("relevance_language"):
        params["relevanceLanguage"] = config["relevance_language"]

    response = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    results: list[SourceItem] = []
    for item in payload.get("items", []):
        video_id = ((item.get("id") or {}).get("videoId") or "").strip()
        if not video_id or video_id in seen_video_ids:
            continue
        seen_video_ids.add(video_id)

        snippet = item.get("snippet") or {}
        published_at = _parse_youtube_datetime(snippet.get("publishedAt"))
        transcript = _fetch_transcript(video_id, transcript_languages)
        description = snippet.get("description", "")
        text = transcript or description

        results.append(
            SourceItem(
                source_type="youtube",
                source_name=snippet.get("channelTitle", "YouTube"),
                title=snippet.get("title", ""),
                url=f"https://www.youtube.com/watch?v={video_id}",
                published_at=published_at,
                text=text,
                external_id=video_id,
                author=snippet.get("channelTitle", ""),
                metadata={"query": query, "channel_id": channel_id, "has_transcript": bool(transcript)},
            )
        )
    return results


def _fetch_transcript(video_id: str, languages: list[str]) -> str:
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=languages)
    except Exception as exc:  # The library raises multiple transcript-specific exceptions.
        LOGGER.info("Transcript unavailable for %s: %s", video_id, exc)
        return ""
    return " ".join(snippet.text for snippet in transcript if snippet.text)


def _parse_youtube_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = date_parser.isoparse(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _rfc3339(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
