"""Baostock mapping tests use fixed SDK responses only."""

from __future__ import annotations

from datetime import date

from market_monitor.providers import CapabilityStatus
from market_monitor.providers.baostock import BaostockProvider


class FakeResult:
    def __init__(self, fields: list[str], rows: list[list[str]], error_code: str = "0") -> None:
        self.fields = fields
        self._rows = rows
        self._position = -1
        self.error_code = error_code
        self.error_msg = "query failed" if error_code != "0" else "success"

    def next(self) -> bool:
        self._position += 1
        return self._position < len(self._rows)

    def get_row_data(self) -> list[str]:
        return self._rows[self._position]


class FakeBaostockSdk:
    def __init__(self, bar_error: str = "0") -> None:
        self.bar_error = bar_error
        self.login_calls = 0
        self.bar_calls: list[tuple[str, str]] = []

    def login(self) -> FakeResult:
        self.login_calls += 1
        return FakeResult([], [])

    def query_trade_dates(self, **_: object) -> FakeResult:
        return FakeResult(["calendar_date", "is_trading_day"], [["2026-08-03", "1"]])

    def query_history_k_data_plus(self, symbol: str, _: str, *, frequency: str, **__: object) -> FakeResult:
        self.bar_calls.append((symbol, frequency))
        return FakeResult(["date", "close"], [["2026-08-03", "100"]], self.bar_error)

    def query_adjust_factor(self, **_: object) -> FakeResult:
        return FakeResult(["code", "adjustDate", "foreAdjustFactor"], [["sh.600519", "2026-08-03", "1"]])

    def query_all_stock(self, **_: object) -> FakeResult:
        return FakeResult(["code"], [["sh.600519"]])


def test_baostock_probe_covers_two_a_shares_daily_30m_and_adjustment_factors() -> None:
    sdk = FakeBaostockSdk()
    provider = BaostockProvider(sdk=sdk, today=lambda: date(2026, 8, 3))

    capabilities = provider.probe_capabilities()

    assert sdk.login_calls == 1
    assert len(capabilities) == 7
    assert all(capability.status is CapabilityStatus.PASS for capability in capabilities)
    assert ("sh.600519", "d") in sdk.bar_calls
    assert ("sz.000001", "30") in sdk.bar_calls


def test_baostock_partial_bar_failure_is_reported_without_suppressing_other_capabilities() -> None:
    provider = BaostockProvider(sdk=FakeBaostockSdk(bar_error="1"), today=lambda: date(2026, 8, 3))

    capabilities = provider.probe_capabilities()

    assert capabilities[0].status is CapabilityStatus.PASS
    assert any(capability.status is CapabilityStatus.FAILED for capability in capabilities[1:])
