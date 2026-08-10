"""/api/market router: local silver overview, instruments, and K-line bars.

This router is a thin adapter over the local silver parquet partitions.  It
only reads data already stored under ``data_control/silver`` and never
executes arbitrary SQL, shell commands or third-party requests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .common import DEFAULT_PAGE_SIZE, MAX_BARS, MAX_PAGE_SIZE, clean, load_inventory, paginate, read_bars

router = APIRouter(prefix="/api/market", tags=["market"])

# 生产环境默认数据根目录；测试或其他宿主可通过 ``app.state.data_root`` 覆盖。
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_DATA_ROOT = _REPO_ROOT / "data_control"


def _data_root(request: Request) -> Path:
    configured = getattr(request.app.state, "data_root", None)
    if configured:
        return Path(configured)
    return _DEFAULT_DATA_ROOT


def _camel_key(key: str) -> str:
    """Convert one snake_case JSON key to camelCase."""
    head, *parts = key.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in parts)


def _overview(data_root: Path) -> dict[str, Any]:
    """Build the market overview from the silver inventory index."""
    inventory = load_inventory(data_root)
    markets: dict[str, int] = {}
    asset_types: dict[str, int] = {}
    for item in inventory.instruments.values():
        market = str(item.get("market") or "")
        asset_type = str(item.get("assetType") or "")
        markets[market] = markets.get(market, 0) + 1
        asset_types[asset_type] = asset_types.get(asset_type, 0) + 1
    return {
        "generatedAt": inventory.generated_at,
        "instruments": len(inventory.instruments),
        "rows": inventory.rows,
        "markets": markets,
        "assetTypes": asset_types,
        "periods": list(inventory.periods),
        "latestBarAt": inventory.latest_bar_at,
    }


@router.get("/overview")
def market_overview(request: Request) -> dict[str, Any]:
    return clean(_overview(_data_root(request)))


@router.get("/instruments")
def market_instruments(
    request: Request,
    market: str | None = None,
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
) -> dict[str, Any]:
    """Paginate the local instrument index, optionally filtered by market/q."""
    items = list(load_inventory(_data_root(request)).instruments.values())
    if market:
        wanted = market.strip().casefold()
        items = [item for item in items if str(item.get("market") or "").casefold() == wanted]
    keyword = q.strip().casefold()
    if keyword:
        items = [
            item
            for item in items
            if keyword in str(item.get("instrumentId") or "").casefold()
            or keyword in str(item.get("symbol") or "").casefold()
            or keyword in str(item.get("name") or "").casefold()
        ]
    return clean(paginate(items, page, page_size))


@router.get("/instruments/{instrument_id}/bars")
def market_bars(
    instrument_id: str,
    request: Request,
    period: str | None = None,
    limit: int = Query(default=1000, ge=1, le=MAX_BARS),
) -> dict[str, Any]:
    """Return ascending K-line bars for one local instrument."""
    data_root = _data_root(request)
    inventory = load_inventory(data_root)
    instrument = inventory.instruments.get(instrument_id)
    if instrument is None:
        raise HTTPException(status_code=404, detail="instrument not found")
    selected_period = period or str(instrument.get("period") or "1d")
    if selected_period not in inventory.periods:
        raise HTTPException(status_code=400, detail=f"unknown period: {selected_period}")
    bars = read_bars(data_root, instrument_id, period=selected_period, limit=limit)
    camel_bars = [{_camel_key(key): value for key, value in bar.items()} for bar in bars]
    return clean(
        {
            "instrumentId": instrument_id,
            "period": selected_period,
            "bars": camel_bars,
            "total": len(camel_bars),
            "lastBarAt": camel_bars[-1].get("barOpenTime") if camel_bars else None,
        }
    )


__all__ = ("router",)
