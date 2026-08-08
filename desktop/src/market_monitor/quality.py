"""Data quality checks that prevent unsafe partitions from being packaged."""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4


BLOCKING_SEVERITIES = frozenset({"ERROR", "QUARANTINED"})


@dataclass(frozen=True)
class QualityIssue:
    category: str
    severity: str
    message: str
    detected_at: str
    partition_id: str
    issue_id: str = ""

    def to_dict(self) -> dict[str, str | int]:
        payload = asdict(self)
        payload["schema_version"] = 1
        payload["issue_id"] = self.issue_id or f"quality-{uuid4().hex}"
        return payload


@dataclass(frozen=True)
class QualityReport:
    partition_id: str
    issues: Sequence[QualityIssue]

    @property
    def blocking(self) -> bool:
        return any(issue.severity in BLOCKING_SEVERITIES for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "partition_id": self.partition_id,
            "blocking": self.blocking,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def validate_partition(
    partition_id: str,
    bars: Sequence[Mapping[str, Any]],
    data_cutoff: str,
    expected_open_times: Sequence[str] = (),
    abnormal_jump_ratio: float = 0.2,
    expected_offset: str | None = None,
) -> QualityReport:
    issues: list[QualityIssue] = []
    seen: set[tuple[str, str, str]] = set()
    previous_by_instrument: dict[str, str] = {}
    previous_close: dict[str, float] = {}
    present_open_times: set[str] = set()
    for bar in bars:
        instrument = _instrument_id(bar.get("instrument_key"))
        period = str(bar.get("period", ""))
        open_time = str(bar.get("bar_open_time", ""))
        primary_key = (instrument, period, open_time)
        if primary_key in seen:
            issues.append(_issue("DUPLICATE", "ERROR", f"Duplicate bar key {primary_key}", partition_id))
        seen.add(primary_key)
        present_open_times.add(open_time)
        if instrument in previous_by_instrument and open_time <= previous_by_instrument[instrument]:
            issues.append(_issue("TIMESTAMP", "ERROR", f"Timestamp is not increasing for {instrument}", partition_id))
        previous_by_instrument[instrument] = open_time
        if not _valid_ohlc(bar):
            issues.append(_issue("OHLC", "QUARANTINED", "OHLC bounds are invalid", partition_id))
        if not _valid_volume(bar):
            issues.append(_issue("VOLUME", "QUARANTINED", "Volume is negative", partition_id))
        close = _number(bar.get("close"))
        previous = previous_close.get(instrument)
        if previous and close > 0 and abs(close / previous - 1) > abnormal_jump_ratio:
            issues.append(_issue("OHLC", "WARNING", f"Close jump exceeds {abnormal_jump_ratio:.0%}", partition_id))
        if close > 0:
            previous_close[instrument] = close
        if str(bar.get("bar_close_time", "")) > data_cutoff:
            issues.append(_issue("SOURCE", "ERROR", "Bar exceeds declared data cutoff", partition_id))
        if expected_offset is not None and _utc_offset(str(bar.get("bar_open_time", ""))) != expected_offset:
            issues.append(
                _issue(
                    "TIMEZONE",
                    "ERROR",
                    f"Bar offset {_utc_offset(str(bar.get('bar_open_time', '')))} does not match {expected_offset}",
                    partition_id,
                )
            )
        if bar.get("is_partial"):
            issues.append(_issue("GAP", "INFO", "Partition contains a documented partial bar", partition_id))
    for missing in sorted(set(expected_open_times) - present_open_times):
        issues.append(_issue("GAP", "WARNING", f"Expected trading interval missing: {missing}", partition_id))
    return QualityReport(partition_id, issues)


def validate_cross_source(
    partition_id: str,
    primary_bars: Sequence[Mapping[str, Any]],
    reference_bars: Sequence[Mapping[str, Any]],
    *,
    close_tolerance: float = 0.005,
    volume_tolerance: float = 0.5,
) -> QualityReport:
    """Compare a primary partition against a reference source.

    This is a *comparison* only: it never mixes rows from both sources into
    the primary partition.  Any diff beyond the declared tolerance produces a
    blocking ``CROSS_SOURCE`` issue so the caller can quarantine instead of
    silently shipping mixed data.
    """

    issues: list[QualityIssue] = []
    reference_by_key = {_bar_key(bar): bar for bar in reference_bars}
    for bar in primary_bars:
        key = _bar_key(bar)
        reference = reference_by_key.get(key)
        if reference is None:
            issues.append(_issue("CROSS_SOURCE", "WARNING", f"Reference row missing for {key}", partition_id))
            continue
        primary_close = _number(bar.get("close"))
        reference_close = _number(reference.get("close"))
        if reference_close > 0 and abs(primary_close / reference_close - 1) > close_tolerance:
            issues.append(
                _issue(
                    "CROSS_SOURCE",
                    "ERROR",
                    f"Close differs beyond {close_tolerance:.2%} for {key}: {primary_close} vs {reference_close}",
                    partition_id,
                )
            )
        primary_volume = _number(bar.get("volume"))
        reference_volume = _number(reference.get("volume"))
        if reference_volume > 0 and abs(primary_volume / reference_volume - 1) > volume_tolerance:
            issues.append(
                _issue(
                    "CROSS_SOURCE",
                    "WARNING",
                    f"Volume differs beyond {volume_tolerance:.0%} for {key}",
                    partition_id,
                )
            )
    return QualityReport(partition_id, issues)


def quarantine_partition(root: Path, partition_id: str, bars: Sequence[Mapping[str, Any]], report: QualityReport) -> Path:
    """Write rejected bars outside Silver under ``quarantine/<partition_id>/``.

    The caller must already have a blocking report; this function only
    persists the evidence atomically so a later audit can inspect why the
    partition was never merged.
    """

    target = root / "quarantine" / partition_id
    target.mkdir(parents=True, exist_ok=True)
    bars_path = target / "bars.jsonl"
    report_path = target / "quality-report.json"
    if bars_path.exists() or report_path.exists():
        raise FileExistsError(f"Quarantine entry already exists: {target}")
    staging_bars = bars_path.with_suffix(f".{uuid4().hex}.jsonl")
    staging_report = report_path.with_suffix(f".{uuid4().hex}.json")
    try:
        with staging_bars.open("w", encoding="utf-8") as stream:
            for bar in bars:
                stream.write(json.dumps(bar, ensure_ascii=False) + "\n")
        staging_report.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(staging_bars, bars_path)
        os.replace(staging_report, report_path)
    finally:
        staging_bars.unlink(missing_ok=True)
        staging_report.unlink(missing_ok=True)
    return target


def _issue(category: str, severity: str, message: str, partition_id: str) -> QualityIssue:
    return QualityIssue(category, severity, message, datetime.now().astimezone().isoformat(timespec="seconds"), partition_id)


def _instrument_id(value: Any) -> str:
    if isinstance(value, Mapping):
        return ".".join(str(value.get(part, "")) for part in ("country_or_market", "exchange", "asset_type", "code"))
    return str(value)


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bar_key(bar: Mapping[str, Any]) -> tuple[str, str, str]:
    return (_instrument_id(bar.get("instrument_key")), str(bar.get("period", "")), str(bar.get("bar_open_time", "")))


def _utc_offset(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    offset = parsed.utcoffset()
    if offset is None:
        return ""
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    return f"{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _valid_ohlc(bar: Mapping[str, Any]) -> bool:
    for field in ("open", "high", "low", "close"):
        value = bar.get(field)
        if value is None or value == "" or not _finite(value) or _number(value) <= 0:
            return False
    low, high, open_price, close = (_number(bar.get(field)) for field in ("low", "high", "open", "close"))
    return low <= min(open_price, close) and high >= max(open_price, close) and low <= high


def _valid_volume(bar: Mapping[str, Any]) -> bool:
    value = bar.get("volume")
    return value is not None and value != "" and _finite(value) and _number(value) >= 0


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
