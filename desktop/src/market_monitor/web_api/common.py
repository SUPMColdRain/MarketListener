"""Shared helpers for the research-terminal API routers.

Everything here is a thin, read-only adapter over the local silver parquet
partitions and JSON/JSONL personal files.  No arbitrary SQL, shell commands or
third-party network calls are performed by these helpers.
"""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500
MAX_BARS = 5000
DEFAULT_QUERY_TIMEOUT_SECONDS = 5.0

_FILE_LOCK = threading.RLock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_value(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        rounded = round(value, 6)
        return int(rounded) if rounded.is_integer() and abs(rounded) < 2**53 else rounded
    if isinstance(value, dict):
        return {str(key): _clean_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_value(item) for item in value]
    return value


def clean(value: Any) -> Any:
    """Recursively remove NaN/Infinity and normalize floats for JSON output."""
    return _clean_value(value)


def json_dumps(value: Any) -> str:
    return json.dumps(clean(value), ensure_ascii=False, separators=(",", ":"))


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def save_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json_dumps(payload) + "\n", encoding="utf-8")
    with _FILE_LOCK:
        temporary.replace(path)
    return path


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        return rows
    return rows


def append_jsonl(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _FILE_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json_dumps(dict(payload)) + "\n")
    return path


def silver_partitions(data_root: Path) -> list[Path]:
    return sorted(Path(data_root).joinpath("silver").rglob("*.parquet"))


def _inventory_key(data_root: Path) -> tuple[str, int, float]:
    files = silver_partitions(data_root)
    newest = 0.0
    for path in files:
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue
    return (str(data_root), len(files), newest)


@dataclass(frozen=True)
class SilverInventory:
    instruments: dict[str, dict[str, Any]]
    rows: int
    markets: dict[str, int]
    asset_types: dict[str, int]
    periods: list[str]
    latest_bar_at: str | None
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "instruments": len(self.instruments),
            "rows": self.rows,
            "markets": dict(self.markets),
            "assetTypes": dict(self.asset_types),
            "periods": list(self.periods),
            "latestBarAt": self.latest_bar_at,
            "generatedAt": self.generated_at,
        }


_inventory_cache: dict[tuple[str, int, float], SilverInventory] = {}


def load_inventory(data_root: Path, *, max_instruments: int = 1000) -> SilverInventory:
    """Read the silver parquet partitions and return a compact instrument index.

    The index is cached by partition fingerprint (path, file count, newest
    mtime) so repeated overview/list calls do not rescan the whole store.
    """
    key = _inventory_key(data_root)
    cached = _inventory_cache.get(key)
    if cached is not None:
        return cached
    files = silver_partitions(data_root)
    rows = 0
    markets: dict[str, int] = {}
    asset_types: dict[str, int] = {}
    periods: set[str] = set()
    instruments: dict[str, dict[str, Any]] = {}
    latest_bar_at: str | None = None
    if files:
        try:
            import duckdb

            connection = duckdb.connect(database=":memory:")
            try:
                query = (
                    f"SELECT instrument_id, market, asset_type, period, bar_open_time, bar_json "
                    f"FROM read_parquet({[str(path) for path in files]!r})"
                )
                for instrument_id, market, asset_type, period, bar_open_time, bar_json in connection.execute(query).fetchall():
                    rows += 1
                    key_id = str(instrument_id)
                    market = str(market or "")
                    asset_type = str(asset_type or "")
                    period = str(period or "")
                    markets[market] = markets.get(market, 0) + 1
                    asset_types[asset_type] = asset_types.get(asset_type, 0) + 1
                    if period:
                        periods.add(period)
                    if bar_open_time and (latest_bar_at is None or str(bar_open_time) > latest_bar_at):
                        latest_bar_at = str(bar_open_time)
                    existing = instruments.get(key_id)
                    if existing is None or str(bar_open_time or "") > str(existing.get("lastBarAt") or ""):
                        try:
                            payload = json.loads(str(bar_json))
                        except ValueError:
                            payload = {}
                        if not isinstance(payload, dict):
                            payload = {}
                        instruments[key_id] = {
                            "instrumentId": key_id,
                            "symbol": str(payload.get("symbol") or ""),
                            "name": str(payload.get("name") or ""),
                            "market": market,
                            "assetType": asset_type,
                            "period": period,
                            "lastClose": _clean_value(payload.get("close")),
                            "lastBarAt": str(bar_open_time or ""),
                            "source": str(payload.get("source") or ""),
                            "qualityStatus": str(payload.get("quality_status") or ""),
                            "updatedAt": str(payload.get("fetched_at") or ""),
                        }
            finally:
                connection.close()
        except ImportError:
            return SilverInventory({}, 0, {}, {}, [], None, now_iso())
        except Exception:
            return SilverInventory({}, 0, {}, {}, [], None, now_iso())
    ordered = dict(sorted(instruments.items())[:max_instruments])
    inventory = SilverInventory(
        instruments=ordered,
        rows=rows,
        markets=markets,
        asset_types=asset_types,
        periods=sorted(periods),
        latest_bar_at=latest_bar_at,
        generated_at=now_iso(),
    )
    _inventory_cache[key] = inventory
    return inventory


def read_bars(
    data_root: Path,
    instrument_id: str,
    *,
    period: str | None = None,
    limit: int = 1000,
    timeout_seconds: float = DEFAULT_QUERY_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Return ascending K-line bars for one instrument from local silver parquet."""
    files = silver_partitions(data_root)
    if not files:
        return []
    limit = max(1, min(int(limit), MAX_BARS))
    clauses = ["instrument_id = ?"]
    parameters: list[Any] = [instrument_id]
    if period:
        clauses.append("period = ?")
        parameters.append(period)
    where = " AND ".join(clauses)
    query = (
        f"SELECT bar_json FROM read_parquet({[str(path) for path in files]!r}) "
        f"WHERE {where} ORDER BY bar_open_time DESC LIMIT {limit}"
    )
    bars: list[dict[str, Any]] = []
    try:
        import duckdb

        connection = duckdb.connect(database=":memory:")
        try:
            for (bar_json,) in connection.execute(query, parameters).fetchall():
                try:
                    payload = json.loads(str(bar_json))
                except ValueError:
                    continue
                if not isinstance(payload, dict):
                    continue
                payload.setdefault("instrument_id", instrument_id)
                bars.append(clean(payload))
        finally:
            connection.close()
    except (ImportError, Exception):
        return []
    bars.sort(key=lambda bar: str(bar.get("bar_open_time") or ""))
    return bars[-limit:]


def bars_by_instrument(
    data_root: Path,
    *,
    period: str | None = None,
    limit_per_instrument: int = 500,
    max_instruments: int = 500,
) -> dict[str, list[dict[str, Any]]]:
    """Group local silver bars by instrument for strategy scans and dashboards."""
    files = silver_partitions(data_root)
    if not files:
        return {}
    parameters: list[Any] = []
    clause = ""
    if period:
        clause = "WHERE period = ?"
        parameters.append(period)
    query = (
        f"SELECT instrument_id, bar_json FROM read_parquet({[str(path) for path in files]!r}) {clause}"
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    try:
        import duckdb

        connection = duckdb.connect(database=":memory:")
        try:
            for instrument_id, bar_json in connection.execute(query, parameters).fetchall():
                try:
                    payload = json.loads(str(bar_json))
                except ValueError:
                    continue
                if not isinstance(payload, dict):
                    continue
                grouped.setdefault(str(instrument_id), []).append(clean(payload))
        finally:
            connection.close()
    except Exception:
        return {}
    for instrument_id, bars in grouped.items():
        bars.sort(key=lambda bar: str(bar.get("bar_open_time") or ""))
        grouped[instrument_id] = bars[-limit_per_instrument:]
    return dict(list(grouped.items())[:max_instruments])


def paginate(items: Sequence[Any], page: int, page_size: int) -> dict[str, Any]:
    total = len(items)
    start = (max(1, page) - 1) * page_size
    return {
        "items": list(items[start : start + page_size]),
        "total": total,
        "page": max(1, page),
        "pageSize": page_size,
    }


__all__ = (
    "DEFAULT_PAGE_SIZE",
    "MAX_BARS",
    "MAX_PAGE_SIZE",
    "SilverInventory",
    "append_jsonl",
    "bars_by_instrument",
    "clean",
    "json_dumps",
    "load_inventory",
    "load_json",
    "load_jsonl",
    "now_iso",
    "paginate",
    "read_bars",
    "save_json",
    "silver_partitions",
)
