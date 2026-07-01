import json

from stock_news_bot.storage.history import load_entity_history_from_snapshots, save_daily_snapshot


def test_save_and_load_entity_history_from_snapshots(tmp_path):
    save_daily_snapshot(
        "2026-06-26",
        {
            "date": "2026-06-26",
            "entities": [
                {
                    "date": "2026-06-26",
                    "entity_type": "stock",
                    "entity_id": "2330",
                    "label": "TSMC(2330)",
                    "count": 4,
                    "source_count": 2,
                }
            ],
        },
        tmp_path,
    )

    rows = load_entity_history_from_snapshots(tmp_path)

    assert rows == [
        {
            "date": "2026-06-26",
            "entity_type": "stock",
            "entity_id": "2330",
            "label": "TSMC(2330)",
            "count": "4",
            "source_count": "2",
        }
    ]
    assert json.loads((tmp_path / "2026-06-26.json").read_text(encoding="utf-8"))["date"] == "2026-06-26"
