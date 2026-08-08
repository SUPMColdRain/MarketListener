from datetime import date, time

import pytest

from market_monitor.calendar import CalendarDay, TradingCalendar
from market_monitor.contracts import ContractValidationError


def day(market: str, on_date: date, trading: bool) -> CalendarDay:
    return CalendarDay(market=market, calendar_date=on_date, is_trading_day=trading)


def test_trading_days_and_missing_days_are_explicit() -> None:
    calendar = TradingCalendar(
        [
            day("CN_STOCK", date(2026, 8, 3), True),
            day("CN_STOCK", date(2026, 8, 4), False),
            day("CN_STOCK", date(2026, 8, 5), True),
        ]
    )

    assert calendar.is_trading_day("CN_STOCK", date(2026, 8, 3))
    assert not calendar.is_trading_day("CN_STOCK", date(2026, 8, 4))
    assert not calendar.is_trading_day("CN_STOCK", date(2026, 8, 6))  # missing -> no phantom bar
    assert calendar.next_trading_day("CN_STOCK", date(2026, 8, 3)) == date(2026, 8, 5)
    assert calendar.previous_trading_day("CN_STOCK", date(2026, 8, 5)) == date(2026, 8, 3)
    assert calendar.trading_days_between("CN_STOCK", date(2026, 8, 1), date(2026, 8, 6)) == [
        date(2026, 8, 3),
        date(2026, 8, 5),
    ]


def test_calendar_is_market_scoped() -> None:
    calendar = TradingCalendar(
        [
            day("CN_STOCK", date(2026, 8, 4), False),
            day("CN_FUTURE", date(2026, 8, 4), True),
        ]
    )

    assert not calendar.is_trading_day("CN_STOCK", date(2026, 8, 4))
    assert calendar.is_trading_day("CN_FUTURE", date(2026, 8, 4))


def test_duplicate_calendar_entries_are_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        TradingCalendar(
            [
                day("CN_STOCK", date(2026, 8, 3), True),
                day("CN_STOCK", date(2026, 8, 3), False),
            ]
        )


def test_mapping_entries_validate_against_the_shared_schema(tmp_path) -> None:
    document = {
        "schema_version": 1,
        "market": "CN_STOCK",
        "calendar_date": "2026-08-03",
        "is_trading_day": True,
        "sessions": [{"start": "09:30", "end": "11:30"}],
        "source": {"provider": "test", "retrieved_at": "2026-08-05T09:00:00+08:00"},
    }
    calendar = TradingCalendar([document])

    assert calendar.day("CN_STOCK", date(2026, 8, 3)).sessions == ((time(9, 30), time(11, 30)),)


def test_invalid_mapping_entries_are_rejected() -> None:
    with pytest.raises(ContractValidationError):
        TradingCalendar(
            [
                {
                    "schema_version": 1,
                    "market": "CN_STOCK",
                    "calendar_date": "not-a-date",
                    "is_trading_day": True,
                    "source": {"provider": "test", "retrieved_at": "2026-08-05T09:00:00+08:00"},
                }
            ]
        )
