"""Shared helpers for the research-terminal FastAPI tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import duckdb


def write_silver(data_root: Path, rows: Iterable[Mapping[str, Any]]) -> Path:
    """Write a small local silver parquet partition with the production schema."""
    path = Path(data_root) / "silver" / "fixture.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(":memory:")
    try:
        connection.execute(
            "CREATE TABLE bars ("
            "instrument_id VARCHAR, market VARCHAR, asset_type VARCHAR, "
            "period VARCHAR, bar_open_time VARCHAR, bar_json VARCHAR)"
        )
        for row in rows:
            payload = dict(row)
            connection.execute(
                "INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?)",
                [
                    str(payload["instrument_id"]),
                    str(payload["market"] or ""),
                    str(payload["asset_type"] or ""),
                    str(payload["period"] or "1d"),
                    str(payload["bar_open_time"]),
                    json.dumps(payload, ensure_ascii=False),
                ],
            )
        quoted = str(path).replace("'", "''")
        connection.execute(f"COPY bars TO '{quoted}' (FORMAT PARQUET)")
    finally:
        connection.close()
    return path


def write_gold_metrics(data_root: Path, rows: Iterable[Mapping[str, Any]]) -> Path:
    """Write a local catalog.duckdb with a minimal gold_metrics table."""
    catalog = Path(data_root) / "catalog.duckdb"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(catalog))
    try:
        connection.execute(
            "CREATE TABLE gold_metrics ("
            "instrument_id VARCHAR, trading_date VARCHAR, metric_name VARCHAR, "
            "value DOUBLE, metric_id VARCHAR)"
        )
        for row in rows:
            connection.execute(
                "INSERT INTO gold_metrics VALUES (?, ?, ?, ?, ?)",
                [
                    str(row["instrument_id"]),
                    str(row["trading_date"]),
                    str(row["metric_name"]),
                    float(row["value"]),
                    str(row["metric_id"]),
                ],
            )
    finally:
        connection.close()
    return catalog


def make_bar(
    instrument_id: str,
    day: str,
    *,
    market: str = "CN",
    asset_type: str = "STOCK",
    period: str = "1d",
    close: float = 10.0,
    open_: float = 10.0,
    high: float = 10.2,
    low: float = 9.8,
    volume: float = 1000.0,
    amount: float = 10000.0,
) -> dict[str, Any]:
    """Build one bar_json payload matching the local silver schema."""
    return {
        "instrument_id": instrument_id,
        "symbol": instrument_id.split(".")[-1],
        "name": f"fixture-{instrument_id}",
        "market": market,
        "asset_type": asset_type,
        "period": period,
        "trading_date": day,
        "bar_open_time": f"{day}T09:30:00",
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "amount": amount,
        "source": "fixture",
        "quality_status": "OK",
        "fetched_at": f"{day}T15:00:00+08:00",
    }


def silver_row(instrument_id: str, day: str, **kwargs: Any) -> dict[str, Any]:
    """Build one row for ``write_silver`` with required top-level columns."""
    payload = make_bar(instrument_id, day, **kwargs)
    return {
        "instrument_id": instrument_id,
        "market": payload["market"],
        "asset_type": payload["asset_type"],
        "period": payload["period"],
        "bar_open_time": payload["bar_open_time"],
        **payload,
    }

