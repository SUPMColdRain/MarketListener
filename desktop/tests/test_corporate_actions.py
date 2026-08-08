from datetime import date

import pytest

from market_monitor.contracts import ContractValidationError
from market_monitor.corporate_actions import (
    CorporateAction,
    apply_adjustment,
    build_adjustment_factors,
    factor_for_day,
    single_action_factor,
)


KEY = {"country_or_market": "CN", "exchange": "SSE", "asset_type": "STOCK", "code": "600519"}


def action(
    action_type: str,
    ex_date: date,
    *,
    cash: float = 0.0,
    bonus: float = 0.0,
    split: float = 1.0,
    rights_ratio: float = 0.0,
    rights_price: float = 0.0,
) -> CorporateAction:
    return CorporateAction(
        instrument_key=KEY,
        action_type=action_type,
        ex_date=ex_date,
        cash_per_share=cash,
        bonus_ratio=bonus,
        split_ratio=split,
        rights_ratio=rights_ratio,
        rights_price=rights_price,
    )


@pytest.mark.parametrize(
    ("previous_close", "cash", "bonus", "split", "expected"),
    [
        (10.0, 0.1, 0.0, 1.0, 0.99),  # cash dividend 10派1
        (10.0, 0.0, 0.0, 2.0, 0.5),  # 1 拆 2
        (10.0, 0.0, 1.0, 1.0, 0.5),  # 10 送 10
        (10.0, 0.5, 0.5, 1.0, 9.5 / 15.0),  # 派息 + 送股
        (10.0, 0.0, 0.0, 1.0, None),  # rights below
    ],
)
def test_single_action_factor_formulas(previous_close, cash, bonus, split, expected) -> None:
    if expected is None:
        factor = single_action_factor(
            previous_close=previous_close,
            rights_ratio=0.2,
            rights_price=5.0,
        )
        assert factor == pytest.approx((10.0 + 1.0) / (10.0 * 1.2))
        return
    factor = single_action_factor(
        previous_close=previous_close,
        cash_per_share=cash,
        bonus_ratio=bonus,
        split_ratio=split,
    )
    assert factor == pytest.approx(expected)


def test_adjusted_series_is_continuous_across_ex_date() -> None:
    ex_date = date(2026, 7, 15)
    actions = [action("CASH_DIVIDEND", ex_date, cash=0.5)]
    previous_close = {date(2026, 7, 14): 10.0}
    k = single_action_factor(previous_close=10.0, cash_per_share=0.5)

    bars = [
        {"trading_day": "2026-07-14", "bar_open_time": "2026-07-14T09:30:00+08:00", "bar_close_time": "2026-07-14T15:00:00+08:00", "open": 10.0, "high": 10.2, "low": 9.9, "close": 10.0, "volume": 1, "amount": 10, "open_interest": None, "period": "1d", "timezone": "Asia/Shanghai", "source_period": "1d", "source": {"provider": "x", "source_symbol": "y", "retrieved_at": "2026-08-05T00:00:00Z"}, "quality_status": "PASS", "schema_version": 1, "instrument_key": KEY, "price_mode": "RAW"},
        {"trading_day": "2026-07-15", "bar_open_time": "2026-07-15T09:30:00+08:00", "bar_close_time": "2026-07-15T15:00:00+08:00", "open": 10.0 * k, "high": 10.2 * k, "low": 9.9 * k, "close": 10.0 * k, "volume": 1, "amount": 10, "open_interest": None, "period": "1d", "timezone": "Asia/Shanghai", "source_period": "1d", "source": {"provider": "x", "source_symbol": "y", "retrieved_at": "2026-08-05T00:00:00Z"}, "quality_status": "PASS", "schema_version": 1, "instrument_key": KEY, "price_mode": "RAW"},
    ]

    for mode in ("FORWARD_ADJUSTED", "BACKWARD_ADJUSTED"):
        factors = build_adjustment_factors(actions, previous_close, mode=mode)
        adjusted = apply_adjustment(bars, factors, mode=mode)
        prev_close = next(bar["close"] for bar in adjusted if bar["trading_day"] == "2026-07-14")
        ex_open = next(bar["open"] for bar in adjusted if bar["trading_day"] == "2026-07-15")
        assert prev_close == pytest.approx(ex_open, rel=1e-12)


def test_multiple_actions_cumulate_in_both_modes() -> None:
    actions = [
        action("CASH_DIVIDEND", date(2026, 6, 1), cash=0.5),
        action("SPLIT", date(2026, 7, 1), split=2.0),
    ]
    previous_close = {date(2026, 5, 29): 20.0, date(2026, 6, 30): 10.0}
    backward = build_adjustment_factors(actions, previous_close, mode="BACKWARD_ADJUSTED")
    forward = build_adjustment_factors(actions, previous_close, mode="FORWARD_ADJUSTED")

    k1 = single_action_factor(previous_close=20.0, cash_per_share=0.5)
    k2 = single_action_factor(previous_close=10.0, split_ratio=2.0)
    assert factor_for_day(backward, date(2026, 5, 28)) == pytest.approx(1.0)
    assert factor_for_day(backward, date(2026, 6, 1)) == pytest.approx(1 / k1)
    assert factor_for_day(backward, date(2026, 7, 1)) == pytest.approx(1 / (k1 * k2))
    assert factor_for_day(forward, date(2026, 5, 28)) == pytest.approx(k1 * k2)
    assert factor_for_day(forward, date(2026, 6, 1)) == pytest.approx(k2)
    assert factor_for_day(forward, date(2026, 7, 1)) == pytest.approx(1.0)


def test_missing_previous_close_is_an_error_not_a_silent_skip() -> None:
    actions = [action("SPLIT", date(2026, 7, 1), split=2.0)]
    with pytest.raises(ValueError, match="missing previous close"):
        build_adjustment_factors(actions, {}, mode="BACKWARD_ADJUSTED")


def test_contract_validation_rejects_inconsistent_action_fields() -> None:
    with pytest.raises(ContractValidationError):
        CorporateAction.from_mapping(
            {
                "schema_version": 1,
                "instrument_key": KEY,
                "action_type": "SPLIT",
                "ex_date": "2026-07-15",
                "source": {"provider": "x", "source_symbol": "y", "retrieved_at": "2026-08-05T00:00:00Z"},
            }
        )
