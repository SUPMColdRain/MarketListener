from datetime import datetime

import duckdb
import pytest

from market_monitor.storage import MarketStore, PartitionKey


def bars(close: float) -> list[dict[str, object]]:
    return [{"instrument_id": "CN.SSE.STOCK.600519", "bar_open_time": "2026-08-03T09:30:00+08:00", "close": close}]


def key() -> PartitionKey:
    return PartitionKey("CN", "STOCK", "15m", 2026, "CN-STOCK-15m-20260803")


def test_bronze_and_silver_are_recorded_with_an_idempotent_partition(tmp_path) -> None:
    store = MarketStore(tmp_path / "data")
    run_id = store.begin_run("test_provider")
    bronze = store.write_bronze(run_id, "test_provider", {"payload": [{"raw": 1}]})
    first = store.write_silver_bars(key(), bars(100.0), "2026-08-03T10:00:00+08:00", run_id)
    second = store.write_silver_bars(key(), bars(100.0), "2026-08-03T10:00:00+08:00", run_id)
    store.finish_run(run_id, "PASS")
    metadata = store.partition_metadata(key().partition_id)
    assert bronze.is_file() and first == second and first.is_file()
    assert duckdb.sql(f"SELECT count(*) FROM read_parquet('{first.as_posix()}')").fetchone()[0] == 1
    assert metadata and metadata[1] == 1 and metadata[4] == "COMPLETE"


def test_failed_retry_does_not_replace_previous_complete_partition(tmp_path, monkeypatch) -> None:
    store = MarketStore(tmp_path / "data")
    run_id = store.begin_run("test_provider")
    partition = store.write_silver_bars(key(), bars(100.0), "2026-08-03T10:00:00+08:00", run_id)
    before = partition.read_bytes()
    monkeypatch.setattr("market_monitor.storage.os.replace", lambda *_: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        store.write_silver_bars(key(), bars(101.0), "2026-08-03T10:15:00+08:00", run_id)
    assert partition.read_bytes() == before
