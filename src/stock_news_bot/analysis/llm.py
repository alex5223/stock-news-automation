from __future__ import annotations

import logging
import os
from typing import Any

from openai import OpenAI

from ..models import Signal, SourceItem

LOGGER = logging.getLogger(__name__)


def summarize_with_llm(
    *,
    config: dict[str, Any],
    items: list[SourceItem],
    entity_rows: list[dict[str, Any]],
    signals: list[Signal],
) -> str | None:
    if not config.get("enabled", False):
        return None
    if config.get("provider", "openai") != "openai":
        LOGGER.warning("Unsupported LLM provider: %s", config.get("provider"))
        return None

    api_key_env = config.get("api_key_env", "OPENAI_API_KEY")
    if not os.getenv(api_key_env):
        LOGGER.warning("LLM summary skipped because %s is missing.", api_key_env)
        return None

    model = os.getenv(config.get("model_env", "OPENAI_MODEL"), config.get("model", "gpt-5.5"))
    source_limit = int(config.get("max_source_items", 30))
    client = OpenAI()

    response = client.responses.create(
        model=model,
        reasoning={"effort": "low"},
        instructions=(
            "你是台灣股票研究助理。請根據使用者提供的新聞與影片文字做研究摘要。"
            "不要提供個人化買賣建議、目標價或保證式結論；請輸出可驗證的觀察、可能影響、風險和待追蹤事項。"
            "若資料不足，請明確說資料不足。請使用繁體中文。"
        ),
        input=_build_prompt(items[:source_limit], entity_rows, signals),
    )
    return response.output_text.strip()


def _build_prompt(items: list[SourceItem], entity_rows: list[dict[str, Any]], signals: list[Signal]) -> str:
    source_lines = []
    for index, item in enumerate(items, start=1):
        text = item.text_for_analysis().replace("\n", " ")
        source_lines.append(
            f"[{index}] {item.source_type}/{item.source_name} | {item.title} | {item.url}\n{text[:1200]}"
        )

    entity_lines = [
        f"- {row['entity_type']} {row['label']}: count={row['count']}, sources={row.get('source_count', 0)}"
        for row in entity_rows[:40]
    ]
    signal_lines = [
        (
            f"- {signal.entity_type} {signal.label}: count={signal.current_count}, "
            f"sources={signal.source_count}, surge={signal.surge_ratio}, "
            f"consecutive={signal.consecutive_days}, reason={signal.reason}"
        )
        for signal in signals[:20]
    ]

    return "\n\n".join(
        [
            "請產出以下段落：重要消息、重複出現的產業/個股、可能受惠與受壓方向、風險、明日追蹤清單。",
            "請盡量引用來源編號，例如 [1]。",
            "今日實體統計：\n" + "\n".join(entity_lines),
            "訊號候選：\n" + "\n".join(signal_lines),
            "來源摘要：\n" + "\n\n".join(source_lines),
        ]
    )
