from datetime import datetime, timezone

import pytest

from market_monitor.baking import ROLE_DEFINITIONS, SourceRouter, bake_sources, write_baking_report
from market_monitor.providers.base import (
    AssetType,
    Capability,
    CapabilityRegistration,
    CapabilityStatus,
    Market,
    ProviderOperation,
    ProviderRequest,
    ProviderRunResult,
    SourceDescription,
)


def capability(provider: str, operation: ProviderOperation, asset_type: AssetType = AssetType.GENERAL, period: str | None = None, rows: int | None = 1) -> Capability:
    capability_id = f"{provider}-{operation.value}"
    return Capability(
        name=capability_id,
        status=CapabilityStatus.PASS,
        registration=CapabilityRegistration(
            id=capability_id,
            description="test",
            request=ProviderRequest(operation=operation, market=Market.CN, asset_type=asset_type, period=period),
        ),
        probed_at="2026-08-06T00:00:00Z",
        row_count=rows,
    )


def result(provider: str, *capabilities: Capability) -> ProviderRunResult:
    return ProviderRunResult(
        run_id=f"run-{provider}",
        source=SourceDescription(id=provider, display_name=provider, description="test source"),
        started_at="2026-08-06T00:00:00Z",
        completed_at="2026-08-06T00:01:00Z",
        capabilities=capabilities,
    )


def test_baking_picks_first_preferred_passing_capability() -> None:
    report = bake_sources(
        {
            "jqdata": result(
                "jqdata",
                capability("jqdata", ProviderOperation.BARS, AssetType.STOCK, "1d", rows=100),
            ),
            "tushare": result(
                "tushare",
                capability("tushare", ProviderOperation.BARS, AssetType.STOCK, "1d", rows=50),
            ),
        }
    )

    decision = next(item for item in report.decisions if item.role == "history_primary")
    assert decision.status == "PASS"
    assert decision.provider == "jqdata"
    router = SourceRouter(report)
    assert router.source_for("history_primary") == "jqdata"


def test_baking_falls_back_when_primary_lacks_rows_or_failed() -> None:
    report = bake_sources(
        {
            "jqdata": result(
                "jqdata",
                capability("jqdata", ProviderOperation.BARS, AssetType.STOCK, "1d", rows=None),
            ),
            "tushare": result(
                "tushare",
                capability("tushare", ProviderOperation.BARS, AssetType.STOCK, "1d", rows=50),
            ),
        }
    )

    decision = next(item for item in report.decisions if item.role == "history_primary")
    assert decision.provider == "tushare"


def test_baking_blocks_role_without_any_passing_capability() -> None:
    report = bake_sources(
        {
            "jqdata": result("jqdata"),
            "tushare": result("tushare"),
            "akshare": result("akshare"),
            "baostock": result("baostock"),
        }
    )

    assert report.status == "BLOCKED"
    decision = next(item for item in report.decisions if item.role == "calendar")
    assert decision.status == "BLOCKED" and decision.provider is None
    router = SourceRouter(report)
    with pytest.raises(ValueError, match="not baked"):
        router.source_for("calendar")


def test_baking_writes_json_and_markdown(tmp_path) -> None:
    report = bake_sources({})
    machine, human = write_baking_report(report, tmp_path)

    assert machine.is_file() and human.is_file()
    assert '"status": "BLOCKED"' in machine.read_text(encoding="utf-8")
    assert "来源烘焙决策" in human.read_text(encoding="utf-8")


def test_router_rejects_unknown_role() -> None:
    router = SourceRouter(bake_sources({}))
    with pytest.raises(KeyError):
        router.source_for("not-a-role")
