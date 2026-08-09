from datetime import datetime, timezone

import pytest

from market_monitor.gold import SUPPORTED_INDICATORS, compute_gold_metrics, enrich_bars


def bar(day, close, high=None, low=None, open_price=None):
    return {
        "instrument_key": {"country_or_market": "CN", "exchange": "SSE", "asset_type": "STOCK", "code": "600519"},
        "instrument_id": "600519",
        "trading_day": day,
        "period": "1d",
        "bar_open_time": f"{day}T09:30:00+08:00",
        "bar_close_time": f"{day}T15:00:00+08:00",
        "open": open_price if open_price is not None else close - 1,
        "high": high if high is not None else close + 2,
        "low": low if low is not None else close - 1,
        "close": close,
        "volume": 1,
        "amount": 1,
        "open_interest": None,
    }


def test_enrich_bars_adds_pct_change_and_amplitude_without_mutating_input():
    rows = [
        bar("2026-08-03", 100.0),
        bar("2026-08-04", 110.0, high=115.0, low=95.0),
    ]
    output = enrich_bars(rows)
    assert output[0]["pct_change"] is None
    assert output[0]["amplitude"] is None
    assert output[1]["pct_change"] == pytest.approx(0.10)
    assert output[1]["amplitude"] == pytest.approx(0.20)
    assert "pct_change" not in rows[0]
    assert "amplitude" not in rows[1]


def test_gold_metrics_compute_sma_roc_rolling_max_min():
    rows = [bar(f"2026-08-{index + 1:02d}", 100.0 + index) for index in range(10)]
    metrics = compute_gold_metrics(
        rows,
        indicators=("sma", "roc", "rolling_max", "rolling_min"),
        window=5,
        now=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
    )
    by_key = {(metric.trading_date, metric.metric_name): metric.value for metric in metrics}
    assert by_key[("2026-08-10", "sma")] == pytest.approx(107.0)
    assert by_key[("2026-08-10", "roc")] == pytest.approx(5.0 / 104.0)
    assert by_key[("2026-08-10", "rolling_max")] == pytest.approx(109.0)
    assert by_key[("2026-08-10", "rolling_min")] == pytest.approx(105.0)
    # window=5：前 4 天指标不足被跳过，剩余 6 天 x 4 个指标
    assert len(metrics) == 6 * 4
    for metric in metrics:
        assert metric.definition
        assert metric.calculation_method.startswith("window=5")
        assert metric.metric_id.startswith("CN.SSE.STOCK.600519|")


def test_gold_metrics_ema_and_stddev_are_supported():
    rows = [bar(f"2026-08-{index + 1:02d}", 1.0 + index) for index in range(10)]
    metrics = compute_gold_metrics(rows, indicators=("ema", "stddev"), window=3)
    names = {metric.metric_name for metric in metrics}
    assert names == {"ema", "stddev"}
    assert SUPPORTED_INDICATORS == {"sma", "ema", "roc", "stddev", "rolling_max", "rolling_min"}


def test_gold_metrics_reject_bad_window_and_unknown_indicator():
    with pytest.raises(ValueError, match="window"):
        compute_gold_metrics([], window=0)
    with pytest.raises(ValueError, match="unsupported indicators"):
        compute_gold_metrics([bar("2026-08-03", 1.0)], indicators=("rsi",))
