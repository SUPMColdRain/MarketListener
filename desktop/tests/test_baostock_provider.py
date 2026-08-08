"""Baostock mapping tests use fixed SDK responses only."""

from __future__ import annotations

from datetime import date

import pytest

from market_monitor.providers import CapabilityStatus, ErrorCategory, ProviderError
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
    def __init__(self, bar_error: str = "0", *, login_error: Exception | None = None, calendar_error: Exception | None = None, bar_rows: list[list[str]] | None = None) -> None:
        self.bar_error = bar_error
        self.login_error = login_error
        self.calendar_error = calendar_error
        self.bar_rows = bar_rows if bar_rows is not None else [["2026-08-03", "100"]]
        self.login_calls = 0
        self.bar_calls: list[tuple[str, str]] = []
        self.bar_kwargs: list[dict[str, object]] = []

    def login(self) -> FakeResult:
        if self.login_error is not None:
            raise self.login_error
        self.login_calls += 1
        return FakeResult([], [])

    def query_trade_dates(self, **_: object) -> FakeResult:
        if self.calendar_error is not None:
            raise self.calendar_error
        return FakeResult(["calendar_date", "is_trading_day"], [["2026-08-03", "1"]])

    def query_history_k_data_plus(self, symbol: str, fields: str, *, frequency: str, **kwargs: object) -> FakeResult:
        self.bar_calls.append((symbol, frequency))
        self.bar_kwargs.append({"symbol": symbol, "fields": fields, "frequency": frequency, **kwargs})
        return FakeResult(["date", "close"], self.bar_rows, self.bar_error)

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


def test_baostock_bar_request_uses_expected_fields_periods_and_forward_adjustment() -> None:
    sdk = FakeBaostockSdk()
    provider = BaostockProvider(sdk=sdk, today=lambda: date(2026, 8, 3))

    provider.probe_capabilities()

    expected_fields = {"date", "time", "code", "open", "high", "low", "close", "volume", "amount", "adjustflag"}
    assert len(sdk.bar_kwargs) == 4
    for kwargs in sdk.bar_kwargs:
        assert set(str(kwargs["fields"]).split(",")) == expected_fields
        assert kwargs["adjustflag"] == "3"
    frequencies = {kwargs["frequency"] for kwargs in sdk.bar_kwargs}
    assert frequencies == {"d", "30"}


def test_baostock_network_error_is_classified_network() -> None:
    provider = BaostockProvider(
        sdk=FakeBaostockSdk(login_error=TimeoutError("网络接收超时")),
        today=lambda: date(2026, 8, 3),
    )

    with pytest.raises(ProviderError) as exc_info:
        provider.probe_capabilities()

    assert exc_info.value.category is ErrorCategory.NETWORK


def test_baostock_calendar_network_timeout_is_an_isolated_failed_capability() -> None:
    provider = BaostockProvider(
        sdk=FakeBaostockSdk(calendar_error=ConnectionError("网络接收错误")),
        today=lambda: date(2026, 8, 3),
    )

    capabilities = provider.probe_capabilities()

    assert capabilities[0].status is CapabilityStatus.FAILED
    assert capabilities[0].error is not None
    assert capabilities[0].error.category is ErrorCategory.NETWORK
    assert all(capability.status is CapabilityStatus.PASS for capability in capabilities[1:])


def test_baostock_empty_bar_result_is_reported_as_no_coverage() -> None:
    provider = BaostockProvider(
        sdk=FakeBaostockSdk(bar_rows=[]),
        today=lambda: date(2026, 8, 3),
    )

    capabilities = provider.probe_capabilities()

    failed = [capability for capability in capabilities[1:] if capability.name.endswith("_1d")]
    assert failed
    assert all(capability.status is CapabilityStatus.FAILED for capability in failed)
    assert all(capability.error is not None and capability.error.category is ErrorCategory.NO_COVERAGE for capability in failed)
