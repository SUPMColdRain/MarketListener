"""API tests for /api/strategy: definitions, validation, run and history."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from market_monitor.web_app import create_web_app
from web_fixtures import silver_row, write_silver


_DSL_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "dsl" / "valid" / "ma-cross.json"


def _strategy_data(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    data_root = tmp_path / "data"
    document = json.loads(_DSL_FIXTURE.read_text(encoding="utf-8"))
    definitions = data_root / "strategies" / "definitions"
    definitions.mkdir(parents=True)
    (definitions / "ma_cross_demo.json").write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )
    rows = []
    for index in range(40):
        day = f"2026-06-{index + 1:02d}"
        close_a = 30.0 - index * 0.7 if index < 25 else 12.5 + index * 0.8
        rows.append(silver_row("CN.SSE.STOCK.600000", day, close=close_a))
        rows.append(silver_row("CN.SSE.STOCK.600001", day, close=30.0 - index * 0.4))
    write_silver(data_root, rows)
    return data_root, document


def _app(tmp_path: Path) -> tuple[TestClient, dict[str, object]]:
    data_root, document = _strategy_data(tmp_path)
    application = create_web_app(data_root)
    return TestClient(application, client=("127.0.0.1", 50000)), document


def test_strategy_definitions_and_validate(tmp_path: Path) -> None:
    client, document = _app(tmp_path)
    definitions = client.get("/api/strategy/definitions")
    assert definitions.status_code == 200
    body = definitions.json()
    assert body["total"] == 1
    assert body["items"][0]["strategyId"] == "ma_cross_demo"
    assert body["items"][0]["inputs"] == ["close"]

    validated = client.post("/api/strategy/validate", json=document)
    assert validated.status_code == 200
    assert validated.json()["valid"] is True
    assert validated.json()["strategyId"] == "ma_cross_demo"


def test_strategy_run_writes_record_and_returns_signals(tmp_path: Path) -> None:
    client, _document = _app(tmp_path)
    response = client.post(
        "/api/strategy/run",
        json={
            "strategyId": "ma_cross_demo",
            "period": "1d",
            "limitInstruments": 10,
            "limitPerInstrument": 100,
            "timeoutSeconds": 5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["report"]["strategyId"] == "ma_cross_demo"
    assert body["report"]["status"] == "PASS"
    assert len(body["report"]["instruments"]) == 2
    assert len(body["signals"]) == 2
    assert any(scan["signalCount"] > 0 for scan in body["signals"])
    first_signal = next(scan for scan in body["signals"] if scan["signalCount"] > 0)
    assert first_signal["signals"][0]["instrumentId"]

    runs_dir = tmp_path / "data" / "strategies" / "runs"
    assert len(list(runs_dir.glob("*.json"))) == 1

    history = client.get("/api/strategy/history")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["strategyId"] == "ma_cross_demo"
    assert history.json()["items"][0]["status"] == "PASS"


def test_strategy_run_rejects_unknown_or_invalid_inputs(tmp_path: Path) -> None:
    client, document = _app(tmp_path)
    assert (
        client.post("/api/strategy/run", json={"strategyId": "missing"}).status_code == 404
    )
    assert (
        client.post(
            "/api/strategy/validate",
            json={"strategy_id": 123, "nodes": {}},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/strategy/run",
            json={"strategyId": "ma_cross_demo", "period": "5m"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/strategy/run",
            json={"strategyId": "ma_cross_demo", "sql": "delete"},
        ).status_code
        == 422
    )


def test_strategy_mutations_are_loopback_only(tmp_path: Path) -> None:
    data_root, document = _strategy_data(tmp_path)
    application = create_web_app(data_root)
    remote = TestClient(application)
    assert remote.post("/api/strategy/validate", json=document).status_code == 403
    assert remote.post("/api/strategy/run", json={"strategyId": "ma_cross_demo"}).status_code == 403
    assert remote.get("/api/strategy/definitions").status_code == 200
