from datetime import date

from market_monitor.market_expansion import (
    MarketIndicator,
    build_continuous_series,
    deduplicate_etfs,
    normalize_hk_bar,
    select_main_contract,
    FuturesContract,
    EtfShare,
)


def test_hk_bar_normalization_maps_chinese_columns() -> None:
    row = {"日期": "2026-08-05", "开盘": 1.0, "收盘": 1.1, "最高": 1.2, "最低": 0.9, "成交量": 100, "成交额": 200}

    normalized = normalize_hk_bar(row)

    assert normalized["date"] == "2026-08-05"
    assert normalized["open"] == 1.0 and normalized["close"] == 1.1
    assert normalized["volume"] == 100 and normalized["amount"] == 200


def test_main_contract_selection_uses_open_interest_then_volume_then_expiry() -> None:
    contracts = [
        FuturesContract("IF2608", "CFFEX", date(2026, 8, 21), open_interest=100, volume=10),
        FuturesContract("IF2609", "CFFEX", date(2026, 9, 18), open_interest=200, volume=5),
        FuturesContract("IF2612", "CFFEX", date(2026, 12, 18), open_interest=200, volume=5),
    ]

    assert select_main_contract(contracts).symbol == "IF2609"


def test_continuous_series_marks_roll_day_and_reports_gap() -> None:
    contracts = {
        date(2026, 8, 3): [FuturesContract("IF2608", "CFFEX", date(2026, 8, 21), open_interest=100)],
        date(2026, 8, 4): [FuturesContract("IF2608", "CFFEX", date(2026, 8, 21), open_interest=100)],
        date(2026, 9, 1): [FuturesContract("IF2609", "CFFEX", date(2026, 9, 18), open_interest=200)],
    }
    closes = {
        (date(2026, 8, 3), "IF2608"): 4000.0,
        (date(2026, 8, 4), "IF2608"): 4010.0,
        (date(2026, 9, 1), "IF2609"): 4050.0,
    }

    series = build_continuous_series(contracts, closes)

    assert [bar.contract_symbol for bar in series] == ["IF2608", "IF2608", "IF2609"]
    assert series[2].is_roll_day
    assert series[2].roll_gap == 40.0


def test_etf_dedup_keeps_one_share_per_underlying_with_exchange_priority() -> None:
    shares = [
        EtfShare("510300", "SH", "沪深300"),
        EtfShare("159919", "SZ", "沪深300"),
        EtfShare("510500", "SH", "中证500"),
    ]

    deduped = deduplicate_etfs(shares)

    assert [(item.underlying, item.exchange) for item in deduped] == [("中证500", "SH"), ("沪深300", "SH")]


def test_indicator_validation_requires_definition_unit_source_and_iso_cutoff() -> None:
    valid = MarketIndicator("rise_count", "上涨家数", "当日上涨股票数量", "家", "1d", "akshare", "2026-08-05T15:00:00+08:00")
    invalid = MarketIndicator("bad", "无定义", "", "", "1d", "", "not-a-time")

    assert valid.validation_errors() == []
    assert len(invalid.validation_errors()) == 4
