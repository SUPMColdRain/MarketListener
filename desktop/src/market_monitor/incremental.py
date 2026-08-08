"""Incremental collection with cursors, bounded retries and resume.

The collector is deliberately small: one *source/instrument/period* unit per
call, so a partial failure in one unit cannot wipe another unit's results.
The orchestrator that loops over units is responsible for aggregate status.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from .storage import MarketStore, PartitionKey


class LockHeldError(RuntimeError):
    """Raised when another collector owns the same unit."""


@dataclass(frozen=True)
class FetchOutcome:
    bars: Sequence[Mapping[str, Any]]
    cursor: str | None
    partial_error: str | None = None


@dataclass(frozen=True)
class IncrementalRunSummary:
    source: str
    instrument: str
    period: str
    run_id: str
    started_cursor: str | None
    ended_cursor: str | None
    fetched_bars: int
    written_bars: int
    retries: int
    status: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "instrument": self.instrument,
            "period": self.period,
            "run_id": self.run_id,
            "started_cursor": self.started_cursor,
            "ended_cursor": self.ended_cursor,
            "fetched_bars": self.fetched_bars,
            "written_bars": self.written_bars,
            "retries": self.retries,
            "status": self.status,
            "error": self.error,
        }


class CheckpointStore:
    """Persistent per-unit cursors and run locks."""

    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path, timeout=10)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS checkpoints (
                source TEXT NOT NULL, instrument TEXT NOT NULL, period TEXT NOT NULL,
                cursor_value TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (source, instrument, period)
            )"""
        )
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS run_locks (
                source TEXT NOT NULL, instrument TEXT NOT NULL, period TEXT NOT NULL,
                owner TEXT NOT NULL, locked_at TEXT NOT NULL,
                PRIMARY KEY (source, instrument, period)
            )"""
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def cursor(self, source: str, instrument: str, period: str) -> str | None:
        row = self.connection.execute(
            "SELECT cursor_value FROM checkpoints WHERE source=? AND instrument=? AND period=?",
            (source, instrument, period),
        ).fetchone()
        return str(row[0]) if row else None

    def set_cursor(self, source: str, instrument: str, period: str, cursor_value: str) -> None:
        self.connection.execute(
            """INSERT INTO checkpoints (source, instrument, period, cursor_value, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source, instrument, period) DO UPDATE SET
                cursor_value=excluded.cursor_value, updated_at=excluded.updated_at""",
            (source, instrument, period, cursor_value, _now()),
        )
        self.connection.commit()

    def acquire_lock(
        self,
        source: str,
        instrument: str,
        period: str,
        owner: str,
        *,
        timeout_ms: int = 0,
        lock_ttl_seconds: float = 3600.0,
    ) -> None:
        deadline = monotonic() + timeout_ms / 1000
        while True:
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                existing = self.connection.execute(
                    "SELECT owner, locked_at FROM run_locks WHERE source=? AND instrument=? AND period=?",
                    (source, instrument, period),
                ).fetchone()
                if existing is None:
                    self.connection.execute(
                        "INSERT INTO run_locks VALUES (?, ?, ?, ?, ?)",
                        (source, instrument, period, owner, _now()),
                    )
                    self.connection.commit()
                    return
                if _is_stale_lock(existing[1], lock_ttl_seconds):
                    self.connection.execute(
                        "DELETE FROM run_locks WHERE source=? AND instrument=? AND period=? AND locked_at=?",
                        (source, instrument, period, existing[1]),
                    )
                    self.connection.execute(
                        "INSERT INTO run_locks VALUES (?, ?, ?, ?, ?)",
                        (source, instrument, period, owner, _now()),
                    )
                    self.connection.commit()
                    return
                self.connection.rollback()
                if monotonic() >= deadline:
                    raise LockHeldError(f"unit already locked by {existing[0]} since {existing[1]}")
                sleep(0.05)
            except sqlite3.OperationalError as error:
                self.connection.rollback()
                if "locked" not in str(error).lower() and "busy" not in str(error).lower():
                    raise
                if monotonic() >= deadline:
                    raise LockHeldError("database lock busy") from error
                sleep(0.05)

    def release_lock(self, source: str, instrument: str, period: str, owner: str) -> None:
        self.connection.execute(
            "DELETE FROM run_locks WHERE source=? AND instrument=? AND period=? AND owner=?",
            (source, instrument, period, owner),
        )
        self.connection.commit()


class IncrementalCollector:
    def __init__(
        self,
        store: MarketStore,
        checkpoints: CheckpointStore,
        *,
        max_retries: int = 2,
        backoff_seconds: float = 0.0,
    ) -> None:
        self.store = store
        self.checkpoints = checkpoints
        self.max_retries = max(0, max_retries)
        self.backoff_seconds = max(0.0, backoff_seconds)

    def collect(
        self,
        *,
        source: str,
        instrument: str,
        period: str,
        partition_key: PartitionKey,
        fetch: Callable[[str | None], FetchOutcome],
        normalize: Callable[[Mapping[str, Any]], list[Mapping[str, Any]]] | None = None,
    ) -> IncrementalRunSummary:
        owner = f"collector-{uuid4().hex}"
        self.checkpoints.acquire_lock(source, instrument, period, owner)
        run_id = self.store.begin_run(source)
        started_cursor = self.checkpoints.cursor(source, instrument, period)
        attempts = 0
        try:
            while True:
                try:
                    outcome = fetch(started_cursor)
                    break
                except Exception as error:  # noqa: BLE001 - bounded retry for transient failures
                    attempts += 1
                    if attempts > self.max_retries:
                        self.store.finish_run(run_id, "FAILED", str(error))
                        return IncrementalRunSummary(
                            source, instrument, period, run_id, started_cursor, started_cursor,
                            0, 0, attempts, "FAILED", str(error),
                        )
                    if self.backoff_seconds:
                        sleep(self.backoff_seconds)

            raw_records = list(outcome.bars)
            self.store.write_bronze(run_id, source, raw_records)
            normalize_fn = normalize or (lambda record: [record])
            normalized: list[Mapping[str, Any]] = []
            for record in raw_records:
                normalized.extend(normalize_fn(record))
            normalized = _dedupe(normalized)

            written = 0
            if normalized:
                self.store.write_silver_bars(
                    partition_key,
                    normalized,
                    outcome.cursor or _now(),
                    run_id,
                )
                written = len(normalized)

            if outcome.cursor is not None:
                self.checkpoints.set_cursor(source, instrument, period, outcome.cursor)
            if outcome.partial_error:
                self.store.finish_run(run_id, "PARTIAL_FAILURE", outcome.partial_error)
                status = "PARTIAL_FAILURE"
            else:
                self.store.finish_run(run_id, "PASS")
                status = "PASS"
            return IncrementalRunSummary(
                source, instrument, period, run_id, started_cursor, outcome.cursor,
                len(raw_records), written, attempts, status, outcome.partial_error,
            )
        finally:
            self.checkpoints.release_lock(source, instrument, period, owner)


def _dedupe(bars: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[Mapping[str, Any]] = []
    for bar in bars:
        instrument = _instrument_id(bar.get("instrument_key"))
        key = (instrument, str(bar.get("period", "")), str(bar.get("bar_open_time", "")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(bar)
    return unique


def _instrument_id(value: Any) -> str:
    if isinstance(value, Mapping):
        return ".".join(str(value.get(part, "")) for part in ("country_or_market", "exchange", "asset_type", "code"))
    return str(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_stale_lock(locked_at: str, ttl_seconds: float) -> bool:
    try:
        locked = datetime.fromisoformat(locked_at)
    except ValueError:
        return True
    if locked.tzinfo is None:
        locked = locked.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - locked).total_seconds() > ttl_seconds
