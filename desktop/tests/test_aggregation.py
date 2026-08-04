from market_monitor.aggregation import aggregate_bars


def minute(open_time, close_time, trading_day="2026-08-03", close=100.0):
    return {"trading_day": trading_day, "bar_open_time": open_time, "bar_close_time": close_time, "period": "15m", "open": close - 1, "high": close + 1, "low": close - 2, "close": close, "volume": 10, "amount": 100, "open_interest": None}


def test_a_share_lunch_break_never_merges_into_a_single_hour_bar():
    rows = [minute("2026-08-03T11:15:00+08:00", "2026-08-03T11:30:00+08:00"), minute("2026-08-03T13:00:00+08:00", "2026-08-03T13:15:00+08:00", close=110)]
    result = aggregate_bars(rows, 60, "CN_STOCK")
    assert len(result) == 2
    assert result[0]["is_partial"] is False
    assert result[1]["is_partial"] is True
    assert result[0]["bar_close_time"] == "2026-08-03T11:30:00+08:00"


def test_tail_bar_is_marked_partial_and_ohlcv_is_aggregated():
    rows = [minute("2026-08-03T09:30:00+08:00", "2026-08-03T09:45:00+08:00", close=100), minute("2026-08-03T09:45:00+08:00", "2026-08-03T10:00:00+08:00", close=105)]
    result = aggregate_bars(rows, 60, "CN_STOCK")
    assert len(result) == 1
    assert result[0]["open"] == 99 and result[0]["close"] == 105
    assert result[0]["high"] == 106.0 and result[0]["low"] == 98.0
    assert result[0]["volume"] == 20.0 and result[0]["is_partial"]


def test_future_night_session_does_not_cross_trading_days():
    rows = [minute("2026-08-03T21:00:00+08:00", "2026-08-03T21:15:00+08:00", trading_day="2026-08-03"), minute("2026-08-04T09:00:00+08:00", "2026-08-04T09:15:00+08:00", trading_day="2026-08-04")]
    result = aggregate_bars(rows, 30, "CN_FUTURE")
    assert [item["trading_day"] for item in result] == ["2026-08-03", "2026-08-04"]
