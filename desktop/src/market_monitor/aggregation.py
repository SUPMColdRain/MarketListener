"""Versioned exchange-session aggregation without crossing session boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class SessionRule:
    version: int
    sessions: tuple[tuple[time, time], ...]


SESSION_RULES = {
    "CN_STOCK": SessionRule(1, ((time(9, 30), time(11, 30)), (time(13), time(15)))),
    "HK_STOCK": SessionRule(1, ((time(9, 30), time(12),), (time(13), time(16)))),
    "CN_FUTURE": SessionRule(1, ((time(9), time(11, 30)), (time(13, 30), time(15)), (time(21), time(23)))),
}


def aggregate_bars(bars: Sequence[Mapping[str, Any]], period_minutes: int, session_rule: str) -> list[dict[str, Any]]:
    if session_rule not in SESSION_RULES:
        raise ValueError(f"Unknown session rule: {session_rule}")
    if period_minutes not in (15, 30, 60, 120, 240):
        raise ValueError("period_minutes must be one of 15, 30, 60, 120, 240")
    rule = SESSION_RULES[session_rule]
    buckets: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    boundaries: dict[tuple[str, str], datetime] = {}
    for bar in sorted(bars, key=lambda item: str(item["bar_open_time"])):
        open_time = _parse(str(bar["bar_open_time"]))
        session = _session_for(open_time, rule)
        if session is None:
            continue
        session_start, session_end = session
        elapsed_minutes = int((open_time - session_start).total_seconds() // 60)
        bucket_start = session_start + timedelta(minutes=(elapsed_minutes // period_minutes) * period_minutes)
        bucket_key = (str(bar["trading_day"]), bucket_start.isoformat())
        buckets.setdefault(bucket_key, []).append(bar)
        boundaries[bucket_key] = min(bucket_start + timedelta(minutes=period_minutes), session_end)
    return [_combine(bucket, period_minutes, boundaries[key], rule.version) for key, bucket in sorted(buckets.items())]


def _combine(bars: Sequence[Mapping[str, Any]], period_minutes: int, expected_end: datetime, rule_version: int) -> dict[str, Any]:
    first, last = bars[0], bars[-1]
    output = dict(first)
    output.update(
        {
            "period": f"{period_minutes}m" if period_minutes < 60 else f"{period_minutes // 60}h",
            "source_period": first.get("period"),
            "bar_open_time": first["bar_open_time"],
            "bar_close_time": last["bar_close_time"],
            "open": first["open"],
            "high": max(float(bar["high"]) for bar in bars),
            "low": min(float(bar["low"]) for bar in bars),
            "close": last["close"],
            "volume": sum(float(bar.get("volume", 0)) for bar in bars),
            "amount": sum(float(bar.get("amount", 0)) for bar in bars),
            "open_interest": last.get("open_interest"),
            "session_rule_version": rule_version,
            "is_partial": _parse(str(last["bar_close_time"])) < expected_end,
        }
    )
    return output


def _session_for(value: datetime, rule: SessionRule) -> tuple[datetime, datetime] | None:
    for start, end in rule.sessions:
        session_start = value.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
        session_end = value.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
        if session_start <= value < session_end:
            return session_start, session_end
    return None


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
