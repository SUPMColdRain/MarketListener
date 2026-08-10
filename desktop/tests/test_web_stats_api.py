"""API tests for /api/stats: Android-compatible ledger statistics."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from market_monitor.web_app import create_web_app
from web_fixtures import silver_row, write_silver


def _ledger_lines() -> list[dict[str, object]]:
    return [
        {"type": "header", "source_label": "desktop-test"},
        {"type": "cash", "kind": "DEPOSIT", "amount": 100000.0, "occurred_at": "2026-08-03T09:00:00+08:00"},
        {
            "type": "trade",
            "instrument_id": "CN.SSE.STOCK.600519",
            "side": "BUY",
            "quantity": 100,
            "price": 10.0,
            "executed_at": "2026-08-04T10:00:00+08:00",
            "fees": [{"kind": "COMMISSION", "amount": 5.0}],
            "strategy_id": "ma_cross_demo",
        },
        {
            "type": "trade",
            "instrument_id": "CN.SSE.STOCK.600519",
            "side": "SELL",
            "quantity": 100,
            "price": 12.0,
            "executed_at": "2026-08-05T10:00:00+08:00",
            "fees": [{"kind": "COMMISSION", "amount": 5.0}],
            "strategy_id": "ma_cross_demo",
        },
    ]


def _data_root(tmp_path: Path) -> Path:
    data_root = tmp_path / "data"
    ledger = data_root / "personal" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in _ledger_lines()),
        encoding="utf-8",
    )
    write_silver(
        data_root,
        [
            silver_row("CN.SSE.STOCK.600519", "2026-08-04", close=10.0),
            silver_row("CN.SSE.STOCK.600519", "2026-08-05", close=12.0),
        ],
    )
    return data_root


def _app(tmp_path: Path, *, with_ledger: bool = True) -> TestClient:
    data_root = _data_root(tmp_path) if with_ledger else tmp_path / "empty"
    return TestClient(create_web_app(data_root), client=("127.0.0.1", 50000))


def test_stats_summary_available_false_when_no_ledger(tmp_path: Path) -> None:
    client = _app(tmp_path, with_ledger=False)
    response = client.get("/api/stats/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["navCurve"] == []
    assert body["totalReturnPct"] is None
    assert body["realizedTotal"] is None
    assert "NaN" not in response.text
    assert "undefined" not in response.text


def test_stats_summary_matches_average_cost_accounting(tmp_path: Path) -> None:
    client = _app(tmp_path)
    body = client.get("/api/stats/summary").json()
    assert body["available"] is True
    assert body["feesTotal"] == 10.0
    assert body["realizedTotal"] == 190.0
    assert body["grossProfit"] == 190.0
    assert body["grossLoss"] == 0.0
    assert body["winRatePct"] == 100.0
    assert body["realizedByStrategy"] == {"ma_cross_demo": 190.0}
    assert body["realizedByInstrument"] == {"CN.SSE.STOCK.600519": 190.0}
    assert body["unrealizedTotal"] == 0.0

    curve = body["navCurve"]
    assert curve[0]["t"] == "2026-08-03"
    assert curve[0]["nav"] == 100000.0
    assert curve[1]["t"] == "2026-08-04"
    assert curve[1]["nav"] == 99995.0
    assert curve[-1]["t"] == "2026-08-05"
    assert curve[-1]["nav"] == 100190.0
    assert curve[-1]["positionValue"] == 0.0


def test_stats_trades_positions_and_pagination(tmp_path: Path) -> None:
    client = _app(tmp_path)
    trades = client.get("/api/stats/trades", params={"pageSize": 2})
    assert trades.status_code == 200
    body = trades.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    newest = body["items"][0]
    assert newest["side"] == "SELL"
    assert newest["fees"] == [{"kind": "COMMISSION", "amount": 5.0}]
    assert newest["strategyId"] == "ma_cross_demo"
    assert body["items"][1]["side"] == "BUY"

    page2 = client.get("/api/stats/trades", params={"page": 2, "pageSize": 2})
    assert page2.json()["items"] == []

    # A fresh open position uses cost fallback when no close is available.
    data_root = tmp_path / "data"
    ledger = data_root / "personal" / "ledger.jsonl"
    ledger.write_text(
        "".join(
            json.dumps(line, ensure_ascii=False) + "\n"
            for line in _ledger_lines()[:-1]
        ),
        encoding="utf-8",
    )
    positions = client.get("/api/stats/positions").json()
    assert positions["total"] == 1
    item = positions["items"][0]
    assert item["instrumentId"] == "CN.SSE.STOCK.600519"
    assert item["quantity"] == 100
    assert item["averageCost"] == 10.05
    assert item["marketValue"] == 1200.0
    assert item["unrealizedPnl"] == 195.0


def test_stats_import_skips_invalid_lines_and_export_roundtrip(tmp_path: Path) -> None:
    client = _app(tmp_path)
    imported = client.post(
        "/api/stats/import",
        json={
            "lines": [
                {
                    "type": "trade",
                    "instrument_id": "HK.HKEX.STOCK.00700",
                    "side": "buy",
                    "quantity": 10,
                    "price": 300.0,
                    "executed_at": "2026-08-06T10:00:00+08:00",
                },
                {"type": "trade", "instrument_id": "X", "side": "BUY", "quantity": 1},
                {"type": "mystery", "foo": 1},
            ]
        },
    )
    assert imported.status_code == 200
    assert imported.json() == {"imported": 1, "skipped": 2, "total": 3}

    exported = client.get("/api/stats/export")
    assert exported.status_code == 200
    text = exported.text
    assert "desktop-test" in text
    assert '"side": "BUY"' in text or '"side":"BUY"' in text

    summary = client.get("/api/stats/summary").json()
    assert summary["available"] is True
    assert "HK.HKEX.STOCK.00700" in summary["unrealizedByInstrument"]


def test_stats_mutations_are_loopback_only(tmp_path: Path) -> None:
    application = create_web_app(_data_root(tmp_path))
    remote = TestClient(application)
    assert remote.post("/api/stats/import", json={"lines": []}).status_code == 403
    assert remote.get("/api/stats/summary").status_code == 200
