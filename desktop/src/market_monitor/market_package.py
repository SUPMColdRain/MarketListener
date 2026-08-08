"""Immutable offline market package creation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import validate_contract
from .quality import QualityReport


def build_market_package(
    output_dir: Path,
    package_id: str,
    bars: Sequence[Mapping[str, Any]],
    quality_report: QualityReport,
    data_cutoff: str,
    source_run_summaries: Sequence[Mapping[str, str]],
    minimum_app_version: str = "0.1.0",
    *,
    package_type: str = "FULL",
    base_package_id: str | None = None,
) -> Path:
    if package_type not in ("FULL", "DELTA"):
        raise ValueError(f"Unknown package type: {package_type}")
    if package_type == "DELTA" and not base_package_id:
        raise ValueError("A DELTA package requires a base_package_id")
    if quality_report.blocking:
        raise ValueError("A partition with blocking quality issues cannot enter a market package")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{package_id}.zip"
    if target.exists():
        raise FileExistsError(f"Immutable market package already exists: {target}")
    with tempfile.TemporaryDirectory(prefix="market-package-") as temporary:
        root = Path(temporary)
        payload = root / "payload.sqlite"
        _write_payload(payload, bars)
        quality_path = root / "quality-report.json"
        quality_path.write_text(json.dumps(quality_report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        files = [_file_metadata(payload), _file_metadata(quality_path)]
        manifest = {
            "package_id": package_id,
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "minimum_app_version": minimum_app_version,
            "package_type": package_type,
            "partitions": [{"partition_id": quality_report.partition_id, "data_cutoff": data_cutoff, "files": files}],
            "source_run_summaries": list(source_run_summaries),
        }
        if base_package_id is not None:
            manifest["base_package_id"] = base_package_id
        validate_contract("market-package-manifest.schema.json", manifest)
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in (root / "manifest.json", payload, quality_path):
                archive.write(file, file.name)
    return target


def build_delta_package(
    output_dir: Path,
    package_id: str,
    base_package_id: str,
    bars: Sequence[Mapping[str, Any]],
    quality_report: QualityReport,
    data_cutoff: str,
    source_run_summaries: Sequence[Mapping[str, str]],
    minimum_app_version: str = "0.1.0",
    ledger: PackageLedger | None = None,
) -> Path:
    """Build an immutable incremental (DELTA) package layered on a base."""

    if ledger is not None and ledger.entry(base_package_id) is None:
        raise ValueError(f"base package {base_package_id} is not registered in the ledger")
    return build_market_package(
        output_dir,
        package_id,
        bars,
        quality_report,
        data_cutoff,
        source_run_summaries,
        minimum_app_version,
        package_type="DELTA",
        base_package_id=base_package_id,
    )


@dataclass(frozen=True)
class PackageLedgerEntry:
    package_id: str
    package_type: str
    base_package_id: str | None
    built_at: str
    status: str


class PackageLedger:
    """Tracks immutable packages and the active/rollback pointer."""

    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS packages (
                package_id TEXT PRIMARY KEY, package_type TEXT NOT NULL, base_package_id TEXT,
                built_at TEXT NOT NULL, status TEXT NOT NULL
            )"""
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def register(self, package_id: str, package_type: str, base_package_id: str | None = None) -> None:
        self.connection.execute(
            "INSERT INTO packages VALUES (?, ?, ?, ?, 'REGISTERED')",
            (package_id, package_type, base_package_id, _now()),
        )
        self.connection.commit()

    def activate(self, package_id: str) -> None:
        if not self._exists(package_id):
            raise KeyError(f"Unknown package: {package_id}")
        self.connection.execute("UPDATE packages SET status='SUPERSEDED' WHERE status='ACTIVE'")
        self.connection.execute("UPDATE packages SET status='ACTIVE' WHERE package_id=?", (package_id,))
        self.connection.commit()

    def rollback_to(self, package_id: str) -> None:
        if not self._exists(package_id):
            raise KeyError(f"Unknown package: {package_id}")
        current = self.active()
        if current is not None and current.package_id != package_id:
            self.connection.execute("UPDATE packages SET status='ROLLED_BACK' WHERE package_id=?", (current.package_id,))
        self.connection.execute("UPDATE packages SET status='ACTIVE' WHERE package_id=?", (package_id,))
        self.connection.commit()

    def active(self) -> PackageLedgerEntry | None:
        row = self.connection.execute("SELECT * FROM packages WHERE status='ACTIVE' ORDER BY built_at DESC LIMIT 1").fetchone()
        return PackageLedgerEntry(*row) if row else None

    def entry(self, package_id: str) -> PackageLedgerEntry | None:
        row = self.connection.execute("SELECT * FROM packages WHERE package_id=?", (package_id,)).fetchone()
        return PackageLedgerEntry(*row) if row else None

    def _exists(self, package_id: str) -> bool:
        return self.connection.execute("SELECT 1 FROM packages WHERE package_id=?", (package_id,)).fetchone() is not None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_payload(path: Path, bars: Sequence[Mapping[str, Any]]) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """PRAGMA foreign_keys=ON;
            CREATE TABLE instruments (instrument_id TEXT PRIMARY KEY, instrument_json TEXT NOT NULL);
            CREATE TABLE bars (
                instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id), period TEXT NOT NULL,
                bar_open_time TEXT NOT NULL, bar_json TEXT NOT NULL,
                PRIMARY KEY (instrument_id, period, bar_open_time)
            );"""
        )
        instruments: dict[str, Mapping[str, Any]] = {}
        for bar in bars:
            key = bar["instrument_key"]
            instrument_id = ".".join(str(key[field]) for field in ("country_or_market", "exchange", "asset_type", "code"))
            instruments[instrument_id] = key
        for instrument_id, key in instruments.items():
            connection.execute("INSERT INTO instruments VALUES (?, ?)", (instrument_id, json.dumps(key, ensure_ascii=False)))
        for bar in bars:
            key = bar["instrument_key"]
            instrument_id = ".".join(str(key[field]) for field in ("country_or_market", "exchange", "asset_type", "code"))
            connection.execute("INSERT INTO bars VALUES (?, ?, ?, ?)", (instrument_id, bar["period"], bar["bar_open_time"], json.dumps(bar, ensure_ascii=False)))
        connection.commit()
    finally:
        connection.close()


def _file_metadata(path: Path) -> dict[str, Any]:
    return {"name": path.name, "bytes": path.stat().st_size, "row_count": _row_count(path), "sha256": _sha256(path)}


def _row_count(path: Path) -> int:
    if path.suffix == ".sqlite":
        connection = sqlite3.connect(path)
        try:
            return connection.execute("SELECT count(*) FROM bars").fetchone()[0]
        finally:
            connection.close()
    return 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest
