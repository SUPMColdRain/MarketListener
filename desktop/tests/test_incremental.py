from datetime import datetime, timedelta, timezone

import pytest

from market_monitor.incremental import (
    CheckpointStore,
    FetchOutcome,
    IncrementalCollector,
    LockHeldError,
)
from market_monitor.storage import MarketStore, PartitionKey


def bar(open_time: str, close: float = 100.0) -> dict[str, object]:
    return {
        "schema_version": 1,
        "instrument_key": {"country_or_market": "CN", "exchange": "SSE", "asset_type": "STOCK", "code": "600519"},
        "period": "1d",
        "trading_day": open_time[:10],
        "bar_open_time": open_time,
        "bar_close_time": open_time[:10] + "T15:00:00+08:00",
        "timezone": "Asia/Shanghai",
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 10,
        "amount": 1000,
        "open_interest": None,
        "price_mode": "RAW",
        "source": {"provider": "test", "source_symbol": "600519.SH", "retrieved_at": "2026-08-05T00:00:00Z"},
        "source_period": "1d",
        "quality_status": "PASS",
    }


def key() -> PartitionKey:
    return PartitionKey("CN", "STOCK", "1d", 2026, "CN-STOCK-1d-2026")


def test_cursor_resume_and_idempotent_rerun(tmp_path) -> None:
    store = MarketStore(tmp_path / "data")
    checkpoints = CheckpointStore(tmp_path / "checkpoints.sqlite")
    collector = IncrementalCollector(store, checkpoints)
    calls: list[str | None] = []

    def fetch(cursor: str | None) -> FetchOutcome:
        calls.append(cursor)
        if cursor is None:
            return FetchOutcome([bar("2026-08-03T09:30:00+08:00")], "2026-08-03T09:30:00+08:00")
        return FetchOutcome([bar("2026-08-04T09:30:00+08:00", close=101.0)], "2026-08-04T09:30:00+08:00")

    first = collector.collect(source="test", instrument="600519", period="1d", partition_key=key(), fetch=fetch)
    second = collector.collect(source="test", instrument="600519", period="1d", partition_key=key(), fetch=fetch)

    assert first.status == "PASS" and first.written_bars == 1
    assert second.status == "PASS" and second.written_bars == 1
    assert second.started_cursor == "2026-08-03T09:30:00+08:00"
    assert calls == [None, "2026-08-03T09:30:00+08:00"]
    assert checkpoints.cursor("test", "600519", "1d") == "2026-08-04T09:30:00+08:00"
    metadata = store.partition_metadata(key().partition_id)
    assert metadata is not None and metadata[1] == 2


def test_bounded_retries_then_failed_status_without_cursor_advance(tmp_path) -> None:
    store = MarketStore(tmp_path / "data")
    checkpoints = CheckpointStore(tmp_path / "checkpoints.sqlite")
    collector = IncrementalCollector(store, checkpoints, max_retries=2, backoff_seconds=0)
    calls = 0

    def fetch(cursor: str | None) -> FetchOutcome:
        nonlocal calls
        calls += 1
        raise ConnectionError("network down")

    summary = collector.collect(source="test", instrument="600519", period="1d", partition_key=key(), fetch=fetch)

    assert summary.status == "FAILED"
    assert summary.retries == 3
    assert calls == 3
    assert checkpoints.cursor("test", "600519", "1d") is None


def test_partial_failure_keeps_written_bars_and_marks_run(tmp_path) -> None:
    store = MarketStore(tmp_path / "data")
    checkpoints = CheckpointStore(tmp_path / "checkpoints.sqlite")
    collector = IncrementalCollector(store, checkpoints)

    def fetch(cursor: str | None) -> FetchOutcome:
        return FetchOutcome(
            [bar("2026-08-03T09:30:00+08:00")],
            "2026-08-03T09:30:00+08:00",
            partial_error="funds endpoint unavailable",
        )

    summary = collector.collect(source="test", instrument="600519", period="1d", partition_key=key(), fetch=fetch)

    assert summary.status == "PARTIAL_FAILURE"
    assert summary.written_bars == 1
    assert store.partition_metadata(key().partition_id) is not None
    assert checkpoints.cursor("test", "600519", "1d") == "2026-08-03T09:30:00+08:00"


def test_duplicate_bars_within_batch_are_dropped_before_silver(tmp_path) -> None:
    store = MarketStore(tmp_path / "data")
    checkpoints = CheckpointStore(tmp_path / "checkpoints.sqlite")
    collector = IncrementalCollector(store, checkpoints)

    def fetch(cursor: str | None) -> FetchOutcome:
        return FetchOutcome(
            [bar("2026-08-03T09:30:00+08:00"), bar("2026-08-03T09:30:00+08:00")],
            "2026-08-03T09:30:00+08:00",
        )

    summary = collector.collect(source="test", instrument="600519", period="1d", partition_key=key(), fetch=fetch)

    assert summary.written_bars == 1


def test_concurrent_collection_is_blocked_by_unit_lock(tmp_path) -> None:
    checkpoints = CheckpointStore(tmp_path / "checkpoints.sqlite")
    checkpoints.acquire_lock("test", "600519", "1d", "owner-a")
    with pytest.raises(LockHeldError):
        checkpoints.acquire_lock("test", "600519", "1d", "owner-b", timeout_ms=50)
    checkpoints.release_lock("test", "600519", "1d", "owner-a")
    checkpoints.acquire_lock("test", "600519", "1d", "owner-b")


def test_stale_lock_is_taken_over_after_ttl(tmp_path) -> None:
    checkpoints = CheckpointStore(tmp_path / "checkpoints.sqlite")
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    checkpoints.connection.execute(
        "INSERT INTO run_locks VALUES (?, ?, ?, ?, ?)",
        ("test", "600519", "1d", "crashed-owner", old),
    )
    checkpoints.connection.commit()

    checkpoints.acquire_lock("test", "600519", "1d", "new-owner", lock_ttl_seconds=3600)

    checkpoints.release_lock("test", "600519", "1d", "new-owner")
