"""Local data-source inventory and routing-preference API.

The router deliberately distinguishes three facts: providers implemented in
this repository, rows currently present in local Silver storage, and routing
preferences chosen by the local administrator.  A preference never claims an
unconfigured commercial provider is usable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .common import clean, load_json, now_iso, save_json, silver_partitions

router = APIRouter(prefix="/api/data-sources", tags=["data-sources"])


# These are repository facts, not a catalogue of vendors the product might
# support in the future. Endpoint text comes from the adapters/collector.
_PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        "providerId": "pytdx",
        "name": "通达信 pytdx",
        "type": "protocol_adapter",
        "access": "TDX TCP quote protocol",
        "endpoint": "TDX_SERVERS (default public hosts, TCP/7709)",
        "authentication": "none",
        "implemented": True,
        "configured": True,
        "priority": 10,
        "enabled": True,
        "markets": ["CN"],
        "assetTypes": ["STOCK", "ETF", "INDEX"],
        "periods": ["1m", "5m", "15m", "30m", "1h", "1d", "1w", "1mo"],
        "fields": ["open", "high", "low", "close", "volume"],
        "status": "IMPLEMENTED_UNVERIFIED",
    },
    {
        "providerId": "akshare",
        "name": "AKShare",
        "type": "sdk_adapter",
        "access": "Python AKShare SDK; upstream varies by function",
        "endpoint": "AKShare functions (stock_hk_hist, futures_main_sina, futures_index_ccidx and others)",
        "authentication": "none for current collector calls",
        "implemented": True,
        "configured": True,
        "priority": 20,
        "enabled": True,
        "markets": ["CN", "HK", "GLOBAL"],
        "assetTypes": ["STOCK", "INDEX", "FUTURE", "MACRO"],
        "periods": ["1d"],
        "fields": ["open", "high", "low", "close", "volume", "amount", "open_interest"],
        "status": "IMPLEMENTED_UNVERIFIED",
    },
    {
        "providerId": "baostock",
        "name": "Baostock",
        "type": "sdk_adapter",
        "access": "Python baostock SDK",
        "endpoint": "baostock.login / query_history_k_data_plus",
        "authentication": "account-free SDK login",
        "implemented": True,
        "configured": True,
        "priority": 30,
        "enabled": True,
        "markets": ["CN"],
        "assetTypes": ["STOCK"],
        "periods": ["1d", "30m"],
        "fields": ["open", "high", "low", "close", "volume", "amount"],
        "status": "IMPLEMENTED_UNVERIFIED",
    },
    {
        "providerId": "joinquant",
        "name": "JQData / 聚宽",
        "type": "sdk_adapter",
        "access": "jqdatasdk",
        "endpoint": "jqdatasdk.auth and price APIs",
        "authentication": "JQDATA_USERNAME + JQDATA_PASSWORD required",
        "implemented": True,
        "configured": False,
        "priority": 90,
        "enabled": False,
        "markets": ["CN"],
        "assetTypes": ["STOCK", "ETF", "INDEX", "FUTURE"],
        "periods": ["1m", "30m", "1d"],
        "fields": ["open", "high", "low", "close", "volume", "money"],
        "status": "BLOCKED_CONFIGURATION",
    },
    {
        "providerId": "tushare",
        "name": "Tushare Pro",
        "type": "sdk_adapter",
        "access": "tushare.pro_api",
        "endpoint": "TUSHARE_TOKEN + Pro endpoints daily/stk_mins/stock_basic",
        "authentication": "TUSHARE_TOKEN and endpoint entitlement required",
        "implemented": True,
        "configured": False,
        "priority": 90,
        "enabled": False,
        "markets": ["CN"],
        "assetTypes": ["STOCK", "ETF", "INDEX"],
        "periods": ["1m", "1d"],
        "fields": ["open", "high", "low", "close", "vol", "amount"],
        "status": "BLOCKED_CONFIGURATION",
    },
    {
        "providerId": "binance",
        "name": "Binance public data",
        "type": "http_adapter",
        "access": "HTTPS JSON",
        "endpoint": "https://data-api.binance.vision/api/v3/klines",
        "authentication": "none for current public endpoint",
        "implemented": True,
        "configured": True,
        "priority": 20,
        "enabled": True,
        "markets": ["GLOBAL"],
        "assetTypes": ["CRYPTO"],
        "periods": ["1d"],
        "fields": ["open", "high", "low", "close", "volume", "amount"],
        "status": "IMPLEMENTED_UNVERIFIED",
    },
    {
        "providerId": "eastmoney_cboe",
        "name": "东方财富 / CBOE",
        "type": "http_adapter",
        "access": "HTTPS JSON and CSV with Tencent fallback",
        "endpoint": "https://push2his.eastmoney.com/api/qt/stock/kline/get; https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
        "authentication": "none for current public endpoints",
        "implemented": True,
        "configured": True,
        "priority": 20,
        "enabled": True,
        "markets": ["GLOBAL"],
        "assetTypes": ["MACRO", "INDEX"],
        "periods": ["1d"],
        "fields": ["date", "close"],
        "status": "IMPLEMENTED_UNVERIFIED",
    },
)

_PROVIDERS_BY_ID = {str(provider["providerId"]): provider for provider in _PROVIDERS}


class RoutingPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: str | None = Field(default=None, max_length=120)
    fallback1: str | None = Field(default=None, max_length=120)
    fallback2: str | None = Field(default=None, max_length=120)


class RoutingPreferencesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferences: dict[str, RoutingPreference]


def _data_root(request: Request) -> Path:
    return Path(request.app.state.data_root)


def _preference_path(data_root: Path) -> Path:
    return data_root / "data_source_preferences.json"


def _category_key(market: str, asset_type: str, period: str) -> str:
    return f"{market}:{asset_type}:{period}"


def _provider_for_source(source: str) -> str:
    value = source.casefold()
    if value.startswith("pytdx"):
        return "pytdx"
    if value.startswith("akshare") or value.startswith("sina-"):
        return "akshare"
    if value.startswith("binance"):
        return "binance"
    if "eastmoney" in value or "cboe" in value or value.startswith("tencent"):
        return "eastmoney_cboe"
    if value.startswith("baostock"):
        return "baostock"
    if value.startswith("joinquant") or value.startswith("jqdata"):
        return "joinquant"
    if value.startswith("tushare"):
        return "tushare"
    return source or "unknown"


def _source_details(source_ids: set[str]) -> list[dict[str, Any]]:
    """Expose the exact registered access path behind each stored source id."""
    details: list[dict[str, Any]] = []
    for provider_id in sorted(source_ids):
        provider = _PROVIDERS_BY_ID.get(provider_id)
        if provider is None:
            details.append(
                {
                    "providerId": provider_id,
                    "name": provider_id,
                    "endpoint": None,
                    "status": "UNREGISTERED_SOURCE",
                    "periods": [],
                    "fields": [],
                }
            )
            continue
        details.append(
            {
                "providerId": provider_id,
                "name": provider["name"],
                "endpoint": provider["endpoint"],
                "status": provider["status"],
                "periods": provider["periods"],
                "fields": provider["fields"],
            }
        )
    return details


def _local_inventory(data_root: Path) -> tuple[list[dict[str, Any]], int]:
    """Return category-level facts by reading actual local Silver rows."""
    files = silver_partitions(data_root)
    if not files:
        return [], 0
    try:
        import duckdb

        connection = duckdb.connect(database=":memory:")
        try:
            source = repr([str(path) for path in files])
            unique_instruments = int(
                connection.execute(f"SELECT count(DISTINCT instrument_id) FROM read_parquet({source})").fetchone()[0]
            )
            rows = connection.execute(
                "SELECT "
                "coalesce(nullif(market, ''), split_part(instrument_id, '.', 1), 'UNKNOWN') AS market, "
                "coalesce(nullif(asset_type, ''), split_part(instrument_id, '.', 3), 'UNKNOWN') AS asset_type, "
                "coalesce(nullif(period, ''), 'UNKNOWN') AS period, "
                "count(*) AS rows, count(DISTINCT instrument_id) AS instruments, "
                "min(bar_open_time) AS earliest_bar_at, max(bar_open_time) AS latest_bar_at, "
                "max(json_extract_string(bar_json, '$.fetched_at')) AS last_updated_at, "
                "list(DISTINCT coalesce(nullif(json_extract_string(bar_json, '$.source'), ''), 'unknown')) AS sources, "
                "histogram(coalesce(nullif(json_extract_string(bar_json, '$.quality_status'), ''), 'UNKNOWN')) AS quality, "
                "sum(CASE WHEN json_extract(bar_json, '$.open') IS NOT NULL AND json_extract(bar_json, '$.open') != 'null' THEN 1 ELSE 0 END) AS open_count, "
                "sum(CASE WHEN json_extract(bar_json, '$.high') IS NOT NULL AND json_extract(bar_json, '$.high') != 'null' THEN 1 ELSE 0 END) AS high_count, "
                "sum(CASE WHEN json_extract(bar_json, '$.low') IS NOT NULL AND json_extract(bar_json, '$.low') != 'null' THEN 1 ELSE 0 END) AS low_count, "
                "sum(CASE WHEN json_extract(bar_json, '$.close') IS NOT NULL AND json_extract(bar_json, '$.close') != 'null' THEN 1 ELSE 0 END) AS close_count, "
                "sum(CASE WHEN json_extract(bar_json, '$.volume') IS NOT NULL AND json_extract(bar_json, '$.volume') != 'null' THEN 1 ELSE 0 END) AS volume_count, "
                "sum(CASE WHEN json_extract(bar_json, '$.amount') IS NOT NULL AND json_extract(bar_json, '$.amount') != 'null' THEN 1 ELSE 0 END) AS amount_count, "
                "sum(CASE WHEN json_extract(bar_json, '$.open_interest') IS NOT NULL AND json_extract(bar_json, '$.open_interest') != 'null' THEN 1 ELSE 0 END) AS open_interest_count, "
                "sum(CASE WHEN json_extract(bar_json, '$.pct_change') IS NOT NULL AND json_extract(bar_json, '$.pct_change') != 'null' THEN 1 ELSE 0 END) AS pct_change_count, "
                "sum(CASE WHEN json_extract(bar_json, '$.amplitude') IS NOT NULL AND json_extract(bar_json, '$.amplitude') != 'null' THEN 1 ELSE 0 END) AS amplitude_count "
                f"FROM read_parquet({source}) GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"
            ).fetchall()
        finally:
            connection.close()
    except Exception:
        return [], 0
    result: list[dict[str, Any]] = []
    for row in rows:
        (
            market, asset_type, period, total, instruments, earliest_bar_at, latest_bar_at, last_updated_at,
            sources, quality, *field_counts,
        ) = row
        total = max(1, int(total))
        quality = {str(status): int(count) for status, count in dict(quality or {}).items()}
        source_ids = {_provider_for_source(str(value)) for value in sources if value}
        counts = dict(zip(("open", "high", "low", "close", "volume", "amount", "open_interest", "pct_change", "amplitude"), field_counts))
        key = _category_key(str(market), str(asset_type), str(period))
        result.append(
            {
                "categoryKey": key,
                "market": str(market),
                "assetType": str(asset_type),
                "period": str(period),
                "instruments": int(instruments),
                "rows": total,
                "earliestBarAt": str(earliest_bar_at) if earliest_bar_at else None,
                "latestBarAt": str(latest_bar_at) if latest_bar_at else None,
                "lastUpdatedAt": str(last_updated_at) if last_updated_at else None,
                "sources": sorted(source_ids),
                "sourceDetails": _source_details(source_ids),
                "quality": dict(sorted(quality.items())),
                "fieldCompleteness": {name: round(int(value or 0) / total, 4) for name, value in sorted(counts.items())},
            }
        )
    return result, unique_instruments


def local_inventory(data_root: Path) -> list[dict[str, Any]]:
    """Return only category-level facts for callers that do not need totals."""
    inventory, _ = _local_inventory(data_root)
    return inventory


@router.get("")
def data_sources(request: Request) -> dict[str, Any]:
    root = _data_root(request)
    preferences = load_json(_preference_path(root), {"preferences": {}})
    stored = preferences.get("preferences", {}) if isinstance(preferences, dict) else {}
    inventory, unique_instruments = _local_inventory(root)
    return clean(
        {
            "generatedAt": now_iso(),
            "providers": list(_PROVIDERS),
            "inventory": inventory,
            "preferences": stored,
            "summary": {
                "categories": len(inventory),
                "rows": sum(int(item["rows"]) for item in inventory),
                "instruments": unique_instruments,
            },
        }
    )


@router.put("")
def save_routing_preferences(request: Request, body: RoutingPreferencesRequest) -> dict[str, Any]:
    root = _data_root(request)
    known = {item["providerId"] for item in _PROVIDERS}
    preferences: dict[str, dict[str, str | None]] = {}
    for category, value in body.preferences.items():
        if not category or len(category) > 200:
            raise HTTPException(status_code=400, detail="invalid category key")
        current = value.model_dump()
        # Custom text is accepted and explicitly labelled by the UI/API; known
        # identifiers are never promoted to configured/usable here.
        for provider_id in current.values():
            if provider_id and provider_id in known:
                continue
        preferences[category] = current
    payload = {"updatedAt": now_iso(), "preferences": preferences}
    save_json(_preference_path(root), payload)
    return clean(payload)


__all__ = ("local_inventory", "router")
