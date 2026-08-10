"""/api/personal/watchlist router: local watchlist persistence.

The watchlist is stored as ``data_control/personal/watchlist.json``.  This
router never writes to ``catalog.duckdb`` and relies on the web_app loopback
middleware to block remote POST/DELETE requests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from .common import clean, load_inventory, load_json, now_iso, save_json

router = APIRouter(prefix="/api/personal", tags=["personal"])

# 生产环境默认数据根目录；测试或其他宿主可通过 ``app.state.data_root`` 覆盖。
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_DATA_ROOT = _REPO_ROOT / "data_control"


def _data_root(request: Request) -> Path:
    configured = getattr(request.app.state, "data_root", None)
    if configured:
        return Path(configured)
    return _DEFAULT_DATA_ROOT


def _watchlist_path(data_root: Path) -> Path:
    return data_root / "personal" / "watchlist.json"


def _load_entries(data_root: Path) -> list[dict[str, Any]]:
    payload = load_json(_watchlist_path(data_root), default=None)
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    entries: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entries.append(
            {
                "instrumentId": str(item.get("instrumentId") or ""),
                "addedAt": str(item.get("addedAt") or ""),
                "note": str(item.get("note") or ""),
            }
        )
    return entries


def _save_entries(data_root: Path, entries: list[dict[str, Any]]) -> None:
    save_json(_watchlist_path(data_root), {"items": entries})


class WatchlistItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instrumentId: str
    note: str = ""


@router.get("/watchlist")
def get_watchlist(request: Request) -> dict[str, Any]:
    return clean({"items": _load_entries(_data_root(request))})


@router.post("/watchlist")
def add_watchlist(request: Request, body: WatchlistItemIn) -> dict[str, Any]:
    """Add an instrument to the watchlist; duplicates return the existing entry."""
    data_root = _data_root(request)
    inventory = load_inventory(data_root)
    instrument_id = body.instrumentId.strip()
    if instrument_id not in inventory.instruments:
        raise HTTPException(status_code=400, detail="instrument not found in silver inventory")
    entries = _load_entries(data_root)
    existing = next((entry for entry in entries if entry.get("instrumentId") == instrument_id), None)
    if existing is not None:
        return clean({"item": existing})
    entry = {"instrumentId": instrument_id, "addedAt": now_iso(), "note": body.note}
    entries.append(entry)
    _save_entries(data_root, entries)
    return clean({"item": entry})


@router.delete("/watchlist/{instrument_id}")
def delete_watchlist(instrument_id: str, request: Request) -> dict[str, Any]:
    """Remove one watchlist entry; missing entries return 404."""
    data_root = _data_root(request)
    entries = _load_entries(data_root)
    removed = next((entry for entry in entries if entry.get("instrumentId") == instrument_id), None)
    if removed is None:
        raise HTTPException(status_code=404, detail="watchlist item not found")
    remaining = [entry for entry in entries if entry.get("instrumentId") != instrument_id]
    _save_entries(data_root, remaining)
    return clean({"item": removed})


__all__ = ("router",)
