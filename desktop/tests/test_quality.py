import pytest

from market_monitor.quality import (
    QualityReport,
    quarantine_partition,
    validate_cross_source,
    validate_partition,
)


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


def test_timezone_mismatch_is_blocking_and_matching_offset_passes():
    report = validate_partition("p", [bar()], "2026-08-03T10:00:00+08:00", expected_offset="+08:00")
    assert not report.blocking
    wrong = validate_partition(
        "p",
        [bar(bar_open_time="2026-08-03T01:30:00+00:00", bar_close_time="2026-08-03T01:45:00+00:00")],
        "2026-08-03T10:00:00+08:00",
        expected_offset="+08:00",
    )
    assert any(issue.category == "TIMEZONE" and issue.severity == "ERROR" for issue in wrong.issues)


def test_cross_source_comparison_never_mixes_rows_and_flags_diffs():
    reference = [bar(close=100.0)]
    matching = validate_cross_source("p", [bar(close=100.0)], reference)
    assert not matching.blocking
    diverging = validate_cross_source("p", [bar(close=110.0)], reference, close_tolerance=0.005)
    assert any(issue.category == "CROSS_SOURCE" and issue.severity == "ERROR" for issue in diverging.issues)
    missing = validate_cross_source("p", [bar(bar_open_time="2026-08-04T09:30:00+08:00")], reference)
    assert any(issue.category == "CROSS_SOURCE" and issue.severity == "WARNING" for issue in missing.issues)


def test_quarantine_persists_bars_and_report_outside_silver(tmp_path):
    report = validate_partition("p", [bar(volume=-1)], "2026-08-03T10:00:00+08:00")
    assert report.blocking
    target = quarantine_partition(tmp_path, "p", [bar(volume=-1)], report)
    assert (target / "bars.jsonl").is_file()
    assert (target / "quality-report.json").is_file()
    assert "quarantine" in str(target)
    with pytest.raises(FileExistsError):
        quarantine_partition(tmp_path, "p", [bar(volume=-1)], QualityReport("p", []))


def test_missing_or_non_positive_ohlc_and_missing_volume_are_blocking():
    empty_report = validate_partition("p", [{}], "2026-08-03T10:00:00+08:00")
    assert empty_report.blocking
    negative_report = validate_partition(
        "p",
        [bar(open=-1.0, high=-0.5, low=-2.0, close=-1.0)],
        "2026-08-03T10:00:00+08:00",
    )
    assert negative_report.blocking
    missing_volume = dict(bar())
    del missing_volume["volume"]
    assert validate_partition("p", [missing_volume], "2026-08-03T10:00:00+08:00").blocking
