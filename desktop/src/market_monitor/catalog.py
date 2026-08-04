"""Versioned canonical-instrument catalogue and source-symbol mappings."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class InstrumentKey:
    country_or_market: str
    exchange: str
    asset_type: str
    code: str

    def as_id(self) -> str:
        return ".".join((self.country_or_market, self.exchange, self.asset_type, self.code))


@dataclass(frozen=True)
class Instrument:
    key: InstrumentKey
    display_name: str
    currency: str
    timezone: str


class InstrumentCatalog:
    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def upsert_instrument(self, instrument: Instrument) -> None:
        self.connection.execute(
            """INSERT INTO instruments (instrument_id, country_or_market, exchange, asset_type, code, display_name, currency, timezone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(instrument_id) DO UPDATE SET display_name=excluded.display_name, currency=excluded.currency, timezone=excluded.timezone""",
            (
                instrument.key.as_id(), instrument.key.country_or_market, instrument.key.exchange,
                instrument.key.asset_type, instrument.key.code, instrument.display_name,
                instrument.currency, instrument.timezone,
            ),
        )
        self.connection.commit()

    def add_source_mapping(
        self, provider: str, source_symbol: str, key: InstrumentKey, effective_from: date, effective_to: date | None = None
    ) -> None:
        self.connection.execute(
            """INSERT INTO source_mappings (provider, source_symbol, instrument_id, effective_from, effective_to)
            VALUES (?, ?, ?, ?, ?)""",
            (provider, source_symbol, key.as_id(), effective_from.isoformat(), effective_to.isoformat() if effective_to else None),
        )
        self.connection.commit()

    def resolve_source_symbol(self, provider: str, source_symbol: str, on_date: date) -> InstrumentKey | None:
        row = self.connection.execute(
            """SELECT country_or_market, exchange, asset_type, code FROM source_mappings
            JOIN instruments USING (instrument_id)
            WHERE provider=? AND source_symbol=? AND effective_from<=? AND (effective_to IS NULL OR effective_to>=?)
            ORDER BY effective_from DESC LIMIT 1""",
            (provider, source_symbol, on_date.isoformat(), on_date.isoformat()),
        ).fetchone()
        return InstrumentKey(row["country_or_market"], row["exchange"], row["asset_type"], row["code"]) if row else None

    def save_universe_rule(self, scope_id: str, version: int, effective_at: date, definition: dict[str, object]) -> None:
        self.connection.execute(
            """INSERT INTO universe_rules (scope_id, version, effective_at, definition_json)
            VALUES (?, ?, ?, ?)""",
            (scope_id, version, effective_at.isoformat(), json.dumps(definition, sort_keys=True)),
        )
        self.connection.commit()

    def add_universe_member(self, scope_id: str, version: int, key: InstrumentKey, effective_from: date, effective_to: date | None = None) -> None:
        self.connection.execute(
            """INSERT INTO universe_members (scope_id, version, instrument_id, effective_from, effective_to)
            VALUES (?, ?, ?, ?, ?)""",
            (scope_id, version, key.as_id(), effective_from.isoformat(), effective_to.isoformat() if effective_to else None),
        )
        self.connection.commit()

    def resolve_universe(self, scope_id: str, version: int, on_date: date) -> list[InstrumentKey]:
        rows = self.connection.execute(
            """SELECT country_or_market, exchange, asset_type, code FROM universe_members
            JOIN instruments USING (instrument_id)
            WHERE scope_id=? AND version=? AND effective_from<=? AND (effective_to IS NULL OR effective_to>=?)
            ORDER BY instrument_id""",
            (scope_id, version, on_date.isoformat(), on_date.isoformat()),
        ).fetchall()
        return [InstrumentKey(row["country_or_market"], row["exchange"], row["asset_type"], row["code"]) for row in rows]

    def _create_schema(self) -> None:
        self.connection.executescript(
            """CREATE TABLE IF NOT EXISTS instruments (
                instrument_id TEXT PRIMARY KEY, country_or_market TEXT NOT NULL, exchange TEXT NOT NULL,
                asset_type TEXT NOT NULL, code TEXT NOT NULL, display_name TEXT NOT NULL, currency TEXT NOT NULL, timezone TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_mappings (
                provider TEXT NOT NULL, source_symbol TEXT NOT NULL, instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
                effective_from TEXT NOT NULL, effective_to TEXT, PRIMARY KEY (provider, source_symbol, effective_from)
            );
            CREATE TABLE IF NOT EXISTS universe_rules (
                scope_id TEXT NOT NULL, version INTEGER NOT NULL, effective_at TEXT NOT NULL, definition_json TEXT NOT NULL,
                PRIMARY KEY (scope_id, version)
            );
            CREATE TABLE IF NOT EXISTS universe_members (
                scope_id TEXT NOT NULL, version INTEGER NOT NULL, instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
                effective_from TEXT NOT NULL, effective_to TEXT, PRIMARY KEY (scope_id, version, instrument_id, effective_from)
            );"""
        )
        self.connection.commit()
