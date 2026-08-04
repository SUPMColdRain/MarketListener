from market_monitor.quality import validate_partition


def bar(**overrides):
    value = {
        "instrument_key": {"country_or_market": "CN", "exchange": "SSE", "asset_type": "STOCK", "code": "600519"},
        "period": "15m", "bar_open_time": "2026-08-03T09:30:00+08:00", "bar_close_time": "2026-08-03T09:45:00+08:00",
        "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 10.0,
    }
    value.update(overrides)
    return value


def test_blocking_quality_issues_quarantine_a_partition():
    report = validate_partition("p", [bar(), bar(high=100.0, close=101.0), bar(volume=-1)], "2026-08-03T10:00:00+08:00")
    assert report.blocking
    assert {issue.category for issue in report.issues} >= {"DUPLICATE", "OHLC", "VOLUME"}
    assert any(issue.severity == "QUARANTINED" for issue in report.issues)


def test_timestamps_gaps_jumps_cutoff_and_partial_are_reported():
    report = validate_partition(
        "p",
        [bar(close=100.0), bar(bar_open_time="2026-08-03T09:20:00+08:00", bar_close_time="2026-08-03T10:30:00+08:00", close=130.0, is_partial=True)],
        "2026-08-03T10:00:00+08:00",
        expected_open_times=["2026-08-03T09:30:00+08:00", "2026-08-03T09:45:00+08:00"],
    )
    categories = {issue.category for issue in report.issues}
    assert {"TIMESTAMP", "GAP", "OHLC", "SOURCE"} <= categories
    assert any(issue.severity == "WARNING" for issue in report.issues)
