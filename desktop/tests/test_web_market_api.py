"""API tests for /api/market and /api/personal/watchlist."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from market_monitor.web_app import create_web_app
from web_fixtures import silver_row, write_silver


def _data_root(tmp_path: Path) -> Path:
    data_root = tmp_path / "data"
    write_silver(
        data_root,
        [
            silver_row("CN.SSE.STOCK.600519", "2026-08-06", close=1510.0),
            silver_row("CN.SSE.STOCK.600519", "2026-08-07", close=1520.0),
            silver_row("HK.HKEX.STOCK.00700", "2026-08-07", market="HK", close=480.0),
            silver_row(
                "CN.SHFE.FUTURE.AU0",
                "2026-08-07",
                market="CN",
                asset_type="FUTURE",
                period="30m",
                close=780.0,
            ),
        ],
    )
    return data_root


def _app(tmp_path: Path) -> tuple[FastAPI, TestClient]:
    application = create_web_app(_data_root(tmp_path))
    return application, TestClient(application, client=("127.0.0.1", 50000))


def test_market_overview_is_local_and_compact(tmp_path: Path) -> None:
    _application, client = _app(tmp_path)
    response = client.get("/api/market/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["instruments"] == 3
    assert payload["rows"] == 4
    assert payload["markets"] == {"CN": 2, "HK": 1}
    assert payload["assetTypes"] == {"STOCK": 2, "FUTURE": 1}
    assert payload["periods"] == ["1d", "30m"]
    assert "NaN" not in response.text
    assert "undefined" not in response.text


def test_market_instruments_paginate_search_and_filter(tmp_path: Path) -> None:
    _application, client = _app(tmp_path)
    first = client.get("/api/market/instruments", params={"pageSize": 2, "page": 1})
    assert first.status_code == 200
    body = first.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2

    second = client.get("/api/market/instruments", params={"pageSize": 2, "page": 2})
    assert len(second.json()["items"]) == 1

    search = client.get("/api/market/instruments", params={"q": "600519"})
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["instrumentId"] == "CN.SSE.STOCK.600519"

    hk = client.get("/api/market/instruments", params={"market": "HK"})
    assert hk.json()["total"] == 1
    assert hk.json()["items"][0]["instrumentId"] == "HK.HKEX.STOCK.00700"


def test_market_bars_are_ascending_bounded_and_camel_cased(tmp_path: Path) -> None:
    _application, client = _app(tmp_path)
    response = client.get(
        "/api/market/instruments/CN.SSE.STOCK.600519/bars",
        params={"period": "1d", "limit": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["instrumentId"] == "CN.SSE.STOCK.600519"
    assert body["total"] == 1
    assert body["bars"][0]["barOpenTime"] == "2026-08-07T09:30:00"
    assert body["bars"][0]["tradingDate"] == "2026-08-07"
    assert body["bars"][0]["qualityStatus"] == "OK"
    assert body["bars"][0]["instrumentId"] == "CN.SSE.STOCK.600519"
    assert body["lastBarAt"] == "2026-08-07T09:30:00"

    all_bars = client.get(
        "/api/market/instruments/CN.SSE.STOCK.600519/bars",
        params={"period": "1d"},
    ).json()["bars"]
    times = [bar["barOpenTime"] for bar in all_bars]
    assert times == sorted(times)
    assert len(times) == 2


def test_market_bars_reject_unknown_instrument_and_period(tmp_path: Path) -> None:
    _application, client = _app(tmp_path)
    assert (
        client.get("/api/market/instruments/NOPE/bars", params={"period": "1d"}).status_code
        == 404
    )
    bad_period = client.get(
        "/api/market/instruments/CN.SSE.STOCK.600519/bars",
        params={"period": "5m"},
    )
    assert bad_period.status_code == 400
    assert client.get("/api/market/instruments", params={"pageSize": 501}).status_code == 422


def test_watchlist_add_list_duplicate_delete(tmp_path: Path) -> None:
    application, loopback = _app(tmp_path)
    assert loopback.get("/api/personal/watchlist").json() == {"items": []}

    created = loopback.post(
        "/api/personal/watchlist",
        json={"instrumentId": "CN.SSE.STOCK.600519", "note": "core"},
    )
    assert created.status_code == 200
    item = created.json()["item"]
    assert item["instrumentId"] == "CN.SSE.STOCK.600519"
    assert item["note"] == "core"

    duplicate = loopback.post(
        "/api/personal/watchlist",
        json={"instrumentId": "CN.SSE.STOCK.600519"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["item"]["addedAt"] == item["addedAt"]

    assert loopback.get("/api/personal/watchlist").json()["items"][0]["instrumentId"] == "CN.SSE.STOCK.600519"

    deleted = loopback.delete("/api/personal/watchlist/CN.SSE.STOCK.600519")
    assert deleted.status_code == 200
    assert loopback.get("/api/personal/watchlist").json()["items"] == []
    assert loopback.delete("/api/personal/watchlist/CN.SSE.STOCK.600519").status_code == 404

    remote = TestClient(application)
    assert remote.get("/api/personal/watchlist").status_code == 200
    assert (
        remote.post("/api/personal/watchlist", json={"instrumentId": "CN.SSE.STOCK.600519"}).status_code
        == 403
    )


def test_watchlist_rejects_unknown_instrument_and_extra_fields(tmp_path: Path) -> None:
    _application, loopback = _app(tmp_path)
    assert (
        loopback.post("/api/personal/watchlist", json={"instrumentId": "UNKNOWN"}).status_code == 400
    )
    assert (
        loopback.post(
            "/api/personal/watchlist",
            json={"instrumentId": "CN.SSE.STOCK.600519", "sql": "delete"},
        ).status_code
        == 422
    )
