from datetime import date

from market_monitor.catalog import Instrument, InstrumentCatalog, InstrumentKey


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
