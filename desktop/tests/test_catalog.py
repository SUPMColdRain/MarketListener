from datetime import date

import pytest

from market_monitor.catalog import Instrument, InstrumentCatalog, InstrumentKey, validate_universe_rule


def instrument(key: InstrumentKey) -> Instrument:
    return Instrument(key, key.code, "CNY", "Asia/Shanghai")


def test_cross_source_a_share_mapping_and_hk_zero_padding(tmp_path) -> None:
    catalog = InstrumentCatalog(tmp_path / "catalog.sqlite")
    a_share = InstrumentKey("CN", "SSE", "STOCK", "600519")
    hk_share = InstrumentKey("HK", "HKEX", "STOCK", "00700")
    catalog.upsert_instrument(instrument(a_share)); catalog.upsert_instrument(Instrument(hk_share, "Tencent", "HKD", "Asia/Hong_Kong"))
    catalog.add_source_mapping("joinquant", "600519.XSHG", a_share, date(2001, 1, 1))
    catalog.add_source_mapping("baostock", "sh.600519", a_share, date(2001, 1, 1))
    catalog.add_source_mapping("provider_x", "700", hk_share, date(2004, 6, 16))
    assert catalog.resolve_source_symbol("joinquant", "600519.XSHG", date.today()) == a_share
    assert catalog.resolve_source_symbol("baostock", "sh.600519", date.today()) == a_share
    assert catalog.resolve_source_symbol("provider_x", "700", date.today()) == hk_share


def test_delisting_future_rollover_and_code_reuse_resolve_by_effective_date(tmp_path) -> None:
    catalog = InstrumentCatalog(tmp_path / "catalog.sqlite")
    old = InstrumentKey("CN", "SSE", "STOCK", "600001")
    reused = InstrumentKey("CN", "SSE", "STOCK", "600001-R")
    future = InstrumentKey("CN", "CFFEX", "FUTURE", "IF2608")
    for key in (old, reused, future): catalog.upsert_instrument(instrument(key))
    catalog.add_source_mapping("source", "600001", old, date(2000, 1, 1), date(2020, 12, 31))
    catalog.add_source_mapping("source", "600001", reused, date(2021, 1, 1))
    catalog.add_source_mapping("source", "IF2608", future, date(2026, 7, 1), date(2026, 8, 21))
    assert catalog.resolve_source_symbol("source", "600001", date(2020, 12, 31)) == old
    assert catalog.resolve_source_symbol("source", "600001", date(2021, 1, 1)) == reused
    assert catalog.resolve_source_symbol("source", "IF2608", date(2026, 8, 22)) is None


def test_universe_rules_are_versioned_with_member_effective_dates(tmp_path) -> None:
    catalog = InstrumentCatalog(tmp_path / "catalog.sqlite")
    first = InstrumentKey("CN", "SSE", "STOCK", "600519")
    second = InstrumentKey("CN", "SZSE", "STOCK", "000001")
    catalog.upsert_instrument(instrument(first)); catalog.upsert_instrument(instrument(second))
    catalog.save_universe_rule("cn-core", 1, date(2026, 1, 1), {"market": "CN", "kind": "core"})
    catalog.add_universe_member("cn-core", 1, first, date(2026, 1, 1))
    catalog.add_universe_member("cn-core", 1, second, date(2026, 7, 1))
    assert catalog.resolve_universe("cn-core", 1, date(2026, 6, 30)) == [first]
    assert catalog.resolve_universe("cn-core", 1, date(2026, 7, 1)) == [first, second]


def test_listing_date_membership_is_point_in_time_without_future_leakage(tmp_path) -> None:
    catalog = InstrumentCatalog(tmp_path / "catalog.sqlite")
    listed_then_delisted = InstrumentKey("CN", "SSE", "STOCK", "600001")
    future_listing = InstrumentKey("CN", "SSE", "STOCK", "600999")
    catalog.upsert_instrument(
        Instrument(listed_then_delisted, "Old", "CNY", "Asia/Shanghai", date(2000, 1, 1), date(2020, 12, 31))
    )
    catalog.upsert_instrument(
        Instrument(future_listing, "Future", "CNY", "Asia/Shanghai", date(2026, 9, 1))
    )

    inserted = catalog.add_membership_from_listing_dates("cn-a-share", 1)

    assert inserted == 2
    assert catalog.resolve_universe("cn-a-share", 1, date(2020, 12, 31)) == [listed_then_delisted]
    assert catalog.resolve_universe("cn-a-share", 1, date(2021, 1, 1)) == []
    assert catalog.resolve_universe("cn-a-share", 1, date(2026, 8, 31)) == []
    assert catalog.resolve_universe("cn-a-share", 1, date(2026, 9, 1)) == [future_listing]
    assert catalog.add_membership_from_listing_dates("cn-a-share", 1) == 0


def test_catalog_migrates_existing_database_with_listing_columns(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(
        """CREATE TABLE instruments (
            instrument_id TEXT PRIMARY KEY, country_or_market TEXT NOT NULL, exchange TEXT NOT NULL,
            asset_type TEXT NOT NULL, code TEXT NOT NULL, display_name TEXT NOT NULL, currency TEXT NOT NULL, timezone TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_mappings (
            provider TEXT NOT NULL, source_symbol TEXT NOT NULL, instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
            effective_from TEXT NOT NULL, effective_to TEXT, PRIMARY KEY (provider, source_symbol, effective_from)
        );
        CREATE TABLE IF NOT EXISTS universe_rules (
            scope_id TEXT NOT NULL, version INTEGER NOT NULL, effective_at TEXT NOT NULL, definition_json TEXT NOT NULL,
            PRIMARY KEY (scope_id, version)
        );
        CREATE TABLE IF NOT EXISTS universe_members (
            scope_id TEXT NOT NULL, version INTEGER NOT NULL, instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
            effective_from TEXT NOT NULL, effective_to TEXT, PRIMARY KEY (scope_id, version, instrument_id, effective_from)
        );"""
    )
    connection.execute(
        """INSERT INTO instruments (instrument_id, country_or_market, exchange, asset_type, code, display_name, currency, timezone)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("CN.SSE.STOCK.600519", "CN", "SSE", "STOCK", "600519", "Moutai", "CNY", "Asia/Shanghai"),
    )
    connection.commit()
    connection.close()

    catalog = InstrumentCatalog(path)
    key = InstrumentKey("CN", "SSE", "STOCK", "600519")
    catalog.upsert_instrument(Instrument(key, "Moutai", "CNY", "Asia/Shanghai", date(2001, 8, 27)))
    catalog.add_membership_from_listing_dates("cn-a-share", 1)

    assert catalog.resolve_universe("cn-a-share", 1, date(2001, 8, 27)) == [key]
    assert catalog.resolve_universe("cn-a-share", 1, date(2001, 8, 26)) == []


def test_universe_rule_validation_rejects_unknown_keys_and_bad_values() -> None:
    validate_universe_rule({"market": "CN", "kind": "a_share", "exchanges": ["SSE", "SZSE"], "asset_types": ["STOCK"]})
    with pytest.raises(ValueError, match="Unknown universe rule keys"):
        validate_universe_rule({"market": "CN", "kind": "a_share", "typo_exchanges": ["SSE"]})
    with pytest.raises(ValueError, match="market"):
        validate_universe_rule({"market": "US", "kind": "a_share"})
    with pytest.raises(ValueError, match="exchanges"):
        validate_universe_rule({"market": "CN", "kind": "a_share", "exchanges": "SSE"})
