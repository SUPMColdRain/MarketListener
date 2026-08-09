import hashlib
import json
import sqlite3
import zipfile

import pytest

from market_monitor.market_package import (
    PackageLedger,
    build_delta_package,
    build_market_package,
)
from market_monitor.quality import QualityReport


def bar():
    return {"instrument_key": {"country_or_market": "CN", "exchange": "SSE", "asset_type": "STOCK", "code": "600519"}, "period": "1d", "bar_open_time": "2026-08-03T09:30:00+08:00"}


def test_market_package_checks_manifest_hashes_and_payload_constraints(tmp_path):
    report = QualityReport("CN-STOCK-1d-20260803", [])
    package = build_market_package(tmp_path, "market-001", [bar()], report, "2026-08-03T15:00:00+08:00", [{"run_id": "run-1", "provider": "test", "status": "PASS"}])
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        for file in manifest["partitions"][0]["files"]:
            assert hashlib.sha256(archive.read(file["name"])).hexdigest() == file["sha256"]
        payload = tmp_path / "payload.sqlite"
        payload.write_bytes(archive.read("payload.sqlite"))
    connection = sqlite3.connect(payload)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("SELECT count(*) FROM bars").fetchone()[0] == 1


def test_market_package_writes_gold_metrics_and_counts_them(tmp_path):
    report = QualityReport("p", [])
    metrics = [
        {
            "metric_id": "CN_MARGIN:CN.SSE.MARGIN:20260807:1d:融资余额",
            "instrument_id": "CN.SSE.MARGIN",
            "trading_date": "20260807",
            "period": "1d",
            "metric_name": "沪市融资余额",
            "value": 1266993136806.0,
            "definition": "融资余额",
            "calculation_method": "sum",
            "timestamp": "2026-08-07T15:00:00+08:00",
        }
    ]
    package = build_market_package(
        tmp_path,
        "market-gold-001",
        [bar()],
        report,
        "2026-08-07T15:00:00+08:00",
        [{"run_id": "run-1", "provider": "test", "status": "PASS"}],
        gold_metrics=metrics,
    )
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        payload = tmp_path / "payload-gold.sqlite"
        payload.write_bytes(archive.read("payload.sqlite"))
    assert manifest["partitions"][0]["files"][0]["row_count"] == 2

    connection = sqlite3.connect(payload)
    assert connection.execute("SELECT count(*) FROM gold_metrics").fetchone()[0] == 1
    row = connection.execute(
        "SELECT metric_id, metric_name, value FROM gold_metrics"
    ).fetchone()
    assert row == ("CN_MARGIN:CN.SSE.MARGIN:20260807:1d:融资余额", "沪市融资余额", 1266993136806.0)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_blocking_quality_issue_cannot_be_packaged(tmp_path):
    report = QualityReport("p", [])
    report = QualityReport("p", [type("Issue", (), {"severity": "ERROR"})()])
    with pytest.raises(ValueError, match="blocking"):
        build_market_package(tmp_path, "market-002", [bar()], report, "2026-08-03T15:00:00+08:00", [])


def test_delta_package_requires_base_and_marks_manifest(tmp_path):
    report = QualityReport("CN-STOCK-1d-20260804", [])
    package = build_delta_package(
        tmp_path, "market-delta-001", "market-001", [bar()], report,
        "2026-08-04T15:00:00+08:00", [{"run_id": "run-1", "provider": "test", "status": "PASS"}],
    )
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["package_type"] == "DELTA"
    assert manifest["base_package_id"] == "market-001"


def test_delta_package_without_base_is_rejected(tmp_path):
    report = QualityReport("p", [])
    with pytest.raises(ValueError, match="base_package_id"):
        build_delta_package(tmp_path, "bad", "", [bar()], report, "2026-08-04T15:00:00+08:00", [])


def test_delta_package_rejects_unregistered_base_ledger(tmp_path):
    ledger = PackageLedger(tmp_path / "ledger.sqlite")
    report = QualityReport("p", [])
    with pytest.raises(ValueError, match="not registered"):
        build_delta_package(
            tmp_path, "delta-bad", "missing-base", [bar()], report,
            "2026-08-04T15:00:00+08:00", [], ledger=ledger,
        )


def test_package_ledger_activation_and_rollback(tmp_path):
    ledger = PackageLedger(tmp_path / "ledger.sqlite")
    for package_id, package_type, base in (
        ("full-1", "FULL", None),
        ("delta-2", "DELTA", "full-1"),
        ("full-3", "FULL", None),
    ):
        ledger.register(package_id, package_type, base)
    ledger.activate("full-1")
    ledger.activate("delta-2")
    assert ledger.active().package_id == "delta-2"

    ledger.rollback_to("full-1")

    assert ledger.active().package_id == "full-1"
    assert ledger.entry("delta-2").status == "ROLLED_BACK"
    assert ledger.entry("full-3").status == "REGISTERED"


def test_package_ledger_rejects_unknown_and_duplicate(tmp_path):
    ledger = PackageLedger(tmp_path / "ledger.sqlite")
    ledger.register("full-1", "FULL")
    with pytest.raises(Exception):
        ledger.register("full-1", "FULL")
    with pytest.raises(KeyError):
        ledger.activate("missing")
    with pytest.raises(KeyError):
        ledger.rollback_to("missing")
