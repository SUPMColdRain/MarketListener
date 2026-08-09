"""Versioned exchange-session aggregation without crossing session boundaries.

支持：
- 分钟级聚合（1/5/15/30/60/120/240 分钟），严格按交易时段分桶；
- 日线 -> 周线/月线聚合（架构调整任务第三节）；
- 期货夜盘归属下一交易日（可传入交易日历，避免把 21:00+ 的 bar 算进错误交易日）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Mapping, Sequence

SUPPORTED_PERIOD_MINUTES = (1, 5, 15, 30, 60, 120, 240)
NIGHT_SESSION_START = time(21)


@dataclass(frozen=True)
class SessionRule:
    version: int
    sessions: tuple[tuple[time, time], ...]


SESSION_RULES = {
    "CN_STOCK": SessionRule(1, ((time(9, 30), time(11, 30)), (time(13), time(15)))),
    "HK_STOCK": SessionRule(1, ((time(9, 30), time(12),), (time(13), time(16)))),
    "CN_FUTURE": SessionRule(1, ((time(9), time(11, 30)), (time(13, 30), time(15)), (time(21), time(23)))),
}


def aggregate_bars(
    bars: Sequence[Mapping[str, Any]],
    period_minutes: int,
    session_rule: str,
    *,
    trading_calendar: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    if session_rule not in SESSION_RULES:
        raise ValueError(f"Unknown session rule: {session_rule}")
    if period_minutes not in SUPPORTED_PERIOD_MINUTES:
        raise ValueError(f"period_minutes must be one of {SUPPORTED_PERIOD_MINUTES}")
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
        trading_day = _trading_day_for_bar(bar, open_time, rule, trading_calendar)
        bucket_key = (trading_day, bucket_start.isoformat())
        buckets.setdefault(bucket_key, []).append(bar)
        boundaries[bucket_key] = min(bucket_start + timedelta(minutes=period_minutes), session_end)
    output: list[dict[str, Any]] = []
    for key, bucket in sorted(buckets.items()):
        combined = _combine(bucket, period_minutes, boundaries[key], rule.version)
        combined["trading_day"] = key[0]
        output.append(combined)
    return output


def aggregate_daily_bars(
    bars: Sequence[Mapping[str, Any]],
    output_period: str,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """把日线（1d）聚合为周线（1w）或月线（1mo）。

    按每个标的独立聚合：open 取首日、high/low 取极值、close 取末日、
    volume/amount 求和、open_interest 取末日。不跨标的混合。
    """

    if output_period not in ("1w", "1mo"):
        raise ValueError("output_period must be '1w' or '1mo'")
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for bar in sorted(bars, key=lambda item: (str(item.get("instrument_key", "")), str(item["bar_open_time"]))):
        trading_day = str(bar["trading_day"])
        bucket = _period_bucket(trading_day, output_period)
        instrument = _instrument_id(bar)
        groups.setdefault((instrument, bucket), []).append(bar)
    output: list[dict[str, Any]] = []
    for (instrument, bucket), group in sorted(groups.items()):
        combined = _combine_daily(group, output_period)
        combined["trading_day"] = str(group[-1]["trading_day"])
        combined["period"] = output_period
        if now is not None:
            combined["is_partial"] = _parse(str(combined["bar_close_time"])) < now
        output.append(combined)
    return output


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


def _combine_daily(bars: Sequence[Mapping[str, Any]], output_period: str) -> dict[str, Any]:
    first, last = bars[0], bars[-1]
    output = dict(first)
    output.update(
        {
            "period": output_period,
            "source_period": "1d",
            "bar_open_time": first["bar_open_time"],
            "bar_close_time": last["bar_close_time"],
            "open": first["open"],
            "high": max(float(bar["high"]) for bar in bars),
            "low": min(float(bar["low"]) for bar in bars),
            "close": last["close"],
            "volume": sum(float(bar.get("volume", 0)) for bar in bars),
            "amount": sum(float(bar.get("amount", 0)) for bar in bars),
            "open_interest": last.get("open_interest"),
            "aggregated_from": "1d",
            "aggregation_rule_version": 1,
            "is_partial": False,
        }
    )
    return output


def _trading_day_for_bar(
    bar: Mapping[str, Any],
    open_time: datetime,
    rule: SessionRule,
    trading_calendar: Sequence[str] | None,
) -> str:
    source_day = str(bar.get("trading_day", open_time.date().isoformat()))
    if rule != SESSION_RULES["CN_FUTURE"] or open_time.time() < NIGHT_SESSION_START:
        return source_day
    # 期货夜盘（21:00+）归属下一交易日。优先使用调用方提供的交易日历，
    # 否则按自然日+1（周一至周五的夜盘落在下一自然日；周五夜盘需要日历才能正确落在周一）。
    if trading_calendar:
        ordered = sorted(trading_calendar)
        try:
            index = ordered.index(source_day)
        except ValueError:
            return source_day
        candidates = ordered[index + 1:]
        return candidates[0] if candidates else source_day
    next_day = open_time.date() + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day.isoformat()


def _period_bucket(trading_day: str, output_period: str) -> str:
    value = datetime.strptime(trading_day, "%Y-%m-%d")
    if output_period == "1w":
        iso_year, iso_week, _ = value.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return f"{value.year:04d}-{value.month:02d}"


def _instrument_id(bar: Mapping[str, Any]) -> str:
    key = bar.get("instrument_key")
    if isinstance(key, Mapping):
        return ".".join(str(key.get(part, "")) for part in ("country_or_market", "exchange", "asset_type", "code"))
    return str(key if key is not None else bar.get("instrument_id", ""))


def _session_for(value: datetime, rule: SessionRule) -> tuple[datetime, datetime] | None:
    for start, end in rule.sessions:
        session_start = value.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
        session_end = value.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
        if session_start <= value < session_end:
            return session_start, session_end
    return None


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
