import pytest

from market_monitor.market_breadth import compute_daily_breadth, compute_limit_up_heights


def bar(day, code, open_price, close, amount=0.0):
    return {
        "instrument_key": {"country_or_market": "CN", "exchange": "SSE", "asset_type": "STOCK", "code": code},
        "instrument_id": code,
        "trading_day": day,
        "period": "1d",
        "bar_open_time": f"{day}T09:30:00+08:00",
        "bar_close_time": f"{day}T15:00:00+08:00",
        "open": open_price,
        "high": max(open_price, close),
        "low": min(open_price, close),
        "close": close,
        "volume": 1.0,
        "amount": amount,
        "open_interest": None,
    }


def test_daily_breadth_counts_advances_declines_unchanged_and_limits():
    day0 = [
        bar("2026-08-02", "600001", 90.0, 90.0),
        bar("2026-08-02", "600002", 105.0, 105.0),
        bar("2026-08-02", "600003", 100.0, 100.0),
    ]
    day1 = [
        bar("2026-08-03", "600001", 90.0, 100.0),   # +11.1% 涨停
        bar("2026-08-03", "600002", 105.0, 100.0),  # -4.8%
        bar("2026-08-03", "600003", 100.0, 100.0),  # 0%
    ]
    day2 = [
        bar("2026-08-04", "600001", 100.0, 110.0),  # +10% 连续涨停
        bar("2026-08-04", "600002", 100.0, 101.0),  # +1%
        bar("2026-08-04", "600003", 100.0, 99.0),   # -1%
    ]
    snapshots = compute_daily_breadth(
        {"2026-08-02": day0, "2026-08-03": day1, "2026-08-04": day2},
        limit_pct=0.10,
    )
    first, second, third = snapshots
    assert first.advances == 0
    assert second.advances == 1
    assert second.declines == 1
    assert second.unchanged == 1
    assert second.limit_ups == 1
    assert second.limit_downs == 0
    assert second.yesterday_limit_up_open_return is None
    assert third.limit_ups == 1
    assert third.limit_up_heights == {"600001": 2}
    # 昨日涨停的 600001 今日 open=100、close=110 → 接盘收益率 10%
    assert third.yesterday_limit_up_open_return == pytest.approx(0.10)


def test_limit_up_heights_uses_previous_close_and_matches_daily_breadth():
    days = {
        "2026-08-03": [bar("2026-08-03", "600001", 50.0, 50.0)],
        "2026-08-04": [bar("2026-08-04", "600001", 50.0, 55.0)],
        "2026-08-05": [bar("2026-08-05", "600001", 55.0, 60.5)],
        "2026-08-06": [bar("2026-08-06", "600001", 60.5, 60.5)],
    }
    heights = compute_limit_up_heights(days, limit_pct=0.10)
    last = compute_daily_breadth(days, limit_pct=0.10)[-1]
    assert heights == last.limit_up_heights == {}
    assert last.limit_ups == 0


def test_limit_up_heights_returns_empty_for_no_data():
    assert compute_limit_up_heights({}) == {}
    assert compute_daily_breadth({}) == []


def test_market_cap_and_amount_are_filtered_to_known_codes():
    day = [bar("2026-08-03", "600001", 100.0, 101.0, amount=3e8)]
    snapshots = compute_daily_breadth(
        {"2026-08-03": day},
        market_caps={"600001": 1e10, "600999": 5e9},
        amounts={"600001": 3e8, "600999": 9e8},
    )
    assert snapshots[0].total_market_cap == pytest.approx(1e10)
    assert snapshots[0].total_amount == pytest.approx(3e8)
    assert snapshots[0].northbound_flow is None


def test_breadth_rejects_invalid_limit_pct():
    with pytest.raises(ValueError, match="limit_pct"):
        compute_daily_breadth({}, limit_pct=0)
    with pytest.raises(ValueError, match="limit_pct"):
        compute_daily_breadth({}, limit_pct=0.6)
