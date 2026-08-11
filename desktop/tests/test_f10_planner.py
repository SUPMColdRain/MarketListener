"""Unit tests for the missing-field planner (pure, no network)."""

from __future__ import annotations

from market_monitor.industry_graph.f10.planner import (
    PROVIDER_PRIORITY,
    compute_missing_fields,
    merge_profile_results,
    plan_requests,
    plan_revenue_requests,
)
from market_monitor.industry_graph.f10.providers import (
    F10Provider,
    ProviderCapabilities,
    ProviderPage,
    ProviderResult,
)


class FakeProfileProvider(F10Provider):
    name = "fake_a"
    capabilities = ProviderCapabilities(profile=True, revenue=True)

    @property
    def pages(self) -> tuple[ProviderPage, ...]:
        return (
            ProviderPage(
                name="zxts",
                market="CN",
                fields=("company_position", "industry_tdx", "main_business", "total_shares"),
            ),
            ProviderPage(
                name="jyfx",
                market="CN",
                fields=("revenue_breakdown",),
            ),
        )

    def fetch_profile(self, code: str, *, market: str = "CN", pages=None) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            page="zxts",
            market="CN",
            code=code,
            fetched_at="2026-08-09T00:00:00+00:00",
            fields={
                "company_position": "Market leader",
                "industry_tdx": "Semiconductors",
                "main_business": "Memory",
                "total_shares": 1_000_000_000,
            },
        )

    def fetch_revenue(self, code: str, *, market: str = "CN", pages=None) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            page="jyfx",
            market="CN",
            code=code,
            fetched_at="2026-08-09T00:00:00+00:00",
            fields={},
            revenue_breakdown=(),
        )


class FakeHighlightProvider(F10Provider):
    name = "fake_b"
    capabilities = ProviderCapabilities(profile=True, hk_supported=True)

    @property
    def pages(self) -> tuple[ProviderPage, ...]:
        return (
            ProviderPage(
                name="basic",
                market="CN",
                fields=("company_highlight", "industry_sw", "business_scope"),
            ),
            ProviderPage(
                name="basic",
                market="HK",
                fields=("name", "main_business", "industry_hs"),
            ),
        )

    def fetch_profile(self, code: str, *, market: str = "CN", pages=None) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            page="basic",
            market=market.upper(),
            code=code,
            fetched_at="2026-08-09T00:00:00+00:00",
            fields={
                "company_highlight": "First in class",
                "industry_sw": "Semiconductor",
                "business_scope": "Design and sales",
            },
        )


class FakeWildcardProvider(F10Provider):
    """A provider whose single page serves both CN and HK (Eastmoney-style)."""

    name = "fake_wide"
    capabilities = ProviderCapabilities(profile=True, hk_supported=True)

    @property
    def pages(self) -> tuple[ProviderPage, ...]:
        return (
            ProviderPage(
                name="company_survey",
                fields=("company_intro", "business_scope", "industry_em"),
                market="*",
            ),
        )

    def fetch_profile(
        self,
        code: str,
        *,
        market: str = "CN",
        pages=None,
    ) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            page="company_survey",
            market=market.upper(),
            code=code,
            fetched_at="2026-08-11T00:00:00Z",
            fields={},
        )


class FakeThsPriorityProvider(F10Provider):
    """THS-shaped provider used to verify source-priority planning."""

    name = "ths"
    capabilities = ProviderCapabilities(profile=True, revenue=True)

    @property
    def pages(self) -> tuple[ProviderPage, ...]:
        return (
            ProviderPage(
                name="company_survey",
                market="CN",
                fields=("company_intro", "industry_sw", "products"),
            ),
            ProviderPage(
                name="operate_revenue",
                market="CN",
                fields=("revenue_breakdown",),
            ),
        )

    def fetch_profile(self, code: str, *, market: str = "CN", pages=None) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            page="company_survey",
            market="CN",
            code=code,
            fetched_at="2026-08-11T00:00:00Z",
            fields={"company_intro": "THS intro", "industry_sw": "Semiconductor", "products": ["DDR5"]},
        )

    def fetch_revenue(self, code: str, *, market: str = "CN") -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            page="operate_revenue",
            market="CN",
            code=code,
            fetched_at="2026-08-11T00:00:00Z",
            fields={},
            revenue_breakdown=(),
        )


class FakeEastmoneyPriorityProvider(F10Provider):
    """Eastmoney-shaped provider used to verify fallback planning."""

    name = "eastmoney"
    capabilities = ProviderCapabilities(profile=True, revenue=True, hk_supported=True)

    @property
    def pages(self) -> tuple[ProviderPage, ...]:
        return (
            ProviderPage(
                name="company_survey",
                fields=("company_intro", "business_scope", "industry_em"),
                market="*",
            ),
            ProviderPage(
                name="business_analysis",
                market="CN",
                fields=("revenue_breakdown",),
            ),
        )

    def fetch_profile(self, code: str, *, market: str = "CN", pages=None) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            page="company_survey",
            market=market.upper(),
            code=code,
            fetched_at="2026-08-11T00:00:00Z",
            fields={"company_intro": "EM intro", "business_scope": "Scope", "industry_em": "Semiconductor"},
        )

    def fetch_revenue(self, code: str, *, market: str = "CN") -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            page="business_analysis",
            market="CN",
            code=code,
            fetched_at="2026-08-11T00:00:00Z",
            fields={},
            revenue_breakdown=(),
        )


def test_compute_missing_fields() -> None:
    record = {
        "code": "688825",
        "name": "Example",
        "org_name": "Example Co",
        "org_profile": "A real profile.",
        "industry_em": "Semiconductors",
        "quote": {"total_market_cap_yi": 100.0},
    }
    missing = compute_missing_fields(record)
    assert "name" not in missing
    assert "company_intro" not in missing
    assert "total_market_cap" not in missing
    assert "company_position" in missing
    assert "company_highlight" in missing
    assert "main_business" in missing
    assert "industry_tdx" in missing


def test_plan_requests_minimal() -> None:
    providers = {"fake_a": FakeProfileProvider(), "fake_b": FakeHighlightProvider()}
    missing = {"company_position", "company_highlight", "industry_tdx", "main_business", "business_scope"}
    requests, remaining = plan_requests(missing, providers, market="CN")
    assert remaining == set()
    names = {page for _, page in requests}
    assert names == {"zxts", "basic"}
    # Greedy should not request both providers' pages more than once.
    assert len(requests) == 2


def test_plan_requests_hk() -> None:
    providers = {"fake_a": FakeProfileProvider(), "fake_b": FakeHighlightProvider()}
    requests, remaining = plan_requests({"industry_hs", "main_business", "name"}, providers, market="HK")
    assert remaining == set()
    assert requests == [("fake_b", "basic")]
    assert all(provider != "fake_a" for provider, _ in requests)


def test_plan_requests_wildcard_page_serves_cn_and_hk() -> None:
    providers = {"fake_wide": FakeWildcardProvider()}
    for market in ("CN", "HK"):
        requests, remaining = plan_requests(
            {"company_intro", "business_scope", "industry_em"},
            providers,
            market=market,
        )
        assert remaining == set()
        assert requests == [("fake_wide", "company_survey")]


def test_plan_revenue_requests_only_capable() -> None:
    providers = {"fake_a": FakeProfileProvider(), "fake_b": FakeHighlightProvider()}
    requests = plan_revenue_requests(providers, market="CN")
    assert requests == [("fake_a", "jyfx")]
    assert plan_revenue_requests(providers, market="HK") == []


def test_plan_requests_prefers_ths_on_equal_coverage() -> None:
    providers = {
        "eastmoney": FakeEastmoneyPriorityProvider(),
        "ths": FakeThsPriorityProvider(),
    }
    # Both pages cover company_intro; THS must win the tie.
    requests, remaining = plan_requests({"company_intro"}, providers, market="CN")
    assert remaining == set()
    assert requests == [("ths", "company_survey")]
    # THS-only fields still request THS even when Eastmoney is registered.
    requests, remaining = plan_requests(
        {"company_intro", "industry_sw", "products"}, providers, market="CN"
    )
    assert remaining == set()
    assert requests == [("ths", "company_survey")]
    # Fields only Eastmoney can fill fall back to Eastmoney.
    requests, remaining = plan_requests({"business_scope"}, providers, market="CN")
    assert remaining == set()
    assert requests == [("eastmoney", "company_survey")]
    # HK has no THS support, so Eastmoney remains the F10 source.
    requests, remaining = plan_requests({"company_intro"}, providers, market="HK")
    assert remaining == set()
    assert requests == [("eastmoney", "company_survey")]


def test_plan_revenue_requests_orders_ths_before_eastmoney() -> None:
    providers = {
        "eastmoney": FakeEastmoneyPriorityProvider(),
        "ths": FakeThsPriorityProvider(),
    }
    assert PROVIDER_PRIORITY["ths"] < PROVIDER_PRIORITY["eastmoney"]
    assert plan_revenue_requests(providers, market="CN") == [
        ("ths", "operate_revenue"),
        ("eastmoney", "business_analysis"),
    ]
    assert plan_revenue_requests(providers, market="HK") == []


def test_merge_profile_results_fills_and_keeps_base() -> None:
    base = {"code": "688825", "name": "Example", "business_scope": "Original scope"}
    result = FakeProfileProvider().fetch_profile("688825")
    merged = merge_profile_results(base, [result])
    assert merged["business_scope"] == "Original scope"
    assert merged["company_position"] == "Market leader"
    assert merged["provenance"]["company_position"]["source"] == "fake_a"


def test_merge_profile_results_products_union() -> None:
    base = {"products": ["DDR4"]}

    class Result:
        provider = "fake"
        page = "p"
        fetched_at = "2026-08-09T00:00:00+00:00"
        fields = {"products": ["DDR4", "DDR5", "DDR4"]}
        provenance = {}

    merged = merge_profile_results(base, [Result()])
    assert merged["products"] == ["DDR4", "DDR5"]
