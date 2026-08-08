"""AkShare mapping tests use fixed records and do not represent live acceptance."""

from __future__ import annotations

import pytest

from market_monitor.providers import CapabilityStatus, ErrorCategory, ProviderError
from market_monitor.providers.akshare import AkShareProvider


class FakeAkShareSdk:
    def __init__(self, spot: object | None = None, calendar: object | None = None, fund: object | None = None, bars: object | None = None) -> None:
        self.spot = spot if spot is not None else [{"代码": "600519", "涨跌幅": 10.1}, {"代码": "000001", "涨跌幅": -10.2}, {"代码": "600000", "涨跌幅": 0.0}]
        self.calendar = calendar if calendar is not None else [{"trade_date": "2026-08-03"}]
        self.fund = fund if fund is not None else [{"日期": "2026-08-03", "主力净流入-净额": 1}]
        self.bars = bars if bars is not None else [{"日期": "2026-08-03", "收盘": 100}]
        self.bar_kwargs: list[dict[str, object]] = []

    def stock_zh_a_spot_em(self):
        if isinstance(self.spot, Exception):
            raise self.spot
        return self.spot

    def stock_market_fund_flow(self):
        if isinstance(self.fund, Exception):
            raise self.fund
        return self.fund

    def stock_zh_a_hist(self, **kwargs: object):
        self.bar_kwargs.append(kwargs)
        if isinstance(self.bars, Exception):
            raise self.bars
        return self.bars

    def tool_trade_date_hist_sina(self):
        if isinstance(self.calendar, Exception):
            raise self.calendar
        return self.calendar


def test_akshare_probe_calculates_market_breadth_and_limit_counts() -> None:
    capabilities = AkShareProvider(sdk=FakeAkShareSdk()).probe_capabilities()

    assert [capability.name for capability in capabilities] == [
        "health_check",
        "a_share_rise_fall_counts",
        "a_share_price_limit_counts",
        "trading_calendar",
        "market_fund_flow",
        "cn_stock_sh.600519_1d",
    ]
    assert [capability.status for capability in capabilities] == [CapabilityStatus.PASS] * 6
    assert "up=1; down=1; flat=1" in (capabilities[1].detail or "")
    assert "limit_up=1; limit_down=1" in (capabilities[2].detail or "")
    bars = capabilities[5]
    assert bars.registration.request.operation.value == "bars"
    assert bars.registration.request.period == "1d"
    assert bars.row_count == 1


def test_akshare_bars_capability_reports_failure_without_wiping_others() -> None:
    capabilities = AkShareProvider(sdk=FakeAkShareSdk(bars=ProviderError(ErrorCategory.NETWORK, "down"))).probe_capabilities()

    assert capabilities[0].status is CapabilityStatus.PASS
    assert capabilities[5].name == "cn_stock_sh.600519_1d"
    assert capabilities[5].status is CapabilityStatus.FAILED
    assert capabilities[5].error is not None


def test_akshare_missing_change_field_is_reported_as_provider_failure() -> None:
    capabilities = AkShareProvider(sdk=FakeAkShareSdk(spot=[{"代码": "600519"}])).probe_capabilities()

    assert capabilities[0].status is CapabilityStatus.PASS
    assert capabilities[1].status is CapabilityStatus.FAILED
    assert capabilities[2].status is CapabilityStatus.FAILED
    assert capabilities[3].status is CapabilityStatus.PASS
    assert capabilities[4].status is CapabilityStatus.PASS
    assert "[PROVIDER]" in (capabilities[1].detail or "")


def test_akshare_snapshot_failure_does_not_erase_calendar_or_fund_results() -> None:
    capabilities = AkShareProvider(
        sdk=FakeAkShareSdk(spot=ConnectionError("connection aborted"))
    ).probe_capabilities()

    assert capabilities[0].status is CapabilityStatus.FAILED
    assert capabilities[0].error is not None
    assert capabilities[0].error.category is ErrorCategory.NETWORK
    assert capabilities[1].status is CapabilityStatus.PASS
    assert capabilities[2].status is CapabilityStatus.PASS


def test_akshare_calendar_failure_does_not_erase_snapshot_or_fund_results() -> None:
    capabilities = AkShareProvider(
        sdk=FakeAkShareSdk(calendar=TimeoutError("network timeout"))
    ).probe_capabilities()

    assert capabilities[0].status is CapabilityStatus.PASS
    assert capabilities[3].name == "trading_calendar"
    assert capabilities[3].status is CapabilityStatus.FAILED
    assert capabilities[3].error is not None
    assert capabilities[3].error.category is ErrorCategory.NETWORK
    assert capabilities[4].status is CapabilityStatus.PASS


def test_akshare_fund_failure_does_not_erase_snapshot_or_calendar_results() -> None:
    capabilities = AkShareProvider(
        sdk=FakeAkShareSdk(fund=ConnectionError("fund endpoint closed"))
    ).probe_capabilities()

    assert capabilities[0].status is CapabilityStatus.PASS
    assert capabilities[3].status is CapabilityStatus.PASS
    assert capabilities[4].status is CapabilityStatus.FAILED
    assert capabilities[4].error is not None


def test_akshare_bars_are_normalised_and_forward_adjusted() -> None:
    sdk = FakeAkShareSdk(
        bars=[{"日期": "2026-08-03", "开盘": 1, "收盘": 2, "最高": 3, "最低": 1, "成交量": 10, "成交额": 20}]
    )
    provider = AkShareProvider(sdk=sdk)

    result = provider.fetch_bars()

    assert sdk.bar_kwargs == [{"symbol": "600519", "period": "daily", "adjust": "qfq"}]
    assert result.records == [{"date": "2026-08-03", "open": 1, "close": 2, "high": 3, "low": 1, "volume": 10, "amount": 20}]
    assert result.earliest == "2026-08-03"
    assert result.latest == "2026-08-03"


def test_akshare_bars_network_error_is_classified_network() -> None:
    provider = AkShareProvider(sdk=FakeAkShareSdk(bars=ConnectionError("connection aborted")))

    with pytest.raises(ProviderError) as exc_info:
        provider.fetch_bars()

    assert exc_info.value.category is ErrorCategory.NETWORK
