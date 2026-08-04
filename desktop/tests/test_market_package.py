import hashlib
import json
import sqlite3
import zipfile

import pytest

from market_monitor.market_package import build_market_package
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


def test_blocking_quality_issue_cannot_be_packaged(tmp_path):
    report = QualityReport("p", [])
    report = QualityReport("p", [type("Issue", (), {"severity": "ERROR"})()])
    with pytest.raises(ValueError, match="blocking"):
        build_market_package(tmp_path, "market-002", [bar()], report, "2026-08-03T15:00:00+08:00", [])
