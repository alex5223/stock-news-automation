from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Any, Literal


SourceType = Literal["rss", "youtube"]


@dataclass(frozen=True)
class SourceItem:
    source_type: SourceType
    source_name: str
    title: str
    url: str
    published_at: datetime | None
    text: str
    external_id: str = ""
    author: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        basis = "|".join([self.source_type, self.external_id, self.url, self.title])
        return sha256(basis.encode("utf-8")).hexdigest()[:24]

    def text_for_analysis(self) -> str:
        return " ".join(part for part in [self.title, self.author, self.text] if part).strip()

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.fingerprint,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else "",
            "author": self.author,
            "external_id": self.external_id,
            "text": self.text,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class EntityMention:
    entity_type: Literal["stock", "industry"]
    entity_id: str
    label: str
    count: int
    industry: str = ""
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class Signal:
    entity_type: Literal["stock", "industry"]
    entity_id: str
    label: str
    current_count: int
    source_count: int
    average_previous: float
    surge_ratio: float
    consecutive_days: int
    reason: str
