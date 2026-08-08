"""Bronze snapshots, immutable Silver partitions, and DuckDB run metadata."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

import duckdb


@dataclass(frozen=True)
class PartitionKey:
    market: str
    asset_type: str
    period: str
    year: int
    partition_id: str

    def relative_path(self) -> Path:
        return Path(
            "silver",
            f"market={self.market}",
            f"asset_type={self.asset_type}",
            f"period={self.period}",
            f"year={self.year}",
            f"{self.partition_id}.parquet",
        )


class MarketStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(root / "catalog.duckdb"))
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def begin_run(self, provider: str) -> str:
        run_id = f"run-{uuid4().hex}"
        self.connection.execute(
            "INSERT INTO runs VALUES (?, ?, 'RUNNING', ?, NULL, NULL)",
            [run_id, provider, _now()],
        )
        return run_id

    def finish_run(self, run_id: str, status: str, detail: str | None = None) -> None:
        self.connection.execute(
            "UPDATE runs SET status=?, completed_at=?, detail=? WHERE run_id=?",
            [status, _now(), detail, run_id],
        )

    def write_bronze(self, run_id: str, provider: str, response: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> Path:
        directory = self.root / "bronze" / provider
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{run_id}.json"
        self._atomic_json(target, response)
        return target

    def write_silver_bars(
        self,
        key: PartitionKey,
        bars: Sequence[Mapping[str, Any]],
        data_cutoff: str,
        source_run_id: str,
    ) -> Path:
        if not bars:
            raise ValueError("A Silver partition requires at least one normalized bar")
        target = self.root / key.relative_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        staging_parquet = target.with_suffix(f".{uuid4().hex}.parquet")
        try:
            escaped_parquet = str(staging_parquet).replace("'", "''")
            existing: list[dict[str, str]] = []
            if target.is_file():
                existing = [
                    {"bar_json": row[0], "instrument_id": row[1], "bar_period": row[2], "bar_open_time": row[3]}
                    for row in self.connection.execute(
                        f"SELECT bar_json, instrument_id, bar_period, bar_open_time FROM read_parquet('{str(target).replace(chr(39), chr(39) * 2)}')"
                    ).fetchall()
                ]
            rows: dict[tuple[str, str, str], dict[str, str]] = {
                (row["instrument_id"], row["bar_period"], row["bar_open_time"]): row for row in existing
            }
            for bar in bars:
                key_tuple = (_bar_instrument_id(bar), str(bar.get("period", "")), str(bar.get("bar_open_time", "")))
                rows[key_tuple] = {
                    "bar_json": json.dumps(bar, ensure_ascii=False),
                    "instrument_id": key_tuple[0],
                    "bar_period": key_tuple[1],
                    "bar_open_time": key_tuple[2],
                }
            self.connection.execute(
                "CREATE OR REPLACE TEMP TABLE _silver_stage (bar_json VARCHAR, instrument_id VARCHAR, bar_period VARCHAR, bar_open_time VARCHAR)"
            )
            for row in rows.values():
                self.connection.execute(
                    "INSERT INTO _silver_stage VALUES (?, ?, ?, ?)",
                    (row["bar_json"], row["instrument_id"], row["bar_period"], row["bar_open_time"]),
                )
            self.connection.execute(
                f"COPY (SELECT bar_json, instrument_id, bar_period, bar_open_time FROM _silver_stage) TO '{escaped_parquet}' (FORMAT PARQUET)"
            )
            self.connection.execute("DROP TABLE _silver_stage")
            row_count = self.connection.execute(
                f"SELECT count(*) FROM read_parquet('{escaped_parquet}') WHERE bar_json IS NOT NULL"
            ).fetchone()[0]
            if row_count != len(rows):
                raise RuntimeError(f"Silver validation row mismatch: expected {len(rows)}, got {row_count}")
            checksum = _sha256(staging_parquet)
            os.replace(staging_parquet, target)
            self.connection.execute(
                """INSERT INTO partitions VALUES (?, ?, ?, ?, ?, ?, 'COMPLETE', ?)
                ON CONFLICT(partition_id) DO UPDATE SET file_path=excluded.file_path, row_count=excluded.row_count,
                data_cutoff=excluded.data_cutoff, sha256=excluded.sha256, source_run_id=excluded.source_run_id,
                status=excluded.status, updated_at=excluded.updated_at""",
                [key.partition_id, str(target.relative_to(self.root)), row_count, data_cutoff, checksum, source_run_id, _now()],
            )
            return target
        finally:
            staging_parquet.unlink(missing_ok=True)

    def partition_metadata(self, partition_id: str) -> tuple[Any, ...] | None:
        return self.connection.execute(
            "SELECT file_path, row_count, data_cutoff, sha256, status FROM partitions WHERE partition_id=?",
            [partition_id],
        ).fetchone()

    def _atomic_json(self, target: Path, data: Any) -> None:
        staging = target.with_suffix(f".{uuid4().hex}.json")
        try:
            staging.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(staging, target)
        finally:
            staging.unlink(missing_ok=True)

    def _create_schema(self) -> None:
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS runs (
                run_id VARCHAR PRIMARY KEY, provider VARCHAR NOT NULL, status VARCHAR NOT NULL,
                started_at VARCHAR NOT NULL, completed_at VARCHAR, detail VARCHAR
            )"""
        )
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS partitions (
                partition_id VARCHAR PRIMARY KEY, file_path VARCHAR NOT NULL, row_count BIGINT NOT NULL,
                data_cutoff VARCHAR NOT NULL, sha256 VARCHAR NOT NULL, source_run_id VARCHAR NOT NULL,
                status VARCHAR NOT NULL, updated_at VARCHAR NOT NULL
            )"""
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bar_instrument_id(bar: Mapping[str, Any]) -> str:
    key = bar.get("instrument_key")
    if isinstance(key, Mapping):
        return ".".join(str(key.get(part, "")) for part in ("country_or_market", "exchange", "asset_type", "code"))
    return str(key if key is not None else bar.get("instrument_id", ""))
