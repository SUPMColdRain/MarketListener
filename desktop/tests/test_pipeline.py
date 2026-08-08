import zipfile

from market_monitor.incremental import FetchOutcome
from market_monitor.market_package import PackageLedger
from market_monitor.pipeline import IngestUnit, MarketPipeline
from market_monitor.storage import PartitionKey


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


def test_pipeline_ingests_quality_signs_and_activates_ledger(tmp_path) -> None:
    key = PartitionKey("CN", "STOCK", "1d", 2026, "CN-STOCK-1d-2026")
    unit = IngestUnit(
        source="test",
        instrument="600519",
        period="1d",
        partition_key=key,
        fetch=lambda cursor: FetchOutcome([bar("2026-08-03T09:30:00+08:00")], "2026-08-03T09:30:00+08:00"),
    )
    pipeline = MarketPipeline(
        data_root=tmp_path / "data",
        state_path=tmp_path / "state.sqlite",
        output_dir=tmp_path / "packages",
        private_key_path=tmp_path / "keys" / "private.pem",
        public_key_path=tmp_path / "keys" / "public.pem",
    )
    ledger = PackageLedger(tmp_path / "ledger.sqlite")
    try:
        result = pipeline.run(
            package_id="market-001",
            units=[unit],
            data_cutoff="2026-08-03T15:00:00+08:00",
            source_run_summaries=[{"run_id": "run-1", "provider": "test", "status": "PASS"}],
            ledger=ledger,
        )

        assert result.ingest[0].status == "PASS"
        assert result.quality is not None and not result.quality.blocking
        assert result.package_path is not None and result.package_path.is_file()
        assert result.verified
        assert ledger.active().package_id == "market-001"
    finally:
        pipeline.close()
        ledger.close()


def test_pipeline_quarantines_blocking_bars_without_packaging(tmp_path) -> None:
    key = PartitionKey("CN", "STOCK", "1d", 2026, "CN-STOCK-1d-2026-bad")
    bad_bar = bar("2026-08-03T09:30:00+08:00")
    bad_bar["volume"] = -1
    unit = IngestUnit(
        source="test",
        instrument="600519",
        period="1d",
        partition_key=key,
        fetch=lambda cursor: FetchOutcome([bad_bar], "2026-08-03T09:30:00+08:00"),
    )
    pipeline = MarketPipeline(
        data_root=tmp_path / "data",
        state_path=tmp_path / "state.sqlite",
        output_dir=tmp_path / "packages",
        private_key_path=tmp_path / "keys" / "private.pem",
        public_key_path=tmp_path / "keys" / "public.pem",
    )
    try:
        result = pipeline.run(
            package_id="market-bad",
            units=[unit],
            data_cutoff="2026-08-03T15:00:00+08:00",
            source_run_summaries=[],
        )

        assert result.package_path is None
        assert result.ledger_status == "QUARANTINED"
        assert result.quality is not None and result.quality.blocking
        assert (tmp_path / "data" / "quarantine").is_dir()
    finally:
        pipeline.close()


def test_pipeline_does_not_package_when_ingest_fails(tmp_path) -> None:
    key = PartitionKey("CN", "STOCK", "1d", 2026, "CN-STOCK-1d-2026-fail")

    def failing_fetch(cursor):
        raise ConnectionError("network down")

    unit = IngestUnit(
        source="test",
        instrument="600519",
        period="1d",
        partition_key=key,
        fetch=failing_fetch,
    )
    pipeline = MarketPipeline(
        data_root=tmp_path / "data",
        state_path=tmp_path / "state.sqlite",
        output_dir=tmp_path / "packages",
        private_key_path=tmp_path / "keys" / "private.pem",
        public_key_path=tmp_path / "keys" / "public.pem",
        max_retries=0,
    )
    try:
        result = pipeline.run(
            package_id="market-fail",
            units=[unit],
            data_cutoff="2026-08-03T15:00:00+08:00",
            source_run_summaries=[],
        )

        assert result.package_path is None
        assert result.ledger_status == "INGEST_FAILED"
    finally:
        pipeline.close()


def test_pipeline_preserves_timezone_offsets_in_package_payload(tmp_path) -> None:
    key = PartitionKey("CN", "STOCK", "1d", 2026, "CN-STOCK-1d-2026-tz")
    unit = IngestUnit(
        source="test",
        instrument="600519",
        period="1d",
        partition_key=key,
        fetch=lambda cursor: FetchOutcome([bar("2026-08-03T09:30:00+08:00")], "2026-08-03T09:30:00+08:00"),
    )
    pipeline = MarketPipeline(
        data_root=tmp_path / "data",
        state_path=tmp_path / "state.sqlite",
        output_dir=tmp_path / "packages",
        private_key_path=tmp_path / "keys" / "private.pem",
        public_key_path=tmp_path / "keys" / "public.pem",
    )
    try:
        result = pipeline.run(
            package_id="market-tz",
            units=[unit],
            data_cutoff="2026-08-03T15:00:00+08:00",
            source_run_summaries=[],
            expected_offset="+08:00",
        )

        assert result.package_path is not None and result.verified
        with zipfile.ZipFile(result.package_path) as archive:
            payload = archive.read("payload.sqlite")
        assert b"2026-08-03T09:30:00+08:00" in payload
    finally:
        pipeline.close()
