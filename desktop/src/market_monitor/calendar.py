"""Data-driven trading calendars with explicit trading-day semantics.

The calendar is authoritative for *whether* a market trades on a date.  A
missing or non-trading day must never produce phantom bars; callers that
aggregate bars simply receive no bars for that day.  Session details (when
present) are used for intraday aggregation and partial-tail marking.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Iterable, Mapping

from .contracts import validate_contract


@dataclass(frozen=True)
class CalendarDay:
    market: str
    calendar_date: date
    is_trading_day: bool
    session_kind: str = "FULL"
    sessions: tuple[tuple[time, time], ...] = ()
    provider: str = ""
    retrieved_at: str = ""


class TradingCalendar:
    """Lookup container for trading days per market."""

    def __init__(self, days: Iterable[CalendarDay] | Iterable[Mapping[str, object]]) -> None:
        self._days: dict[tuple[str, date], CalendarDay] = {}
        for raw in days:
            if isinstance(raw, Mapping):
                document = dict(raw)
                validate_contract("trading-calendar.schema.json", document)
                day = CalendarDay(
                    market=str(document["market"]),
                    calendar_date=date.fromisoformat(str(document["calendar_date"])),
                    is_trading_day=bool(document["is_trading_day"]),
                    session_kind=str(document.get("session_kind", "FULL")),
                    sessions=_parse_sessions(document.get("sessions", [])),
                    provider=str(document["source"].get("provider", "")),
                    retrieved_at=str(document["source"].get("retrieved_at", "")),
                )
            else:
                day = raw
            key = (day.market, day.calendar_date)
            if key in self._days:
                raise ValueError(f"Duplicate calendar entry: {key}")
            self._days[key] = day

    def day(self, market: str, on_date: date) -> CalendarDay | None:
        return self._days.get((market, on_date))

    def is_trading_day(self, market: str, on_date: date) -> bool:
        day = self.day(market, on_date)
        return bool(day and day.is_trading_day)

    def next_trading_day(self, market: str, on_date: date) -> date | None:
        candidates = [
            day.calendar_date
            for (candidate_market, calendar_date), day in self._days.items()
            if candidate_market == market and day.is_trading_day and calendar_date > on_date
        ]
        return min(candidates) if candidates else None

    def previous_trading_day(self, market: str, on_date: date) -> date | None:
        candidates = [
            day.calendar_date
            for (candidate_market, calendar_date), day in self._days.items()
            if candidate_market == market and day.is_trading_day and calendar_date < on_date
        ]
        return max(candidates) if candidates else None

    def trading_days_between(self, market: str, start: date, end: date) -> list[date]:
        return sorted(
            calendar_date
            for (candidate_market, calendar_date), day in self._days.items()
            if candidate_market == market and day.is_trading_day and start <= calendar_date <= end
        )


def _parse_sessions(raw: object) -> tuple[tuple[time, time], ...]:
    if not isinstance(raw, list):
        return ()
    sessions: list[tuple[time, time]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("session entries must be objects")
        start = time.fromisoformat(str(item["start"]))
        end = time.fromisoformat(str(item["end"]))
        if start >= end:
            raise ValueError(f"session start must be before end: {item}")
        sessions.append((start, end))
    return tuple(sorted(sessions))
