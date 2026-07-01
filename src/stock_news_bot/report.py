from __future__ import annotations

from datetime import date, datetime

from .models import Signal, SourceItem


def render_markdown(
    *,
    report_date: date,
    since: datetime,
    until: datetime,
    items: list[SourceItem],
    entity_rows: list[dict[str, str]],
    signals: list[Signal],
    llm_summary: str | None,
) -> str:
    stock_rows = [row for row in entity_rows if row["entity_type"] == "stock"]
    industry_rows = [row for row in entity_rows if row["entity_type"] == "industry"]

    sections = [
        f"# 每日股票新聞觀察報告 - {report_date.isoformat()}",
        (
            f"資料視窗：{since.isoformat()} 至 {until.isoformat()}。"
            "本報告是研究輔助與觀察清單，不構成個人化投資建議。"
        ),
        "## 今日概況",
        f"- 收集來源數：{len(items)}",
        f"- 股票關鍵字：{len(stock_rows)}",
        f"- 產業關鍵字：{len(industry_rows)}",
        "## 重複出現的產業",
        _entity_table(industry_rows[:15]),
        "## 重複出現的個股",
        _entity_table(stock_rows[:20]),
        "## 聲量訊號",
        _signal_table(signals[:20]),
        "## 重要來源",
        _source_list(items[:20]),
    ]
    if llm_summary:
        sections.extend(["## LLM 研究摘要", llm_summary])
    sections.append("## 使用注意")
    sections.append(
        "- 頻率代表媒體與影片討論熱度，不等於基本面改善或股價方向。\n"
        "- YouTube 字幕可能缺漏、錯字或與口語內容不一致。\n"
        "- RSS 摘要可能只含部分內文，重要結論需回原文驗證。\n"
        "- 任何觀察都應搭配財報、法說、估值、籌碼與風險控管。"
    )
    return "\n\n".join(sections).strip() + "\n"


def _entity_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "_目前沒有達到門檻的項目。_"
    lines = ["| 名稱 | 次數 | 來源數 | 證據詞 |", "|---|---:|---:|---|"]
    for row in rows:
        lines.append(
            f"| {row.get('label', '')} | {row.get('count', 0)} | "
            f"{row.get('source_count', 0)} | {row.get('evidence', '')} |"
        )
    return "\n".join(lines)


def _signal_table(signals: list[Signal]) -> str:
    if not signals:
        return "_目前沒有明顯的連續上榜或聲量放大訊號。_"
    lines = [
        "| 類型 | 名稱 | 今日次數 | 來源數 | 近期待均 | 放大倍數 | 連續天數 | 原因 |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for signal in signals:
        lines.append(
            f"| {signal.entity_type} | {signal.label} | {signal.current_count} | "
            f"{signal.source_count} | {signal.average_previous:.2f} | {signal.surge_ratio:.2f} | "
            f"{signal.consecutive_days} | {signal.reason} |"
        )
    return "\n".join(lines)


def _source_list(items: list[SourceItem]) -> str:
    if not items:
        return "_尚未收集到來源。_"
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        published = item.published_at.isoformat() if item.published_at else "unknown time"
        transcript = "有字幕" if item.metadata.get("has_transcript") else "摘要/描述"
        lines.append(f"{index}. [{item.title}]({item.url}) - {item.source_name}, {published}, {transcript}")
    return "\n".join(lines)
