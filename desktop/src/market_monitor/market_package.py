"""Immutable offline market package creation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import zipfile
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
) -> Path:
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
            "partitions": [{"partition_id": quality_report.partition_id, "data_cutoff": data_cutoff, "files": files}],
            "source_run_summaries": list(source_run_summaries),
        }
        validate_contract("market-package-manifest.schema.json", manifest)
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in (root / "manifest.json", payload, quality_path):
                archive.write(file, file.name)
    return target


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
