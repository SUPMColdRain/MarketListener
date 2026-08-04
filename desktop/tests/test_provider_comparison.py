"""Comparison reports describe differences and never create blended records."""

from __future__ import annotations

from market_monitor.providers import FetchResult, Provider, ProviderError, ErrorCategory
from market_monitor.providers.comparison import compare_daily_bars


class RecordsProvider(Provider):
    def __init__(self, name: str, bars: FetchResult, factors: FetchResult) -> None:
        self.name = name
        self._bars = bars
        self._factors = factors

    def probe_capabilities(self):
        return []

    def fetch_instruments(self) -> FetchResult:
        return FetchResult([])

    def fetch_bars(self) -> FetchResult:
        return self._bars

    def fetch_indicators(self) -> FetchResult:
        return self._factors

    def fetch_calendar(self) -> FetchResult:
        return FetchResult([])

    def health_check(self) -> FetchResult:
        return FetchResult([])


def test_comparison_reports_coverage_and_differences_without_blending() -> None:
    left = RecordsProvider(
        "left",
        FetchResult([{"date": "2026-08-01", "close": "10", "volume": "100"}, {"date": "2026-08-02", "close": "11", "volume": "110"}]),
        FetchResult([{"date": "2026-08-02", "factor": "1"}]),
    )
    right = RecordsProvider(
        "right",
        FetchResult([{"date": "2026-08-02", "close": "12", "volume": "110"}, {"date": "2026-08-03", "close": "13", "volume": "130"}]),
        FetchResult([{"date": "2026-08-02", "factor": "1"}]),
    )

    report = compare_daily_bars(left, right).to_dict()

    assert report["status"] == "PASS"
    assert report["row_blending"] == "DISABLED"
    assert report["comparison"]["overlap_days"] == 1
    assert report["comparison"]["close_differences"] == 1
    assert report["comparison"]["volume_differences"] == 0


def test_comparison_is_blocked_when_a_source_cannot_be_read() -> None:
    class BrokenProvider(RecordsProvider):
        def fetch_bars(self) -> FetchResult:
            raise ProviderError(ErrorCategory.NETWORK, "connection failed")

    report = compare_daily_bars(
        BrokenProvider("broken", FetchResult([]), FetchResult([])),
        RecordsProvider("working", FetchResult([]), FetchResult([])),
    ).to_dict()

    assert report["status"] == "BLOCKED"
    assert report["errors"][0]["category"] == "NETWORK"
