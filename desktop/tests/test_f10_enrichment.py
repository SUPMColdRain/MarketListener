"""Unit tests for the multi-source F10 enrichment orchestrator (no network)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from market_monitor.industry_graph.f10 import enrichment
from market_monitor.industry_graph.f10.enrichment import (
    already_enriched,
    enrich_batch,
    enrich_one,
    load_revenue_rows,
    merge_revenue_rows,
)
from market_monitor.industry_graph.f10.providers import (
    F10Provider,
    ProviderCapabilities,
    ProviderError,
    ProviderPage,
    ProviderResult,
)


class FakeProvider(F10Provider):
    """Deterministic provider used by the enrichment tests."""

    name = "fake"
    capabilities = ProviderCapabilities(
        profile=True,
        company=True,
        business=True,
        revenue=True,
        hk_supported=True,
    )

    def __init__(
        self,
        *,
        fields: Mapping[str, Any] | None = None,
        revenue: Sequence[Mapping[str, Any]] | None = None,
        fail: bool = False,
    ) -> None:
        self._fields = dict(fields or {})
        self._revenue = list(revenue or [])
        self._fail = fail

    @property
    def pages(self) -> tuple[ProviderPage, ...]:
        return (
            ProviderPage(
                name="profile",
                fields=(
                    "company_position",
                    "company_highlight",
                    "main_business",
                    "industry_tdx",
                    "total_shares",
                    "float_shares",
                    "products",
                ),
            ),
            ProviderPage(name="revenue", fields=("revenue_breakdown",)),
        )

    def fetch_profile(
        self,
        code: str,
        *,
        market: str = "CN",
        pages: Sequence[str] | None = None,
    ) -> ProviderResult:
        if self._fail:
            raise ProviderError("fake provider unavailable")
        requested = {page for page in (pages or ("profile",))}
        if "profile" not in requested:
            raise ProviderError("fake profile only has page profile")
        return ProviderResult(
            provider=self.name,
            page="profile",
            market=market.upper(),
            code=code,
            fetched_at="2026-08-11T00:00:00Z",
            fields=dict(self._fields),
            provenance={
                key: {"source": self.name, "sourcePage": "profile", "fetchedAt": "2026-08-11T00:00:00Z"}
                for key in self._fields
            },
        )

    def fetch_revenue(self, code: str, *, market: str = "CN") -> ProviderResult:
        if self._fail:
            raise ProviderError("fake provider unavailable")
        return ProviderResult(
            provider=self.name,
            page="revenue",
            market=market.upper(),
            code=code,
            fetched_at="2026-08-11T00:00:00Z",
            fields={},
            revenue_breakdown=tuple(self._revenue),
            provenance={
                "revenue_breakdown": {
                    "source": self.name,
                    "sourcePage": "revenue",
                    "fetchedAt": "2026-08-11T00:00:00Z",
                }
            },
        )


class FakeTencentProvider(F10Provider):
    """Tencent-shaped provider that never touches the network."""

    name = "tencent"
    capabilities = ProviderCapabilities(
        profile=True,
        company=False,
        business=False,
        revenue=False,
        hk_supported=True,
    )

    def __init__(self, quotes: Mapping[str, Mapping[str, Any]]) -> None:
        self.quotes = {code: dict(fields) for code, fields in quotes.items()}
        self.profile_calls = 0
        self.batch_calls = 0

    @property
    def pages(self) -> tuple[ProviderPage, ...]:
        return (
            ProviderPage(
                name="bulk_quote",
                fields=("name", "total_market_cap", "float_market_cap", "price"),
                url_pattern="https://qt.gtimg.cn/q=",
                market="*",
            ),
        )

    def fetch_quotes(self, codes: Sequence[str], *, market: str = "CN") -> dict[str, dict[str, Any]]:
        self.batch_calls += 1
        return {code: dict(self.quotes.get(code, {})) for code in codes}

    def fetch_profile(
        self,
        code: str,
        *,
        market: str = "CN",
        pages: Sequence[str] | None = None,
    ) -> ProviderResult:
        self.profile_calls += 1
        raise ProviderError("network call must not happen when quote cache is used")


def _write_details(root: Path, market: str, *records: Mapping[str, Any]) -> Path:
    directory = root / "f10" / market.lower()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "details_20260811.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(dict(record), ensure_ascii=False) + "\n")
    return path


def _write_quotes(root: Path, market: str, *rows: Mapping[str, Any]) -> Path:
    directory = root / "f10" / market.lower()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "quotes_20260811.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"fetched_at": "2026-08-11T00:00:00Z", "rows": list(rows)}, ensure_ascii=False) + "\n")
    return path


def _write_revenue(root: Path, market: str, code: str, rows: Sequence[Mapping[str, Any]]) -> Path:
    directory = root / "f10" / market.lower()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "revenue_20260811.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps({"code": code, "revenue_breakdown": list(rows), "fetched_at": "2026-08-11T00:00:00Z"}, ensure_ascii=False)
            + "\n"
        )
    return path


def _base_record(code: str = "688825") -> dict[str, Any]:
    return {
        "code": code,
        "market": "CN",
        "name": "Example Co",
        "org_name": "Example Co Ltd",
        "industry_em": "Semiconductors",
        "industry_csrc": "Manufacturing",
        "org_profile": "A real company profile.",
        "business_scope": "Design and sales.",
        "quote": {
            "total_market_cap_yi": 100.0,
            "float_market_cap_yi": 80.0,
            "quote_time": "2026-08-09 10:00:00",
        },
    }


def _base_record_without_quote(code: str = "688825") -> dict[str, Any]:
    record = _base_record(code)
    record.pop("name", None)
    record.pop("quote", None)
    return record


def _latest_record(root: Path, market: str, code: str) -> dict[str, Any]:
    import market_monitor.f10 as f10_service

    records = f10_service._load_existing_records(root, market)
    return records.get(code) or {}


def test_enrich_one_fills_missing_and_writes_marker(tmp_path: Path) -> None:
    root = tmp_path / "data"
    _write_details(root, "CN", _base_record())
    provider = FakeProvider(
        fields={
            "company_position": "中国第一",
            "company_highlight": "行业领先",
            "main_business": "存储芯片",
            "industry_tdx": "半导体",
            "total_shares": 66_881_000_000.0,
            "float_shares": 50_000_000_000.0,
            "products": ["LPDDR5", "DRAM"],
        },
        revenue=[
            {
                "item": "DRAM",
                "income": 40_703_545_008.2,
                "ratio": 0.658641,
                "revenue_share_pct": 65.8641,
                "period": "2025-12-31",
                "classification": "product",
                "source": "fake",
            }
        ],
    )
    summary = enrich_one(
        root,
        market="CN",
        code="688825",
        providers={"fake": provider},
    )
    assert summary["status"] == "PASS"
    assert "company_position" in summary["filledFields"]
    assert "products" in summary["filledFields"]
    record = _latest_record(root, "CN", "688825")
    assert record["company_position"] == "中国第一"
    assert record["company_highlight"] == "行业领先"
    assert record["main_business"] == "存储芯片"
    assert record["products"] == ["LPDDR5", "DRAM"]
    assert record["provenance"]["company_position"]["source"] == "fake"
    assert already_enriched(record)
    revenue = load_revenue_rows(root, "CN", "688825")
    assert revenue and revenue[0]["item"] == "DRAM"
    assert revenue[0]["income"] == 40_703_545_008.2


def test_enrich_one_skips_already_marked_record(tmp_path: Path) -> None:
    root = tmp_path / "data"
    base = _base_record()
    base["_enrichment"] = {"version": enrichment.ENRICHMENT_VERSION, "enrichedAt": "2026-08-11T00:00:00Z"}
    _write_details(root, "CN", base)
    provider = FakeProvider(fields={"company_position": "新值"})
    summary = enrich_one(root, market="CN", code="688825", providers={"fake": provider})
    assert summary["status"] == "SKIPPED"
    record = _latest_record(root, "CN", "688825")
    assert record.get("company_position") is None


def test_enrich_one_skips_superseded_code_without_provider_request(tmp_path: Path) -> None:
    root = tmp_path / "data"
    record = _base_record("02997")
    record["market"] = "HK"
    _write_details(root, "HK", record)
    calls: list[str] = []

    class CountingProvider(FakeProvider):
        def fetch_profile(
            self,
            code: str,
            *,
            market: str = "CN",
            pages: Sequence[str] | None = None,
        ) -> ProviderResult:
            calls.append(code)
            return super().fetch_profile(code, market=market, pages=pages)

    summary = enrich_one(
        root,
        market="HK",
        code="02997",
        providers={"fake": CountingProvider()},
        force=True,
    )
    assert summary["status"] == "SKIPPED"
    assert summary["reason"] == "superseded_by_01651"
    assert summary["canonicalCode"] == "01651"
    assert calls == []


def test_build_quote_index_prefers_latest_file(tmp_path: Path) -> None:
    root = tmp_path / "data"
    directory = root / "f10" / "cn"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "quotes_20260810.jsonl").write_text(
        json.dumps({"fetched_at": "2026-08-10T00:00:00Z", "rows": [{"code": "688825", "price": 10.0}]}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    (directory / "quotes_20260811.jsonl").write_text(
        json.dumps(
            {
                "fetched_at": "2026-08-11T00:00:00Z",
                "rows": [{"code": "688825", "price": 11.0}, {"code": "000001", "price": 5.0}],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    index = enrichment._build_quote_index(root, "CN")
    assert index["688825"]["price"] == 11.0
    assert index["000001"]["price"] == 5.0


def test_build_revenue_index_collects_rows(tmp_path: Path) -> None:
    root = tmp_path / "data"
    directory = root / "f10" / "cn"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "revenue_20260811.jsonl").write_text(
        json.dumps(
            {"code": "688825", "revenue_breakdown": [{"item": "DRAM", "income": 100.0}], "fetched_at": "2026-08-11T00:00:00Z"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    index = enrichment._build_revenue_index(root, "CN")
    assert [row["item"] for row in index["688825"]] == ["DRAM"]


def test_enrich_one_uses_quote_cache_without_network(tmp_path: Path) -> None:
    root = tmp_path / "data"
    _write_details(root, "CN", _base_record_without_quote())
    fields = {
        "name": "Example Co",
        "total_market_cap": {
            "value": 100_000_000_000.0,
            "currency": "CNY",
            "asOf": "2026-08-11 10:00:00",
            "source": "tencent_quote",
            "derived": False,
        },
        "float_market_cap": {
            "value": 80_000_000_000.0,
            "currency": "CNY",
            "asOf": "2026-08-11 10:00:00",
            "source": "tencent_quote",
            "derived": False,
        },
        "price": 1520.21,
    }
    provider = FakeTencentProvider({"688825": fields})
    summary = enrich_one(
        root,
        market="CN",
        code="688825",
        providers={"tencent": provider},
        quote_cache={"688825": (fields, "2026-08-11T10:00:00Z")},
    )
    assert summary["status"] == "PASS"
    assert provider.profile_calls == 0
    record = _latest_record(root, "CN", "688825")
    assert record["name"] == "Example Co"
    assert record["total_market_cap"]["value"] == 100_000_000_000.0
    assert record["total_market_cap"]["source"] == "tencent_quote"


def test_enrich_one_uses_local_quote_index_and_revenue_index(tmp_path: Path) -> None:
    root = tmp_path / "data"
    _write_details(root, "CN", _base_record_without_quote())
    _write_quotes(root, "CN", {"code": "688825", "price": 1520.21, "quote_time": "2026-08-11 10:00:00"})
    _write_revenue(root, "CN", "688825", [{"item": "DRAM", "income": 100.0, "period": "2025-12-31"}])
    provider = FakeProvider(fields={"company_position": "中国第一"})
    summary = enrich_one(
        root,
        market="CN",
        code="688825",
        providers={"fake": provider},
        quote_index=enrichment._build_quote_index(root, "CN"),
        revenue_index=enrichment._build_revenue_index(root, "CN"),
    )
    assert summary["status"] == "PASS"
    record = _latest_record(root, "CN", "688825")
    assert record["quote"]["price"] == 1520.21
    assert record["company_position"] == "中国第一"
    revenue = load_revenue_rows(root, "CN", "688825")
    assert revenue and revenue[0]["item"] == "DRAM"


def test_enrich_batch_prefetches_tencent_quotes_once(tmp_path: Path) -> None:
    root = tmp_path / "data"
    codes = ["688825", "000001"]
    _write_details(root, "CN", *(_base_record_without_quote(code) for code in codes))
    provider = FakeTencentProvider(
        {
            code: {
                "name": f"Co {code}",
                "total_market_cap": {
                    "value": 10_000_000_000.0,
                    "currency": "CNY",
                    "asOf": "2026-08-11 10:00:00",
                    "source": "tencent_quote",
                    "derived": False,
                },
                "float_market_cap": {
                    "value": 8_000_000_000.0,
                    "currency": "CNY",
                    "asOf": "2026-08-11 10:00:00",
                    "source": "tencent_quote",
                    "derived": False,
                },
                "price": 100.0,
            }
            for code in codes
        }
    )
    summary = enrich_batch(
        root,
        market="CN",
        codes=codes,
        providers={"tencent": provider},
        checkpoint_every=1,
        workers=2,
    )
    assert summary["status"] == "PASS"
    assert summary["passed"] == 2
    assert provider.batch_calls == 1
    assert provider.profile_calls == 0


def test_enrich_one_failed_when_all_providers_fail(tmp_path: Path) -> None:
    root = tmp_path / "data"
    path = _write_details(root, "CN", _base_record())
    provider = FakeProvider(fail=True)
    summary = enrich_one(root, market="CN", code="688825", providers={"fake": provider})
    assert summary["status"] == "FAILED"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = _latest_record(root, "CN", "688825")
    assert not already_enriched(record)


def test_enrich_one_passes_when_no_provider_can_fill_remaining_fields(tmp_path: Path) -> None:
    """Missing fields no registered source can fill are not a failure."""
    root = tmp_path / "data"
    path = _write_details(root, "CN", _base_record())
    summary = enrich_one(root, market="CN", code="688825", providers={})
    assert summary["status"] == "PASS"
    assert summary["remainingFields"]
    record = _latest_record(root, "CN", "688825")
    assert already_enriched(record)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_enrich_one_preserves_existing_values(tmp_path: Path) -> None:
    root = tmp_path / "data"
    base = _base_record()
    base["company_position"] = "已有地位"
    _write_details(root, "CN", base)
    provider = FakeProvider(fields={"company_position": "Provider 新值", "company_highlight": "亮点"})
    enrich_one(root, market="CN", code="688825", providers={"fake": provider})
    record = _latest_record(root, "CN", "688825")
    assert record["company_position"] == "已有地位"
    assert record["company_highlight"] == "亮点"


def test_enrich_batch_checkpoints_and_exports(tmp_path: Path) -> None:
    root = tmp_path / "data"
    _write_details(root, "CN", _base_record("688825"), _base_record("000001"))
    provider = FakeProvider(
        fields={
            "company_position": "中国第一",
            "main_business": "存储芯片",
            "industry_tdx": "半导体",
            "total_shares": 66_881_000_000.0,
            "float_shares": 50_000_000_000.0,
            "products": ["DRAM"],
        }
    )
    summary = enrich_batch(
        root,
        market="CN",
        codes=["688825", "000001"],
        providers={"fake": provider},
        checkpoint_every=1,
    )
    assert summary["status"] == "PASS"
    assert summary["passed"] == 2
    state = json.loads((root / "f10" / "cn" / "enrichment_state.json").read_text(encoding="utf-8"))
    assert state["passed"] == 2
    exported = (root / "industry" / "f10" / "cn_f10.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(exported) == 2
    first = json.loads(exported[0])
    assert first["company_position"] == "中国第一"
    assert first["industry_tdx"] == "半导体"


def test_enrich_batch_counts_failed_summaries(tmp_path: Path) -> None:
    root = tmp_path / "data"
    _write_details(root, "CN", _base_record("688825"), _base_record("000001"))
    provider = FakeProvider(fail=True)
    summary = enrich_batch(
        root,
        market="CN",
        codes=["688825", "000001"],
        providers={"fake": provider},
        checkpoint_every=1,
    )
    assert summary["status"] == "FAILED"
    assert summary["failed"] == 2
    assert summary["passed"] == 0
    assert {item.get("code") for item in summary["errors"]} == {"688825", "000001"}
    assert all(item.get("reason") for item in summary["errors"])
    state = json.loads((root / "f10" / "cn" / "enrichment_state.json").read_text(encoding="utf-8"))
    assert state["failed"] == 2


def test_enrich_batch_persists_run_summary_log(tmp_path: Path) -> None:
    root = tmp_path / "data"
    _write_details(root, "CN", _base_record("688825"), _base_record("000001"))
    summary = enrich_batch(
        root,
        market="CN",
        codes=["688825", "000001"],
        providers={"fake": FakeProvider(fields={"company_position": "龙头"})},
        checkpoint_every=1,
    )
    assert summary["status"] == "PASS"
    assert summary["passed"] == 2
    runs_path = root / "f10" / "cn" / "enrichment_runs.jsonl"
    lines = [
        json.loads(line)
        for line in runs_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["requested"] == 2
    assert lines[0]["passed"] == 2
    assert lines[0]["status"] == "PASS"
    assert lines[0]["supersededCodes"] == {}


def test_enrich_batch_counts_superseded_code_as_skipped(tmp_path: Path) -> None:
    root = tmp_path / "data"
    hk_old = _base_record("02997")
    hk_old["market"] = "HK"
    hk_new = _base_record("01651")
    hk_new["market"] = "HK"
    _write_details(root, "HK", hk_old, hk_new)
    summary = enrich_batch(
        root,
        market="HK",
        codes=["02997", "01651"],
        providers={"fake": FakeProvider(fields={"company_position": "龙头"})},
        checkpoint_every=1,
    )
    assert summary["failed"] == 0
    assert summary["passed"] == 1
    assert summary["skipped"] == 1
    assert summary["status"] == "PASS"
    assert summary["supersededCodes"] == {"02997": "01651"}
    state = json.loads((root / "f10" / "hk" / "enrichment_state.json").read_text(encoding="utf-8"))
    assert state["failed"] == 0
    assert state["skipped"] == 1
    assert state["supersededCodes"] == {"02997": "01651"}


def test_enrich_batch_respects_global_lock(tmp_path: Path) -> None:
    root = tmp_path / "data"
    _write_details(root, "CN", _base_record("688825"))
    lock_dir = root / "f10"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / "enrichment.lock"
    lock_file.write_text(str(os.getpid()), encoding="utf-8")
    try:
        summary = enrich_batch(
            root,
            market="CN",
            codes=["688825"],
            providers={"fake": FakeProvider(fields={"company_position": "中国第一"})},
        )
        assert summary["status"] == "SKIPPED"
        assert summary["requested"] == 0
        assert summary["errors"][0]["code"] == "__lock__"
    finally:
        enrichment._release_global_enrichment_lock(root)


def test_enrich_batch_recycles_stale_global_lock(tmp_path: Path) -> None:
    root = tmp_path / "data"
    _write_details(root, "CN", _base_record("688825"))
    lock_dir = root / "f10"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / "enrichment.lock"
    lock_file.write_text("99999999", encoding="utf-8")
    summary = enrich_batch(
        root,
        market="CN",
        codes=[],
        providers={"fake": FakeProvider()},
    )
    assert summary["status"] == "PASS"
    assert not lock_file.exists()


def test_enrich_batch_workers_process_all_codes(tmp_path: Path) -> None:
    root = tmp_path / "data"
    codes = ["000001", "000002", "000003", "000004", "000005", "000006"]
    _write_details(root, "CN", *(_base_record(code) for code in codes))
    provider = FakeProvider(
        fields={
            "company_position": "龙头",
            "main_business": "主营",
            "industry_tdx": "行业",
            "total_shares": 66_881_000_000.0,
            "float_shares": 50_000_000_000.0,
            "products": ["DRAM"],
        }
    )
    summary = enrich_batch(
        root,
        market="CN",
        codes=codes,
        providers={"fake": provider},
        checkpoint_every=2,
        workers=3,
    )
    assert summary["status"] == "PASS"
    assert summary["passed"] == len(codes)
    assert summary["failed"] == 0
    state = json.loads((root / "f10" / "cn" / "enrichment_state.json").read_text(encoding="utf-8"))
    assert state["processed"] == len(codes)
    assert state["passed"] == len(codes)
    exported = (root / "industry" / "f10" / "cn_f10.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(exported) == len(codes)


def test_merge_revenue_rows_deduplicates() -> None:
    base = [
        {
            "item": "DRAM",
            "income": 100.0,
            "period": "2025-12-31",
            "classification": "product",
            "source": "eastmoney_f10",
        }
    ]

    class Result:
        provider = "fake"
        fetched_at = "2026-08-11T00:00:00Z"
        revenue_breakdown = (
            {
                "item": "DRAM",
                "income": 100.0,
                "period": "2025-12-31",
                "classification": "product",
                "source": "eastmoney_f10",
            },
            {
                "item": "NAND",
                "income": 50.0,
                "period": "2025-12-31",
                "classification": "product",
            },
        )

    merged, added = merge_revenue_rows(base, [Result()])
    assert added == 1
    assert len(merged) == 2
    assert merged[1]["item"] == "NAND"
    assert merged[1]["source"] == "fake"


def test_enrich_one_derives_float_cap_and_migrates_revenue(tmp_path: Path) -> None:
    root = tmp_path / "data"
    base = _base_record()
    base["quote"] = {"total_market_cap_yi": 100.0, "float_market_cap_yi": None}
    _write_details(root, "CN", base)
    _write_quotes(
        root,
        "CN",
        {
            "code": "688825",
            "total_market_cap_yi": 100.0,
            "float_market_cap_yi": None,
            "price": 60.0,
            "quote_time": "2026-08-09 10:00:00",
            "quote_source": "tencent_quote",
        },
    )
    provider = FakeProvider(
        fields={
            "float_shares": 50_000_000_000.0,
        },
        revenue=[
            {
                "item": "DRAM",
                "type": "2",
                "income": 40_703_545_008.2,
                "ratio": 0.65,
                "period": "2025-12-31",
                "source": "fake",
            }
        ],
    )
    summary = enrich_one(root, market="CN", code="688825", providers={"fake": provider})
    assert summary["status"] == "PASS"
    assert summary["revenueMigrated"] == 1
    record = _latest_record(root, "CN", "688825")
    assert record["total_market_cap"] == {
        "value": 10_000_000_000.0,
        "currency": "CNY",
        "asOf": "2026-08-09 10:00:00",
        "source": "tencent_quote",
    }
    assert record["float_market_cap"]["value"] == 3_000_000_000_000.0
    assert record["float_market_cap"]["derived"] is True
    assert record["float_market_cap"]["calculationMethod"] == "price_x_float_shares"
    assert record["quote"]["quote_time"] == "2026-08-09 10:00:00"
    revenue = load_revenue_rows(root, "CN", "688825")
    assert revenue[0]["classification"] == "product"
    assert revenue[0]["revenue_share_pct"] == 65.0
    assert revenue[0]["revenue"] == 40_703_545_008.2


def test_enrich_one_persists_migrated_legacy_revenue_without_new_rows(tmp_path: Path) -> None:
    root = tmp_path / "data"
    base = {
        "code": "688825",
        "market": "CN",
        "name": "Example Co",
        "org_name": "Example Co Ltd",
        "company_position": "已有地位",
        "company_highlight": "已有亮点",
        "company_intro": "简介",
        "company_website": "https://example.com",
        "industry_csrc": "Manufacturing",
        "industry_sw": "半导体",
        "industry_tdx": "半导体",
        "industry_em": "半导体",
        "industry_hs": "半导体",
        "main_business": "存储",
        "business_scope": "经营",
        "products": ["DRAM"],
        "total_shares": 66_881_000_000.0,
        "float_shares": 50_000_000_000.0,
        "total_market_cap": {
            "value": 10_000_000_000.0,
            "currency": "CNY",
            "asOf": "2026-08-09 10:00:00",
            "source": "tencent_quote",
        },
        "float_market_cap": {
            "value": 8_000_000_000.0,
            "currency": "CNY",
            "asOf": "2026-08-09 10:00:00",
            "source": "tencent_quote",
        },
    }
    _write_details(root, "CN", base)
    _write_revenue(
        root,
        "CN",
        "688825",
        [
            {"item": "DRAM", "type": "2", "income": 100.0, "ratio": 0.8, "period": "2025-12-31"},
            {"item": "NAND", "type": "2", "income": 25.0, "ratio": 0.2, "period": "2025-12-31"},
        ],
    )
    summary = enrich_one(root, market="CN", code="688825", providers={})
    assert summary["status"] == "PASS"
    assert summary["revenueMigrated"] == 2
    revenue = load_revenue_rows(root, "CN", "688825")
    assert len(revenue) == 2
    assert revenue[0]["classification"] == "product"
    assert revenue[0]["revenue_share_pct"] == 80.0
    assert revenue[1]["item"] == "NAND"
