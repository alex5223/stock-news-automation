from datetime import date

from stock_news_bot.analysis.signals import compute_signals


def test_compute_signals_detects_surge_and_consecutive_days():
    current_rows = [
        {
            "date": "2026-06-23",
            "entity_type": "stock",
            "entity_id": "2330",
            "label": "台積電(2330)",
            "count": "6",
            "source_count": "3",
        }
    ]
    history_rows = [
        {"date": "2026-06-22", "entity_type": "stock", "entity_id": "2330", "label": "台積電(2330)", "count": "2"},
        {"date": "2026-06-21", "entity_type": "stock", "entity_id": "2330", "label": "台積電(2330)", "count": "1"},
    ]

    signals = compute_signals(
        report_date=date(2026, 6, 23),
        current_rows=current_rows,
        history_rows=history_rows,
        lookback_days=5,
        min_signal_count=2,
        surge_ratio_threshold=2.0,
    )

    assert signals[0].entity_id == "2330"
    assert signals[0].consecutive_days == 3
    assert signals[0].surge_ratio == 6.0
