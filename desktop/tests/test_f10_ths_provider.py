"""Unit tests for the THS F10 provider (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_monitor.industry_graph.f10.providers import (
    ProviderError,
    ThsF10Provider,
    list_providers,
    reset_registry,
)
from market_monitor.industry_graph.f10.providers.ths import (
    _split_products,
    parse_company_survey,
    parse_operate_business,
    parse_revenue_payload,
    ths_market_id,
)


COMPANY_HTML = """
<html><body>
<input id="stockName" type="hidden" value="贵州茅台">
<table class="m_table">
  <tbody>
    <tr>
      <td><strong class="hltip fl">公司名称：</strong><span>贵州茅台酒股份有限公司</span></td>
      <td><strong class="hltip fl">英文名称：</strong><span>Kweichow Moutai Co.,Ltd.</span></td>
    </tr>
    <tr>
      <td><strong class="hltip fl">所属申万行业：</strong><span>食品饮料 — 白酒Ⅱ</span></td>
      <td><strong class="hltip fl">董　　秘：</strong><span>余思明</span></td>
    </tr>
    <tr>
      <td colspan="2"><strong class="hltip fl">主营业务：</strong><span>茅台酒及系列酒的生产与销售。</span></td>
    </tr>
    <tr>
      <td colspan="2"><strong class="hltip fl">产品名称：</strong><span>茅台酒 、其他系列酒</span></td>
    </tr>
    <tr>
      <td colspan="2"><strong class="hltip fl">公司网址：</strong><span>www.moutaichina.com</span></td>
    </tr>
    <tr class="intro">
      <td colspan="2">
        <strong class="hltip">公司简介：</strong>
        <p class="tip lh24">贵州茅台酒股份有限公司的主营业务是茅台酒及系列酒的生产与销售。</p>
      </td>
    </tr>
  </tbody>
</table>
<div class="m_box">
  <h2>发行相关</h2>
  <table class="m_table">
    <tr><td><strong class="hltip">成立日期：</strong><span>1999-11-20</span></td></tr>
  </table>
</div>
</body></html>
"""


OPERATE_HTML = """
<html><body>
<input id="stockCode" type="hidden" value="600519">
<input id="stockName" type="hidden" value="贵州茅台">
<input id="marketId" type="hidden" value="17">
<ul class="main_intro_list">
  <li><span class="hltip f12">主营业务：</span><p>茅台酒及系列酒的生产与销售。</p></li>
  <li><span class="hltip f12">产品类型：</span><p>茅台酒、其他系列酒</p></li>
  <li><span class="hltip f12">产品名称：</span><p>茅台酒 、其他系列酒</p></li>
  <li><span class="hltip f12">经营范围：</span><p>茅台酒及系列酒的生产与销售；防伪技术开发。</p></li>
</ul>
</body></html>
"""


REVENUE_PAYLOAD = {
    "status_code": 0,
    "status_msg": "success",
    "data": [
        {
            "analysis_type": "area",
            "time_operate_index_item_list": [
                {
                    "time": "2026-03-31",
                    "product_index_item_list": [
                        {
                            "product_name": "国内",
                            "level": "1",
                            "parent": "ROOT",
                            "sort_value": 53733787300.0,
                            "index_analysis_list": [
                                {
                                    "index_id": "income",
                                    "index_value": "53733787300.00",
                                    "index_unit": "元",
                                    "index_currency": "CNY",
                                    "account": "0.98228385",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "analysis_type": "product",
            "time_operate_index_item_list": [
                {
                    "time": "2026-03-31",
                    "product_index_item_list": [
                        {
                            "product_name": "茅台酒",
                            "level": "1",
                            "parent": "ROOT",
                            "sort_value": 46004868600.0,
                            "index_analysis_list": [
                                {
                                    "index_id": "income",
                                    "index_value": "46004868600.00",
                                    "index_unit": "元",
                                    "index_currency": "CNY",
                                    "account": "0.84099487",
                                }
                            ],
                        },
                        {
                            "product_name": "其他业务总计",
                            "level": "1",
                            "parent": "ROOT",
                            "sort_value": 5387695900.0,
                            "index_analysis_list": [
                                {
                                    "index_id": "income",
                                    "index_value": "5387695900.00",
                                    "index_unit": "元",
                                    "index_currency": "CNY",
                                    "account": "0.09846810",
                                }
                            ],
                        },
                    ],
                },
                {
                    "time": "2025-12-31 00:00:00",
                    "product_index_item_list": [
                        {
                            "product_name": "系列酒",
                            "level": "1",
                            "parent": "ROOT",
                            "sort_value": 19734000000.0,
                            "index_analysis_list": [
                                {
                                    "index_id": "income",
                                    "index_value": "19734000000.00",
                                    "index_unit": "元",
                                    "index_currency": "CNY",
                                    "account": "0.11465219",
                                },
                                {
                                    "index_id": "cost",
                                    "index_value": "1230000000.00",
                                    "index_unit": "元",
                                    "index_currency": "CNY",
                                    "account": "0.08261021",
                                },
                                {
                                    "index_id": "gross_profit",
                                    "index_value": "18504000000.00",
                                    "index_unit": "元",
                                    "index_currency": "CNY",
                                    "account": "0.11766031",
                                },
                                {
                                    "index_id": "gross_profit_rate",
                                    "index_value": "0.93765000",
                                    "index_unit": "元",
                                    "index_currency": "CNY",
                                    "account": "0.35027952",
                                },
                            ],
                        }
                    ],
                },
            ],
        },
        {
            "analysis_type": "industry",
            "time_operate_index_item_list": [],
        },
    ],
}


def test_ths_market_id_mapping() -> None:
    assert ths_market_id("600519") == 17
    assert ths_market_id("688981") == 17
    assert ths_market_id("000001") == 33
    assert ths_market_id("300750") == 33
    assert ths_market_id("430047") == 151
    assert ths_market_id("920001") == 151
    assert ths_market_id("900901") == 18
    assert ths_market_id("200002") == 105
    with pytest.raises(ProviderError):
        ths_market_id("500000")


def test_parse_company_survey() -> None:
    fields = parse_company_survey(COMPANY_HTML)
    assert fields["name"] == "贵州茅台"
    assert fields["org_name"] == "贵州茅台酒股份有限公司"
    assert fields["org_name_en"] == "Kweichow Moutai Co.,Ltd."
    assert fields["industry_sw"] == "食品饮料 — 白酒Ⅱ"
    assert fields["main_business"] == "茅台酒及系列酒的生产与销售。"
    assert fields["products"] == ("茅台酒", "其他系列酒")
    assert fields["company_website"] == "www.moutaichina.com"
    assert fields["company_intro"] == "贵州茅台酒股份有限公司的主营业务是茅台酒及系列酒的生产与销售。"
    # 发行相关 table outside the survey table is not picked up.
    assert "org_name" in fields
    assert fields.get("成立日期") is None


def test_parse_operate_business() -> None:
    fields = parse_operate_business(OPERATE_HTML)
    assert fields["name"] == "贵州茅台"
    assert fields["main_business"] == "茅台酒及系列酒的生产与销售。"
    assert fields["business_scope"] == "茅台酒及系列酒的生产与销售；防伪技术开发。"
    assert fields["products"] == ("茅台酒", "其他系列酒")


def test_parse_revenue_payload() -> None:
    fetched_at = "2026-08-11T00:00:00+00:00"
    rows = parse_revenue_payload(REVENUE_PAYLOAD, fetched_at=fetched_at)
    assert len(rows) == 2
    first = rows[0]
    assert first["item"] == "茅台酒"
    assert first["revenue"] == 46004868600.0
    assert first["income"] == 46004868600.0
    assert first["currency"] == "CNY"
    assert first["ratio"] == pytest.approx(0.84099487)
    assert first["revenue_share_pct"] == pytest.approx(84.099487)
    assert first["period"] == "2026-03-31"
    assert first["classification"] == "product"
    assert first["classification_label"] == "产品"
    assert first["source"] == "ths_f10"
    assert first["fetched_at"] == fetched_at
    annual = rows[1]
    assert annual["period"] == "2025-12-31"
    assert annual["cost"] == 1230000000.0
    assert annual["gross_profit"] == 18504000000.0
    assert annual["gross_margin_pct"] == pytest.approx(93.765)
    # Aggregate totals and non-product analysis types are excluded.
    assert all(row["classification"] == "product" for row in rows)
    assert all(row["item"] != "其他业务总计" for row in rows)
    assert all(row["item"] != "国内" for row in rows)


def test_fetch_profile_requests_only_selected_page(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_get(url: str, *, provider: str, encoding: str = "utf-8", **kwargs: object) -> str:
        calls.append((url, encoding))
        if url.endswith("/company.html"):
            return COMPANY_HTML
        if url.endswith("/operate.html"):
            return OPERATE_HTML
        return ""

    monkeypatch.setattr(
        "market_monitor.industry_graph.f10.providers.ths.governed_get",
        fake_get,
    )
    provider = ThsF10Provider()
    profile = provider.fetch_profile("600519", pages=("company_survey",))
    assert [url for url, _ in calls] == ["https://basic.10jqka.com.cn/600519/company.html"]
    assert calls[0][1] == "gbk"
    assert profile.page == "company_survey"
    assert profile.fields["name"] == "贵州茅台"
    assert profile.fields["org_name"] == "贵州茅台酒股份有限公司"
    assert profile.fields["code"] == "600519"
    assert profile.provenance["company_website"]["sourcePage"] == "company_survey"

    calls.clear()
    profile = provider.fetch_profile("600519", pages=("operate_business",))
    assert [url for url, _ in calls] == ["https://basic.10jqka.com.cn/600519/operate.html"]
    assert profile.fields["business_scope"] == "茅台酒及系列酒的生产与销售；防伪技术开发。"
    assert profile.provenance["business_scope"]["sourcePage"] == "operate_business"


def test_fetch_profile_default_fetches_both_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_get(url: str, *, provider: str, encoding: str = "utf-8", **kwargs: object) -> str:
        calls.append(url)
        if url.endswith("/company.html"):
            return COMPANY_HTML
        if url.endswith("/operate.html"):
            return OPERATE_HTML
        return ""

    monkeypatch.setattr(
        "market_monitor.industry_graph.f10.providers.ths.governed_get",
        fake_get,
    )
    profile = ThsF10Provider().fetch_profile("600519")
    assert len(calls) == 2
    assert profile.page == "profile"
    assert profile.fields["business_scope"] == "茅台酒及系列酒的生产与销售；防伪技术开发。"
    # company_survey is fetched first, so its provenance wins for overlaps.
    assert profile.provenance["name"]["sourcePage"] == "company_survey"


def test_fetch_revenue_parses_api(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_get(url: str, *, provider: str, encoding: str = "utf-8", **kwargs: object) -> str:
        calls.append((url, encoding))
        return json.dumps(REVENUE_PAYLOAD)

    monkeypatch.setattr(
        "market_monitor.industry_graph.f10.providers.ths.governed_get",
        fake_get,
    )
    result = ThsF10Provider().fetch_revenue("600519")
    assert len(calls) == 1
    assert calls[0][1] == "utf-8"
    assert "market=17" in calls[0][0]
    assert result.provider == "ths"
    assert result.page == "operate_revenue"
    assert result.code == "600519"
    assert len(result.revenue_breakdown) == 2
    assert result.revenue_breakdown[0]["item"] == "茅台酒"
    assert result.provenance["revenue_breakdown"]["source"] == "ths"


def test_ths_hk_unsupported() -> None:
    provider = ThsF10Provider()
    with pytest.raises(ProviderError):
        provider.fetch_profile("02513", market="HK")
    with pytest.raises(ProviderError):
        provider.fetch_revenue("02513", market="HK")


def test_fetch_profile_rejects_unknown_page() -> None:
    with pytest.raises(ProviderError):
        ThsF10Provider().fetch_profile("600519", pages=("not_a_page",))


def test_registry_includes_ths() -> None:
    reset_registry()
    providers = list_providers()
    assert "ths" in providers
    provider = providers["ths"]
    assert isinstance(provider, ThsF10Provider)
    assert provider.capabilities.revenue is True
    assert provider.capabilities.hk_supported is False
    assert any(page.name == "operate_revenue" for page in provider.pages)


def test_parse_company_survey_live_fixture() -> None:
    html = (
        Path(__file__).parent
        / "fixtures"
        / "f10"
        / "ths"
        / "ths_company_688825.html"
    ).read_text(encoding="utf-8")
    fields = parse_company_survey(html)
    assert fields["name"] == "长鑫科技"
    assert fields["org_name"] == "长鑫科技集团股份有限公司"
    assert fields["org_name_en"] == "Cxmt Corporation"
    assert fields["industry_sw"] == "电子 — 半导体"
    assert fields["company_website"] == "www.cxmt.com"
    assert fields["main_business"] == "DRAM产品的研发、设计、生产及销售。"
    assert "长鑫科技集团股份有限公司的主营业务为DRAM产品" in fields["company_intro"]
    # Live pages split the survey across two tables; the product table must
    # still be found even though it does not contain the 公司名称 anchor.
    assert fields["products"] == (
        "DDR4",
        "DDR5",
        "LPDDR4X",
        "LPDDR5/5X",
        "RDIMM",
        "MRDIMM",
        "UDIMM",
        "CUDIMM",
        "SODIMM",
        "CSODIMM",
        "LPCAMM",
        "DRAM晶圆",
    )


def test_parse_operate_business_live_fixture() -> None:
    html = (
        Path(__file__).parent
        / "fixtures"
        / "f10"
        / "ths"
        / "ths_operate_688825.html"
    ).read_text(encoding="utf-8")
    fields = parse_operate_business(html)
    assert fields["name"] == "长鑫科技"
    assert fields["main_business"] == "DRAM产品的研发、设计、生产及销售。"
    assert "集成电路设计、制造、加工" in fields["business_scope"]
    assert "LPDDR5/5X" in fields["products"]
    assert "5X" not in fields["products"]


def test_split_products_keeps_slash_in_names() -> None:
    assert _split_products("LPDDR5/5X、DDR5；UDIMM,SO-DIMM") == (
        "LPDDR5/5X",
        "DDR5",
        "UDIMM",
        "SO-DIMM",
    )
