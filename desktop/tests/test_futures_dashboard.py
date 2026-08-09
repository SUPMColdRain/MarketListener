import pytest

from market_monitor.futures_dashboard import (
    FuturesBreadthSnapshot,
    MemberPositionRow,
    OpenInterestLeaderRow,
    build_open_interest_leaderboard,
    compute_futures_breadth,
)


def _bar(code, day, close):
    return {
        "instrument_key": {"country_or_market": "CN", "exchange": "SHFE", "asset_type": "FUTURE", "code": code},
        "instrument_id": code,
        "trading_day": day,
        "period": "1d",
        "close": close,
    }


def test_compute_futures_breadth_counts_advance_decline_and_unchanged():
    bars_by_day = {
        "2026-08-03": [_bar("rb", "2026-08-03", 100.0), _bar("cu", "2026-08-03", 200.0)],
        "2026-08-04": [
            _bar("rb", "2026-08-04", 110.0),
            _bar("cu", "2026-08-04", 190.0),
            _bar("au", "2026-08-04", 300.0),
        ],
        "2026-08-05": [_bar("rb", "2026-08-05", 110.0), _bar("cu", "2026-08-05", 195.0)],
    }
    snapshots = compute_futures_breadth(bars_by_day, series_kind="WEIGHTED")
    assert [snapshot.trading_day for snapshot in snapshots] == ["2026-08-03", "2026-08-04", "2026-08-05"]
    assert snapshots[0].advances == snapshots[0].declines == snapshots[0].unchanged == 0
    assert snapshots[1].advances == 1
    assert snapshots[1].declines == 1
    assert snapshots[1].unchanged == 0
    assert snapshots[2].advances == 1
    assert snapshots[2].declines == 0
    assert snapshots[2].unchanged == 1
    assert all(snapshot.series_kind == "WEIGHTED" for snapshot in snapshots)
    assert all(snapshot.source == "local-computed" for snapshot in snapshots)
    assert isinstance(snapshots[0], FuturesBreadthSnapshot)


def test_compute_futures_breadth_rejects_unknown_series_kind():
    with pytest.raises(ValueError, match="series_kind"):
        compute_futures_breadth({}, series_kind="UNKNOWN")


def test_compute_futures_breadth_supports_all_registered_kinds():
    for kind in ("MAIN", "WEIGHTED", "CONTRACT", "INDEX"):
        snapshot = compute_futures_breadth(
            {"2026-08-03": [_bar("rb", "2026-08-03", 100.0)]},
            series_kind=kind,
        )[0]
        assert snapshot.series_kind == kind


def _member(instrument_id, trading_day, member, long_pos, long_chg, short_pos, short_chg):
    return MemberPositionRow(
        member=member,
        instrument_id=instrument_id,
        trading_day=trading_day,
        long_position=long_pos,
        long_position_change=long_chg,
        short_position=short_pos,
        short_position_change=short_chg,
    )


def test_leaderboard_aggregates_members_sorts_by_net_and_filters_day():
    rows = [
        _member("rb", "2026-08-04", "broker-a", 100, 10, 40, -5),
        _member("rb", "2026-08-04", "broker-b", 60, 5, 90, 8),
        _member("cu", "2026-08-04", "broker-a", 200, 20, 180, 12),
        _member("rb", "2026-08-03", "broker-a", 50, 0, 30, 0),
    ]
    leaderboard = build_open_interest_leaderboard(rows)
    assert [row.instrument_id for row in leaderboard] == ["rb", "cu"]
    assert leaderboard[0].net_position == pytest.approx(30.0)
    assert leaderboard[0].net_position_change == pytest.approx(12.0)
    assert leaderboard[0].member_count == 2
    assert leaderboard[0].long_position == pytest.approx(160.0)
    assert leaderboard[0].short_position == pytest.approx(130.0)
    assert leaderboard[1].net_position == pytest.approx(20.0)
    assert leaderboard[1].net_position_change == pytest.approx(8.0)
    assert leaderboard[1].member_count == 1
    assert isinstance(leaderboard[0], OpenInterestLeaderRow)

    filtered = build_open_interest_leaderboard(rows, trading_day="2026-08-03")
    assert [row.instrument_id for row in filtered] == ["rb"]
    assert filtered[0].net_position == pytest.approx(20.0)

    top = build_open_interest_leaderboard(rows, top_n=1)
    assert [row.instrument_id for row in top] == ["rb"]


def test_leaderboard_empty_and_validation():
    assert build_open_interest_leaderboard([]) == []
    row = _member("rb", "2026-08-04", "broker-a", 1, 0, 1, 0)
    with pytest.raises(ValueError, match="top_n"):
        build_open_interest_leaderboard([row], top_n=0)


def test_instrument_id_accepts_key_code_or_direct_field():
    from market_monitor.futures_dashboard import _instrument_id

    assert _instrument_id({"instrument_key": {"code": "rb2610"}, "instrument_id": "ignored"}) == "rb2610"
    assert _instrument_id({"instrument_id": "rb2610"}) == "rb2610"
    assert _instrument_id({"instrument_key": {}}) == ""
