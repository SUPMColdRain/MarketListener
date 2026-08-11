"""Unit tests for the TDX F10 provider (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

import market_monitor.f10 as f10_module
from market_monitor.industry_graph.f10.providers import (
    ProviderError,
    TdxF10Provider,
    get_governance,
    get_provider,
    list_providers,
    reset_governance,
    reset_registry,
)
from market_monitor.industry_graph.f10.providers.tdx import (
    BASE_URLS,
    parse_tdx_company_summary,
    parse_tdx_company_survey,
    parse_tdx_datasets,
    parse_tdx_revenue,
    url_for_page,
)
from market_monitor.industry_graph.f10.segments import largest_revenue_segment

_FIXTURES = Path(__file__).parent / "fixtures" / "f10" / "tdx"


def _read(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8", errors="replace")


@pytest.fixture(autouse=True)
def _fast_governance() -> None:
    reset_governance()
    get_governance(max_rps=10.0)
    yield
    reset_governance()


def _install_fixture_fetcher(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    pages = {
        "gg_gsgk": "tdx_gsgk_688825.html",
        "gg_zxts": "tdx_zxts_688825.html",
        "gg_jyfx": "tdx_jyfx_688825.html",
    }
    calls: list[str] = []

    def fake_get(url: str, *, timeout: float, encoding: str, headers=None) -> str:
        calls.append(url)
        for fragment, name in pages.items():
            if f"/{fragment}/" in url:
                return _read(name)
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(f10_module, "_get", fake_get)
    return calls


def test_parse_tdx_datasets_two_layer_json() -> None:
    datasets = parse_tdx_datasets(_read("tdx_gsgk_688825.html"))
    key = "tql.CWServ.tdxf10_gg_gsgk_0_688825_"
    assert key in datasets
    result_sets = datasets[key]["ResultSets"]
    assert result_sets[0]["ColName"][:2] == ["imgsrc", "T003"]
    assert result_sets[0]["Content"][0][1] == "长鑫科技集团股份有限公司"


def test_parse_tdx_datasets_ignores_plain_html() -> None:
    assert parse_tdx_datasets("<html></html>") == {}


def test_parse_tdx_company_survey() -> None:
    datasets = parse_tdx_datasets(_read("tdx_gsgk_688825.html"))
    fields = parse_tdx_company_survey(datasets)
    assert fields["org_name"] == "长鑫科技集团股份有限公司"
    assert fields["org_name_en"] == "CXMT Corporation"
    assert fields["company_website"] == "www.cxmt.com"
    assert fields["industry_tdx"] == "电子—半导体"
    assert fields["industry_csrc"] == "制造业—计算机、通信和其他电子设备制造业"
    assert fields["main_business"] == "DRAM产品的研发、设计、生产及销售"
    assert "集成电路设计" in fields["business_scope"]


def test_parse_tdx_company_summary() -> None:
    datasets = parse_tdx_datasets(_read("tdx_zxts_688825.html"))
    fields = parse_tdx_company_summary(datasets)
    assert fields["name"] == "长鑫科技"
    assert fields["company_position"] == "中国第一、全球第四的DRAM厂商"
    assert fields["industry_tdx"] == "电子-半导体"
    assert fields["industry_csrc"] == "计算机、通信和其他电子设备制造业"
    assert fields["main_business"] == "DRAM产品的研发、设计、生产及销售"
    assert fields["total_shares"] == 66880886077.0
    assert fields["float_shares"] == 4503038971.0
    snapshot = fields["total_market_cap"]
    assert snapshot["value"] == pytest.approx(3430989455750.1)
    assert snapshot["currency"] == "CNY"
    assert snapshot["asOf"] == "2026-08-10"
    assert snapshot["source"] == "tdx"
    assert "company_highlight" not in fields


def test_parse_tdx_revenue_rows() -> None:
    datasets = parse_tdx_datasets(_read("tdx_jyfx_688825.html"))
    parsed = parse_tdx_revenue(datasets, fetched_at="2026-08-11T00:00:00Z")
    rows = parsed["revenue_breakdown"]
    assert len(rows) == 7
    assert parsed["fields"]["main_business"] == "DRAM产品的研发、设计、生产及销售"
    first = rows[0]
    assert first["period"] == "2025-12-31"
    assert first["item"] == "LPDDR系列"
    assert first["item_name"] == "LPDDR系列"
    assert first["classification"] == "product"
    assert first["classification_label"] == "按产品(项目)"
    assert first["revenue"] == pytest.approx(40703545008.2)
    assert first["income"] == pytest.approx(40703545008.2)
    assert first["ratio"] == pytest.approx(0.65864065)
    assert first["revenue_share_pct"] == pytest.approx(65.864065)
    assert first["cost"] == pytest.approx(24327445765.76)
    assert first["gross_profit"] == pytest.approx(16376099242.44)
    assert first["gross_margin_pct"] == pytest.approx(40.232612)
    assert first["source"] == "tdx"
    assert first["fetched_at"] == "2026-08-11T00:00:00Z"
    region = next(row for row in rows if row["item"] == "境外:中国香港")
    assert region["classification"] == "region"
    assert region["revenue"] == pytest.approx(33345364100.0)
    assert "cost" not in region
    assert "gross_margin_pct" not in region


def test_largest_revenue_segment_skips_region() -> None:
    datasets = parse_tdx_datasets(_read("tdx_jyfx_688825.html"))
    parsed = parse_tdx_revenue(datasets)
    largest = largest_revenue_segment(parsed["revenue_breakdown"])
    assert largest is not None
    assert largest["item_name"] == "LPDDR系列"
    assert largest["classification"] == "product"
    assert largest["revenue"] == pytest.approx(40703545008.2)


def test_url_for_page() -> None:
    url = url_for_page("company_survey", "688825")
    assert url.startswith(f"{BASE_URLS[0]}/site/tdxf10/gg_gsgk/688825.html")
    assert "gp=688825" in url
    jyfx = url_for_page("business_analysis", "688825", base_url=BASE_URLS[1])
    assert jyfx.startswith(f"{BASE_URLS[1]}/site/tdxf10/gg_jyfx/688825.html")
    with pytest.raises(ProviderError):
        url_for_page("nope", "688825")


def test_registry_contains_tdx() -> None:
    reset_registry()
    try:
        providers = list_providers()
        assert "tdx" in providers
        assert providers["tdx"].name == "tdx"
        assert get_provider("tdx").name == "tdx"
    finally:
        reset_registry()


def test_fetch_profile_combines_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fixture_fetcher(monkeypatch)
    result = TdxF10Provider().fetch_profile("688825")
    assert any("gg_gsgk" in url for url in calls)
    assert any("gg_zxts" in url for url in calls)
    assert result.page == "company_survey,company_summary"
    assert result.market == "CN"
    assert result.fields["org_name"] == "长鑫科技集团股份有限公司"
    assert result.fields["name"] == "长鑫科技"
    assert result.fields["company_position"] == "中国第一、全球第四的DRAM厂商"
    assert result.provenance["org_name"]["sourcePage"] == "company_survey"
    assert result.provenance["company_position"]["sourcePage"] == "company_summary"


def test_fetch_profile_single_page(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fixture_fetcher(monkeypatch)
    result = TdxF10Provider().fetch_profile("688825", pages=("company_summary",))
    assert calls and all("gg_zxts" in url for url in calls)
    assert result.page == "company_summary"
    assert "name" in result.fields


def test_fetch_revenue_uses_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fixture_fetcher(monkeypatch)
    result = TdxF10Provider().fetch_revenue("688825")
    assert calls and "gg_jyfx" in calls[0]
    assert result.page == "business_analysis"
    assert len(result.revenue_breakdown) == 7
    assert result.fields["main_business"] == "DRAM产品的研发、设计、生产及销售"
    assert result.provenance["revenue_breakdown"]["source"] == "tdx"


def test_fetch_profile_unknown_page() -> None:
    with pytest.raises(ProviderError):
        TdxF10Provider().fetch_profile("688825", pages=("business_analysis",))


def test_fetch_hk_unsupported() -> None:
    provider = TdxF10Provider()
    with pytest.raises(ProviderError):
        provider.fetch_profile("00700", market="HK")
    with pytest.raises(ProviderError):
        provider.fetch_revenue("00700", market="HK")


def test_fetch_profile_plain_html_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, *, timeout: float, encoding: str, headers=None) -> str:
        return "<html></html>"

    monkeypatch.setattr(f10_module, "_get", fake_get)
    with pytest.raises(ProviderError):
        TdxF10Provider().fetch_profile("688825")
