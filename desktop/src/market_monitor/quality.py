"""Data quality checks that prevent unsafe partitions from being packaged."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
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
        if _number(bar.get("volume")) < 0:
            issues.append(_issue("VOLUME", "QUARANTINED", "Volume is negative", partition_id))
        close = _number(bar.get("close"))
        previous = previous_close.get(instrument)
        if previous and close > 0 and abs(close / previous - 1) > abnormal_jump_ratio:
            issues.append(_issue("OHLC", "WARNING", f"Close jump exceeds {abnormal_jump_ratio:.0%}", partition_id))
        if close > 0:
            previous_close[instrument] = close
        if str(bar.get("bar_close_time", "")) > data_cutoff:
            issues.append(_issue("SOURCE", "ERROR", "Bar exceeds declared data cutoff", partition_id))
        if bar.get("is_partial"):
            issues.append(_issue("GAP", "INFO", "Partition contains a documented partial bar", partition_id))
    for missing in sorted(set(expected_open_times) - present_open_times):
        issues.append(_issue("GAP", "WARNING", f"Expected trading interval missing: {missing}", partition_id))
    return QualityReport(partition_id, issues)


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


def _valid_ohlc(bar: Mapping[str, Any]) -> bool:
    low, high, open_price, close = (_number(bar.get(field)) for field in ("low", "high", "open", "close"))
    return low <= min(open_price, close) and high >= max(open_price, close) and low <= high
