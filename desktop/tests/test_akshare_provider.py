"""AkShare mapping tests use fixed records and do not represent live acceptance."""

from __future__ import annotations

from market_monitor.providers import CapabilityStatus
from market_monitor.providers.akshare import AkShareProvider


class FakeAkShareSdk:
    def __init__(self, spot: object | None = None) -> None:
        self.spot = spot if spot is not None else [{"代码": "600519", "涨跌幅": 10.1}, {"代码": "000001", "涨跌幅": -10.2}, {"代码": "600000", "涨跌幅": 0.0}]

    def stock_zh_a_spot_em(self):
        return self.spot

    def stock_market_fund_flow(self):
        return [{"日期": "2026-08-03", "主力净流入-净额": 1}]

    def stock_zh_a_hist(self, **_: object):
        return [{"日期": "2026-08-03", "收盘": 100}]

    def tool_trade_date_hist_sina(self):
        return [{"trade_date": "2026-08-03"}]


def test_akshare_probe_calculates_market_breadth_and_limit_counts() -> None:
    capabilities = AkShareProvider(sdk=FakeAkShareSdk()).probe_capabilities()

    assert [capability.status for capability in capabilities] == [CapabilityStatus.PASS] * 4
    assert "up=1; down=1; flat=1" in (capabilities[1].detail or "")
    assert "limit_up=1; limit_down=1" in (capabilities[2].detail or "")


def test_akshare_missing_change_field_is_reported_as_provider_failure() -> None:
    capabilities = AkShareProvider(sdk=FakeAkShareSdk(spot=[{"代码": "600519"}])).probe_capabilities()

    assert capabilities[0].status is CapabilityStatus.PASS
    assert capabilities[1].status is CapabilityStatus.FAILED
    assert capabilities[2].status is CapabilityStatus.FAILED
    assert "[PROVIDER]" in (capabilities[1].detail or "")
