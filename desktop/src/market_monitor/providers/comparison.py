"""Cross-source comparison that reports differences without blending rows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from .base import FetchResult, Provider, ProviderError


@dataclass(frozen=True)
class CrossSourceReport:
    status: str
    left_provider: str
    right_provider: str
    comparison: Mapping[str, Any] | None = None
    errors: tuple[Mapping[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "status": self.status,
            "left_provider": self.left_provider,
            "right_provider": self.right_provider,
            "comparison": self.comparison,
            "errors": list(self.errors),
            "row_blending": "DISABLED",
        }
        return payload


def compare_daily_bars(left: Provider, right: Provider) -> CrossSourceReport:
    """Compare two source partitions; source rows remain separate throughout."""

    errors: list[Mapping[str, str]] = []
    left_bars = _call(left, "bars", left.fetch_bars, errors)
    right_bars = _call(right, "bars", right.fetch_bars, errors)
    left_factors = _call(left, "adjustment_factors", left.fetch_indicators, errors)
    right_factors = _call(right, "adjustment_factors", right.fetch_indicators, errors)
    if errors:
        return CrossSourceReport("BLOCKED", left.name, right.name, errors=tuple(errors))
    assert left_bars and right_bars and left_factors and right_factors

    left_by_day = _bars_by_day(left_bars)
    right_by_day = _bars_by_day(right_bars)
    overlap = sorted(set(left_by_day).intersection(right_by_day))
    close_differences = _different_values(left_by_day, right_by_day, overlap, "close")
    volume_differences = _different_values(left_by_day, right_by_day, overlap, "volume")
    return CrossSourceReport(
        "PASS",
        left.name,
        right.name,
        comparison={
            "left_coverage": _coverage(left_by_day),
            "right_coverage": _coverage(right_by_day),
            "overlap_days": len(overlap),
            "close_differences": close_differences,
            "volume_differences": volume_differences,
            "left_adjustment_factor_rows": len(left_factors.records),
            "right_adjustment_factor_rows": len(right_factors.records),
        },
    )


def write_comparison(report: CrossSourceReport, report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    machine_path = report_dir / "provider-comparison.json"
    human_path = report_dir / "provider-comparison.md"
    machine_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Cross-source comparison", "", f"Status: {report.status}", "", "Row blending: DISABLED", ""]
    if report.comparison:
        lines.append("```json")
        lines.append(json.dumps(report.comparison, ensure_ascii=False, indent=2))
        lines.extend(["```", ""])
    for error in report.errors:
        lines.append(f"- {error['provider']} {error['operation']}: {error['category']} - {error['message']}")
    human_path.write_text("\n".join(lines), encoding="utf-8")
    return machine_path, human_path


def _call(provider: Provider, operation: str, call: Any, errors: list[Mapping[str, str]]) -> FetchResult | None:
    try:
        return call()
    except ProviderError as error:
        errors.append({"provider": provider.name, "operation": operation, "category": error.category.value, "message": error.message})
    except Exception as error:
        errors.append({"provider": provider.name, "operation": operation, "category": "UNKNOWN", "message": str(error)})
    return None


def _bars_by_day(result: FetchResult) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    for row in result.records:
        day = str(row.get("date") or row.get("time") or "")[:10]
        if day:
            rows[day] = row
    return rows


def _coverage(rows: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    days = sorted(rows)
    return {"rows": len(days), "earliest": days[0] if days else None, "latest": days[-1] if days else None}


def _different_values(
    left: Mapping[str, Mapping[str, Any]],
    right: Mapping[str, Mapping[str, Any]],
    overlap: list[str],
    field: str,
) -> int:
    differences = 0
    for day in overlap:
        if _decimal(left[day].get(field)) != _decimal(right[day].get(field)):
            differences += 1
    return differences


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None
