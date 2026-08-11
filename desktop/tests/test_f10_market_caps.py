"""Unit tests for canonical market-cap derivation (no network)."""

from __future__ import annotations

from market_monitor.industry_graph.f10.market_caps import derive_market_caps


def test_record_snapshot_wins_over_quote_scalar() -> None:
    record = {
        "market": "CN",
        "total_market_cap": {
            "value": 123_456_000_000.0,
            "currency": "CNY",
            "asOf": "2026-08-09 10:00:00",
            "source": "tdx",
        },
        "float_market_cap": {
            "value": 80_000_000_000.0,
            "currency": "CNY",
            "asOf": "2026-08-09 10:00:00",
            "source": "tdx",
        },
    }
    quote = {"total_market_cap_yi": 999.0, "float_market_cap_yi": 999.0, "quote_time": "2026-08-09 10:00:00"}
    total, float_cap, reasons = derive_market_caps(record, quote, market="CN")
    assert total == {
        "value": 123_456_000_000.0,
        "currency": "CNY",
        "asOf": "2026-08-09 10:00:00",
        "source": "tdx",
    }
    assert float_cap["value"] == 80_000_000_000.0
    assert reasons == {}


def test_legacy_quote_yi_scalar_converted_with_quote_time() -> None:
    record = {"market": "CN", "code": "600519"}
    quote = {
        "total_market_cap_yi": 16366.32,
        "float_market_cap_yi": 16366.32,
        "quote_time": "2026/08/09 10:00:00",
        "quote_source": "tencent",
    }
    total, float_cap, reasons = derive_market_caps(record, quote, market="CN")
    assert total == {
        "value": 1_636_632_000_000.0,
        "currency": "CNY",
        "asOf": "2026/08/09 10:00:00",
        "source": "tencent",
    }
    assert float_cap["value"] == 1_636_632_000_000.0
    assert reasons == {}


def test_derived_float_cap_price_times_float_shares() -> None:
    record = {
        "market": "CN",
        "float_shares": 50_000_000_000.0,
        "source": "tdx",
    }
    quote = {
        "total_market_cap_yi": 100.0,
        "price": 60.0,
        "quote_time": "20260807161436",
        "quote_source": "tencent_quote",
    }
    total, float_cap, reasons = derive_market_caps(record, quote, market="CN")
    assert total["value"] == 10_000_000_000.0
    assert float_cap["value"] == 3_000_000_000_000.0
    assert float_cap["derived"] is True
    assert float_cap["calculationMethod"] == "price_x_float_shares"
    assert float_cap["inputs"]["price"] == 60.0
    assert float_cap["inputs"]["float_shares"] == 50_000_000_000.0
    assert float_cap["inputs"]["input_sources"]["float_shares"] == "tdx"
    assert reasons == {}


def test_derived_float_cap_total_ratio_fallback() -> None:
    record = {
        "market": "CN",
        "total_shares": 100_000_000_000.0,
        "float_shares": 25_000_000_000.0,
    }
    quote = {
        "total_market_cap_yi": 100.0,
        "quote_time": "20260807161436",
        "quote_source": "tencent_quote",
    }
    total, float_cap, reasons = derive_market_caps(record, quote, market="CN")
    assert total["value"] == 10_000_000_000.0
    assert float_cap["value"] == 2_500_000_000.0
    assert float_cap["calculationMethod"] == "total_cap_x_float_ratio"
    assert float_cap["derived"] is True
    assert reasons == {}


def test_hk_never_derives_float_cap() -> None:
    record = {"market": "HK", "float_shares": 10_000_000_000.0, "total_shares": 20_000_000_000.0}
    quote = {"total_market_cap_yi": 50.0, "price": 30.0, "quote_time": "2026/08/09 10:00:00"}
    total, float_cap, reasons = derive_market_caps(record, quote, market="HK")
    assert total["currency"] == "HKD"
    assert float_cap is None
    assert reasons["float_market_cap"] == "hk_share_class_unconfirmed"


def test_missing_quote_time_blocks_derivation() -> None:
    record = {"market": "CN", "float_shares": 10_000_000_000.0, "total_shares": 20_000_000_000.0}
    quote = {"total_market_cap_yi": 50.0, "float_market_cap_yi": 40.0, "price": 30.0}
    total, float_cap, reasons = derive_market_caps(record, quote, market="CN")
    assert total is None
    assert float_cap is None
    assert reasons["float_market_cap"] == "missing_quote_time"


def test_missing_inputs_leave_float_missing() -> None:
    record = {"market": "CN"}
    quote = {"total_market_cap_yi": 50.0, "quote_time": "2026/08/09 10:00:00"}
    total, float_cap, reasons = derive_market_caps(record, quote, market="CN")
    assert total is not None
    assert float_cap is None
    assert reasons["float_market_cap"] == "missing_price_or_float_shares"


def test_non_positive_values_never_become_caps() -> None:
    record = {
        "market": "CN",
        "total_market_cap": {"value": 0, "currency": "CNY", "asOf": "2026-08-09 10:00:00", "source": "x"},
        "float_market_cap": -5.0,
        "float_shares": 0,
    }
    quote = {"total_market_cap_yi": -1.0, "float_market_cap_yi": -2.0, "price": -3.0, "quote_time": "2026-08-09 10:00:00"}
    total, float_cap, reasons = derive_market_caps(record, quote, market="CN")
    assert total is None
    assert float_cap is None
    assert "float_market_cap" in reasons


def test_record_legacy_scalar_treated_as_yi() -> None:
    record = {"market": "CN", "total_market_cap": 12.5}
    quote = {"quote_time": "2026-08-09 10:00:00"}
    total, float_cap, _reasons = derive_market_caps(record, quote, market="CN")
    assert total["value"] == 1_250_000_000.0
    assert float_cap is None
