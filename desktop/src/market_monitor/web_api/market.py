"""/api/market router: local silver overview, instruments, and K-line bars.

This router is a thin adapter over the local silver parquet partitions.  It
only reads data already stored under ``data_control/silver`` and never
executes arbitrary SQL, shell commands or third-party requests.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from market_monitor.aggregation import aggregate_bars, aggregate_daily_bars

from .common import DEFAULT_PAGE_SIZE, MAX_BARS, MAX_PAGE_SIZE, clean, load_inventory, paginate, read_bars
from .sources import local_inventory

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


_RAW_PERIODS = ("1m", "5m", "15m", "30m", "1h", "1d", "1w", "1mo")
_MINUTE_DERIVATIVES = {"1h": 60, "2h": 120, "4h": 240}
_MINUTE_SOURCES = ("1m", "5m", "15m", "30m")


def _session_rule(bar: dict[str, Any]) -> str | None:
    market = str(bar.get("market") or "").upper()
    asset_type = str(bar.get("asset_type") or "").upper()
    if market == "HK":
        return "HK_STOCK"
    if market == "CN" and asset_type == "FUTURE":
        return "CN_FUTURE"
    if market == "CN" and asset_type in {"STOCK", "ETF", "INDEX"}:
        return "CN_STOCK"
    return None


def _bar_with_close_time(bar: dict[str, Any]) -> dict[str, Any]:
    """Make older Silver bars usable by the aggregation contract without guessing OHLC."""
    if bar.get("bar_close_time"):
        return bar
    period = str(bar.get("period") or "")
    minutes = {"1m": 1, "5m": 5, "15m": 15, "30m": 30}.get(period)
    if minutes is None:
        return bar
    try:
        opened = datetime.fromisoformat(str(bar["bar_open_time"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return bar
    result = dict(bar)
    result["bar_close_time"] = (opened + timedelta(minutes=minutes)).isoformat()
    return result


def _daily_bar_for_aggregate(bar: dict[str, Any]) -> dict[str, Any]:
    """Bridge legacy Silver names for a read-time weekly/monthly projection."""
    result = dict(bar)
    result.setdefault("trading_day", result.get("trading_date") or str(result.get("bar_open_time") or "")[:10])
    # Old daily rows did not retain a close timestamp.  Preserve their source
    # timestamp rather than inventing an exchange-close time at read time.
    result.setdefault("bar_close_time", result.get("bar_open_time"))
    return result


def _raw_periods_for_instrument(data_root: Path, instrument_id: str) -> list[str]:
    return [period for period in _RAW_PERIODS if read_bars(data_root, instrument_id, period=period, limit=1)]


def _available_periods(data_root: Path, instrument_id: str) -> list[str]:
    raw = _raw_periods_for_instrument(data_root, instrument_id)
    available = set(raw)
    if "1d" in raw:
        available.update({"1w", "1mo"})
    minute_source = next((period for period in _MINUTE_SOURCES if period in raw), None)
    if minute_source:
        probe = read_bars(data_root, instrument_id, period=minute_source, limit=1)
        if probe and _session_rule(probe[0]):
            available.update(_MINUTE_DERIVATIVES)
    order = ("1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w", "1mo")
    return [period for period in order if period in available]


def _derived_bars(data_root: Path, instrument_id: str, period: str) -> list[dict[str, Any]]:
    if period in {"1w", "1mo"}:
        daily = read_bars(data_root, instrument_id, period="1d", limit=MAX_BARS)
        normalized = [_daily_bar_for_aggregate(bar) for bar in daily]
        return aggregate_daily_bars(normalized, period) if normalized else []
    minutes = _MINUTE_DERIVATIVES.get(period)
    if minutes is None:
        return []
    source = next(
        (candidate for candidate in _MINUTE_SOURCES if read_bars(data_root, instrument_id, period=candidate, limit=1)),
        None,
    )
    if source is None:
        return []
    bars = [_bar_with_close_time(bar) for bar in read_bars(data_root, instrument_id, period=source, limit=MAX_BARS)]
    if not bars:
        return []
    rule = _session_rule(bars[0])
    return aggregate_bars(bars, minutes, rule) if rule else []


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


@router.get("/groups")
def market_groups(request: Request) -> dict[str, Any]:
    """Return actual Silver coverage grouped for the client market view."""
    items = local_inventory(_data_root(request))
    return clean({"items": items, "total": len(items)})


@router.get("/instruments")
def market_instruments(
    request: Request,
    market: str | None = None,
    asset_type: str | None = Query(default=None, alias="assetType"),
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
) -> dict[str, Any]:
    """Paginate the local instrument index, optionally filtered by market/q."""
    items = list(load_inventory(_data_root(request)).instruments.values())
    if market:
        wanted = market.strip().casefold()
        items = [item for item in items if str(item.get("market") or "").casefold() == wanted]
    if asset_type:
        wanted_type = asset_type.strip().casefold()
        items = [item for item in items if str(item.get("assetType") or "").casefold() == wanted_type]
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
    available_periods = _available_periods(data_root, instrument_id)
    selected_period = period or str(instrument.get("period") or "1d")
    if selected_period not in available_periods:
        raise HTTPException(status_code=400, detail=f"unknown period: {selected_period}")
    bars = read_bars(data_root, instrument_id, period=selected_period, limit=limit)
    if not bars:
        bars = _derived_bars(data_root, instrument_id, selected_period)[-limit:]
    camel_bars = [{_camel_key(key): value for key, value in bar.items()} for bar in bars]
    return clean(
        {
            "instrumentId": instrument_id,
            "period": selected_period,
            "availablePeriods": available_periods,
            "bars": camel_bars,
            "total": len(camel_bars),
            "lastBarAt": camel_bars[-1].get("barOpenTime") if camel_bars else None,
        }
    )


__all__ = ("router",)
