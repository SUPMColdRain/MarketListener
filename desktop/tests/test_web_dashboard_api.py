"""API tests for /api/dashboard and /api/metrics real-data panels."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from market_monitor.web_app import create_web_app
from web_fixtures import make_bar, silver_row, write_gold_metrics, write_silver


def _app(tmp_path: Path) -> TestClient:
    return TestClient(create_web_app(tmp_path / "data"), client=("127.0.0.1", 50000))


def test_dashboard_definitions_empty_data_is_never_fabricated(tmp_path: Path) -> None:
    client = _app(tmp_path)
    response = client.get("/api/dashboard/definitions")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 8
    assert all(item["available"] is False for item in body["items"])
    assert all(item["id"] for item in body["items"])

    for dashboard_id in ("market-breadth", "futures-breadth", "gold-metrics", "storage", "quality", "freshness", "runs", "partitions"):
        detail = client.get(f"/api/dashboard/{dashboard_id}")
        assert detail.status_code == 200
        assert detail.json()["available"] is False

    assert client.get("/api/dashboard/unknown").status_code == 404
    assert client.get("/api/metrics/ranking", params={"category": "nope"}).status_code == 400
    assert client.get("/api/metrics/heatmap", params={"category": "nope"}).status_code == 400


def test_dashboard_storage_becomes_available_with_local_files(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    write_silver(data_root, [silver_row("CN.SSE.STOCK.600519", "2026-08-07")])
    client = TestClient(create_web_app(data_root), client=("127.0.0.1", 50000))
    detail = client.get("/api/dashboard/storage")
    assert detail.status_code == 200
    body = detail.json()
    assert body["available"] is True
    assert any(series["points"][0]["value"] > 0 for series in body["series"])


def test_futures_breadth_dashboard_uses_trading_day_field(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    write_silver(
        data_root,
        [
            silver_row("CN.SHFE.FUTURE.AU0", "2026-08-06", market="CN", asset_type="FUTURE", close=700.0),
            silver_row("CN.SHFE.FUTURE.AU0", "2026-08-07", market="CN", asset_type="FUTURE", close=710.0, open_=700.0),
            silver_row("CN.DCE.FUTURE.M0", "2026-08-06", market="CN", asset_type="FUTURE", close=2500.0),
            silver_row("CN.DCE.FUTURE.M0", "2026-08-07", market="CN", asset_type="FUTURE", close=2450.0, open_=2500.0),
        ],
    )
    client = TestClient(create_web_app(data_root), client=("127.0.0.1", 50000))
    response = client.get("/api/dashboard/futures-breadth")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    advancing = next(series for series in body["series"] if series["name"] == "上涨")
    declining = next(series for series in body["series"] if series["name"] == "下跌")
    assert advancing["points"][-1] == {"t": "2026-08-07", "value": 1}
    assert declining["points"][-1] == {"t": "2026-08-07", "value": 1}


def test_metrics_ranking_and_heatmap_use_real_breadth_data(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    write_silver(
        data_root,
        [
            silver_row("CN.SSE.STOCK.600000", "2026-08-06", close=10.0),
            silver_row("CN.SSE.STOCK.600001", "2026-08-06", close=10.0),
            silver_row("CN.SSE.STOCK.600000", "2026-08-07", close=11.0, open_=10.0),
            silver_row("CN.SSE.STOCK.600001", "2026-08-07", close=9.0, open_=10.0),
        ],
    )
    client = TestClient(create_web_app(data_root), client=("127.0.0.1", 50000))

    breadth = client.get("/api/dashboard/market-breadth")
    assert breadth.status_code == 200
    series = breadth.json()["series"]
    assert any(item["name"] == "上涨" for item in series)
    advancing = next(item for item in series if item["name"] == "上涨")
    assert advancing["points"][-1]["value"] == 1
    declining = next(item for item in series if item["name"] == "下跌")
    assert declining["points"][-1]["value"] == 1

    ranking = client.get("/api/metrics/ranking", params={"category": "breadth", "limit": 10})
    assert ranking.status_code == 200
    assert ranking.json()["available"] is True
    assert ranking.json()["frames"][0]["t"] == "2026-08-07"
    assert ranking.json()["frames"][0]["items"][0]["name"] == "上涨"

    heatmap = client.get("/api/metrics/heatmap", params={"category": "breadth"})
    assert heatmap.status_code == 200
    body = heatmap.json()
    assert body["available"] is True
    assert body["x"] == ["2026-08-06", "2026-08-07"]
    assert body["y"] == ["上涨", "下跌", "平盘", "涨停", "跌停"]
    assert body["cells"]


def test_metrics_gold_ranking_heatmap_and_downsampling(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    write_silver(data_root, [silver_row("CN.SHFE.FUTURE.AU0", "2026-08-07", market="CN", asset_type="FUTURE")])
    rows = [
        {
            "instrument_id": "CN.SHFE.FUTURE.AU0",
            "trading_date": f"2026-08-{day:02d}",
            "metric_name": "最新价",
            "value": 700.0 + day,
            "metric_id": "GOLD.LATEST",
        }
        for day in range(1, 6)
    ]
    rows.append(
        {
            "instrument_id": "CN.SHFE.FUTURE.AU0",
            "trading_date": "2026-08-05",
            "metric_name": "净持仓",
            "value": 123.0,
            "metric_id": "FUTURES_OI_LEADERBOARD:AU",
        }
    )
    write_gold_metrics(data_root, rows)
    client = TestClient(create_web_app(data_root), client=("127.0.0.1", 50000))

    dashboard = client.get("/api/dashboard/gold-metrics")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["available"] is True
    assert body["series"][0]["name"] == "最新价"
    assert len(body["series"][0]["points"]) == 5

    ranking = client.get("/api/metrics/ranking", params={"category": "gold"})
    assert ranking.status_code == 200
    frames = ranking.json()["frames"]
    assert frames[0]["t"] == "2026-08-05"
    assert any(item["name"] == "CN.SHFE.FUTURE.AU0" for item in frames[0]["items"])

    heatmap = client.get("/api/metrics/heatmap", params={"category": "gold"})
    assert heatmap.status_code == 200
    heat = heatmap.json()
    assert heat["available"] is True
    assert heat["x"] == ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04", "2026-08-05"]
    assert heat["cells"]


def test_dashboard_series_points_are_capped(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    rows = [
        {
            "instrument_id": "CN.SHFE.FUTURE.AU0",
            "trading_date": f"2026-08-{day % 28 + 1:02d}",
            "metric_name": "最新价",
            "value": 700.0 + day,
            "metric_id": "GOLD.LATEST",
        }
        for day in range(1200)
    ]
    write_gold_metrics(data_root, rows)
    client = TestClient(create_web_app(data_root), client=("127.0.0.1", 50000))
    body = client.get("/api/dashboard/gold-metrics").json()
    assert body["available"] is True
    for series in body["series"]:
        assert len(series["points"]) <= 1000
