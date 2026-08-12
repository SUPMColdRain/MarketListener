import pytest

from market_monitor.market_breadth import compute_daily_breadth


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


def test_daily_breadth_counts_advances_declines_and_unchanged():
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
    )
    first, second, third = snapshots
    assert first.advances == 0
    assert second.advances == 1
    assert second.declines == 1
    assert second.unchanged == 1
    assert third.advances == 2


def test_daily_breadth_returns_empty_for_no_data():
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
