from __future__ import annotations

import os
from datetime import date
from typing import Any

import gspread
from gspread.exceptions import WorksheetNotFound

from ..models import SourceItem
from .local_store import ENTITY_HEADERS


def export_to_sheets(
    *,
    config: dict[str, Any],
    report_date: date,
    items: list[SourceItem],
    entity_rows: list[dict[str, Any]],
    report_markdown: str,
) -> None:
    if not config.get("enabled", False):
        return

    spreadsheet_id = os.getenv(config.get("spreadsheet_id_env", "GOOGLE_SHEET_ID"), "")
    if not spreadsheet_id:
        raise RuntimeError("Google Sheets export is enabled, but spreadsheet ID env var is missing.")

    service_account_env = config.get("service_account_file_env", "GOOGLE_APPLICATION_CREDENTIALS")
    service_account_file = os.getenv(service_account_env, "")
    client = gspread.service_account(filename=service_account_file) if service_account_file else gspread.service_account()
    spreadsheet = client.open_by_key(spreadsheet_id)

    source_headers = ["date", "id", "source_type", "source_name", "title", "url", "published_at", "author"]
    source_rows = [
        [
            report_date.isoformat(),
            item.fingerprint,
            item.source_type,
            item.source_name,
            item.title,
            item.url,
            item.published_at.isoformat() if item.published_at else "",
            item.author,
        ]
        for item in items
    ]
    _append_rows(spreadsheet, "Sources", source_headers, source_rows)

    entity_values = [[row.get(header, "") for header in ENTITY_HEADERS] for row in entity_rows]
    _append_rows(spreadsheet, "Entities", ENTITY_HEADERS, entity_values)

    report_headers = ["date", "markdown"]
    _append_rows(spreadsheet, "Reports", report_headers, [[report_date.isoformat(), report_markdown]])


def _append_rows(spreadsheet: Any, title: str, headers: list[str], rows: list[list[Any]]) -> None:
    worksheet = _worksheet(spreadsheet, title, headers)
    if rows:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def _worksheet(spreadsheet: Any, title: str, headers: list[str]) -> Any:
    try:
        worksheet = spreadsheet.worksheet(title)
    except WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=title, rows=1000, cols=max(len(headers), 1))
        worksheet.append_row(headers)
        return worksheet

    existing_header = worksheet.row_values(1)
    if not existing_header:
        worksheet.append_row(headers)
    return worksheet
