"""Per-role source baking: primary/backup decisions from real probe results.

Every decision is capability-scoped.  A provider is selected for a role only
when its matching capability record is ``PASS`` with non-empty evidence;
source-wide availability is never inferred.  Missing roles produce a
``BLOCKED`` report instead of a silent fallback.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .providers.base import AssetType, Capability, CapabilityStatus, Market, ProviderOperation, ProviderRunResult


@dataclass(frozen=True)
class RoleDefinition:
    operation: ProviderOperation
    market: Market
    asset_type: AssetType
    period: str | None
    preference: tuple[str, ...]


ROLE_DEFINITIONS: dict[str, RoleDefinition] = {
    "history_primary": RoleDefinition(ProviderOperation.BARS, Market.CN, AssetType.STOCK, "1d", ("jqdata", "tushare", "akshare", "baostock")),
    "daily_check": RoleDefinition(ProviderOperation.BARS, Market.CN, AssetType.STOCK, "1d", ("tushare", "baostock", "akshare")),
    "calendar": RoleDefinition(ProviderOperation.CALENDAR, Market.CN, AssetType.GENERAL, None, ("tushare", "akshare", "baostock", "jqdata")),
    "minute": RoleDefinition(ProviderOperation.BARS, Market.CN, AssetType.STOCK, "30m", ("jqdata", "akshare", "baostock")),
    "etf_daily": RoleDefinition(ProviderOperation.BARS, Market.CN, AssetType.ETF, "1d", ("jqdata", "tushare", "akshare")),
    "index_daily": RoleDefinition(ProviderOperation.BARS, Market.CN, AssetType.INDEX, "1d", ("jqdata", "tushare", "akshare")),
    "futures_daily": RoleDefinition(ProviderOperation.BARS, Market.CN, AssetType.FUTURE, "1d", ("jqdata", "akshare")),
}


@dataclass(frozen=True)
class SourceDecision:
    role: str
    provider: str | None
    capability_id: str | None
    status: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "provider": self.provider,
            "capability_id": self.capability_id,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class BakingReport:
    generated_at: str
    decisions: tuple[SourceDecision, ...]

    @property
    def status(self) -> str:
        return "READY" if all(decision.status == "PASS" for decision in self.decisions) else "BLOCKED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "generated_at": self.generated_at,
            "status": self.status,
            "decisions": [decision.to_dict() for decision in self.decisions],
        }


def bake_sources(
    probe_results: Mapping[str, ProviderRunResult],
    *,
    role_definitions: Mapping[str, RoleDefinition] | None = None,
    now: datetime | None = None,
) -> BakingReport:
    """Decide one source per role from real capability records."""

    roles = role_definitions or ROLE_DEFINITIONS
    decisions: list[SourceDecision] = []
    for role, definition in roles.items():
        selected: SourceDecision | None = None
        for provider_name in definition.preference:
            result = probe_results.get(provider_name)
            if result is None:
                continue
            for capability in result.capabilities:
                if not _matches(capability, definition):
                    continue
                if capability.status is CapabilityStatus.PASS and _has_rows(capability):
                    selected = SourceDecision(
                        role, provider_name, capability.registration.id, "PASS",
                        f"real capability PASS with {capability.row_count} rows",
                    )
                    break
            if selected is not None:
                break
        if selected is None:
            selected = SourceDecision(
                role, None, None, "BLOCKED",
                "no preferred provider has a PASS capability with non-empty evidence for this role",
            )
        decisions.append(selected)
    return BakingReport((now or datetime.now(timezone.utc)).isoformat(timespec="seconds"), tuple(decisions))


class SourceRouter:
    """Route a role to the baked provider; unknown or unready roles are rejected."""

    def __init__(self, report: BakingReport) -> None:
        self._decisions = {decision.role: decision for decision in report.decisions}

    def source_for(self, role: str) -> str:
        decision = self._decisions.get(role)
        if decision is None:
            raise KeyError(f"unknown role: {role}")
        if decision.status != "PASS" or decision.provider is None:
            raise ValueError(f"role {role} is not baked (status={decision.status})")
        return decision.provider

    def capability_for(self, role: str) -> str:
        decision = self._decisions.get(role)
        if decision is None or decision.capability_id is None:
            raise ValueError(f"role {role} has no baked capability (status={decision.status if decision else 'unknown'})")
        return decision.capability_id


def write_baking_report(report: BakingReport, report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    machine_path = report_dir / "source-baking.json"
    human_path = report_dir / "source-baking.md"
    machine_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 来源烘焙决策",
        "",
        f"- 生成时间：{report.generated_at}",
        f"- 状态：{report.status}",
        "",
        "| 角色 | 状态 | 来源 | 能力 | 原因 |",
        "|---|---|---|---|---|",
    ]
    for decision in report.decisions:
        lines.append(
            f"| {decision.role} | {decision.status} | {decision.provider or '-'} | "
            f"{decision.capability_id or '-'} | {decision.reason} |"
        )
    human_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return machine_path, human_path


def _matches(capability: Capability, definition: RoleDefinition) -> bool:
    request = capability.registration.request
    return (
        request.operation is definition.operation
        and request.market is definition.market
        and request.asset_type is definition.asset_type
        and (definition.period is None or request.period == definition.period)
    )


def _has_rows(capability: Capability) -> bool:
    return capability.row_count is not None and capability.row_count > 0
