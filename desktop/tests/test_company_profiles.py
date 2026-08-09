"""Regression coverage for the shared CompanySummary / CompanyDetail read model."""

from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from market_monitor.control_center import make_handler
from market_monitor.industry_graph.f10 import CompanyRepository


def _write_f10(data_root: Path) -> None:
    directory = data_root / "industry" / "f10"
    directory.mkdir(parents=True)
    cn = {
        "code": "600519",
        "market": "CN",
        "name": "贵州茅台",
        "total_market_cap": 16366.32,
        "float_market_cap": 16366.32,
        "industry": "食品饮料-白酒",
        "csrc_industry": "酒、饮料和精制茶制造业",
        "profile": "白酒生产和销售企业",
        "main_business": "白酒业务",
        "products": ["茅台酒"],
        "revenue_breakdown": [{"item": "茅台酒", "income": 146499906480.49, "ratio": 0.867695}],
        "source": "eastmoney_f10",
        "fetched_at": "2026-08-09T10:00:00+08:00",
        "status": "ok",
    }
    hk = {
        "code": "600519",
        "market": "HK",
        "name": "港股样本",
        "profile": "港股资料",
        "source": "eastmoney_f10",
        "fetched_at": "2026-08-09T10:00:00+08:00",
        "status": "ok",
    }
    (directory / "cn_f10.jsonl").write_text(json.dumps(cn, ensure_ascii=False) + "\n", encoding="utf-8")
    (directory / "hk_f10.jsonl").write_text(json.dumps(hk, ensure_ascii=False) + "\n", encoding="utf-8")


def test_company_repository_uses_canonical_instrument_and_money_provenance(tmp_path: Path) -> None:
    _write_f10(tmp_path)
    repository = CompanyRepository(tmp_path)

    page = repository.list_companies(sort="code")

    assert page.total == 2
    assert {item.instrument_key for item in page.items} == {"CN.SSE.STOCK.600519", "HK.HKEX.STOCK.600519"}
    detail = repository.company("CN.SSE.STOCK.600519")
    assert detail is not None
    document = detail.to_dict()
    assert document["totalMarketCap"] == {
        "value": 1_636_632_000_000.0,
        "currency": "CNY",
        "asOf": "2026-08-09T10:00:00+08:00",
        "source": "tencent_quote",
    }
    assert document["topRevenueSegment"]["name"] == "茅台酒"
    assert document["revenueSegments"][0]["amount"]["currency"] == "CNY"


def test_company_repository_filters_and_enforces_page_bounds(tmp_path: Path) -> None:
    _write_f10(tmp_path)
    repository = CompanyRepository(tmp_path)

    page = repository.list_companies(query="茅台", market="CN", page_size=1)

    assert page.total == 1
    assert page.items[0].name == "贵州茅台"
    with pytest.raises(ValueError, match="page_size"):
        repository.list_companies(page_size=501)
    with pytest.raises(ValueError, match="sort"):
        repository.list_companies(sort="sql")
    with pytest.raises(ValueError, match="market"):
        repository.list_companies(market="US")


class _Server:
    def __init__(self, data_root: Path) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data_root, quiet=True))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def test_f10_http_api_is_paginated_local_and_has_no_placeholder_values(tmp_path: Path) -> None:
    _write_f10(tmp_path)
    server = _Server(tmp_path)
    try:
        with urlopen(f"{server.base_url}/api/f10/companies?q=%E8%8C%85%E5%8F%B0&page_size=1", timeout=5) as response:
            page = json.loads(response.read().decode("utf-8"))
        assert page["total"] == 1
        assert page["items"][0]["instrumentKey"] == "CN.SSE.STOCK.600519"

        with urlopen(f"{server.base_url}/api/f10/companies/CN.SSE.STOCK.600519", timeout=5) as response:
            detail = json.loads(response.read().decode("utf-8"))
        encoded = json.dumps(detail, ensure_ascii=False)
        assert "undefined" not in encoded
        assert "Invalid Date" not in encoded
        assert "null" not in encoded

        with pytest.raises(HTTPError) as error:
            urlopen(f"{server.base_url}/api/f10/companies?sort=sql", timeout=5)
        assert error.value.code == 400
    finally:
        server.close()
