"""/api/strategy router: local Strategy DSL definitions, validation, scans and history.

Definitions live under ``data_control/strategies/definitions/*.json`` and run
records under ``data_control/strategies/runs/{run_id}.json``.  The router only
loads allow-listed local documents, never accepts inline DSL code for
execution, and reuses the shared ``strategy_dsl`` scanner/writer services.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from market_monitor.strategy_dsl import StrategyDslError, scan_strategy, validate_dsl, write_run_record
from market_monitor.web_api.common import (
    bars_by_instrument,
    clean,
    load_inventory,
    load_json,
    now_iso,
)

router = APIRouter(prefix="/api/strategy", tags=["strategy"])

# 生产环境默认数据根目录；测试或其他宿主可通过 ``app.state.data_root`` 覆盖。
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_DATA_ROOT = _REPO_ROOT / "data_control"

_DEFINITION_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_DEFAULT_HISTORY_LIMIT = 50
_MAX_HISTORY_LIMIT = 200
_MAX_SIGNALS_PER_INSTRUMENT = 50


def _camel_key(key: str) -> str:
    head, *parts = key.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in parts)


def _camel_keys(value: Any) -> Any:
    """Recursively convert snake_case dict keys to camelCase for JSON responses."""
    if isinstance(value, dict):
        return {_camel_key(str(key)): _camel_keys(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_camel_keys(item) for item in value]
    return value


def _data_root(request: Request) -> Path:
    configured = getattr(request.app.state, "data_root", None)
    if configured:
        return Path(configured)
    return _DEFAULT_DATA_ROOT


def _definitions_dir(data_root: Path) -> Path:
    return data_root / "strategies" / "definitions"


def _runs_dir(data_root: Path) -> Path:
    return data_root / "strategies" / "runs"


def _definition_items(data_root: Path) -> list[dict[str, Any]]:
    directory = _definitions_dir(data_root)
    if not directory.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        document = load_json(path, default=None)
        if not isinstance(document, dict) or not str(document.get("strategy_id") or ""):
            continue
        try:
            updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
        except OSError:
            updated_at = now_iso()
        items.append(
            {
                "strategyId": str(document.get("strategy_id") or ""),
                "strategyVersion": str(document.get("strategy_version") or ""),
                "inputs": list(document.get("inputs") or []),
                "parameters": dict(document.get("parameters") or {}),
                "description": str(document.get("description") or ""),
                "updatedAt": updated_at,
            }
        )
    return items


def _load_definition(data_root: Path, strategy_id: str) -> dict[str, Any]:
    strategy_id = strategy_id.strip()
    if not _DEFINITION_NAME.fullmatch(strategy_id):
        raise HTTPException(status_code=400, detail="invalid strategy id")
    path = _definitions_dir(data_root) / f"{strategy_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="strategy definition not found")
    document = load_json(path, default=None)
    if not isinstance(document, dict):
        raise HTTPException(status_code=404, detail="strategy definition is not valid JSON")
    return document


class StrategyRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategyId: str
    parameters: dict[str, int | float | bool] = Field(default_factory=dict)
    period: str | None = None
    limitInstruments: int = Field(default=200, ge=1, le=1000)
    limitPerInstrument: int = Field(default=500, ge=1, le=5000)
    timeoutSeconds: float = Field(default=2.0, gt=0.0, le=30.0)
    maxOps: int = Field(default=500_000, ge=1000, le=5_000_000)


@router.get("/definitions")
def strategy_definitions(request: Request) -> dict[str, Any]:
    items = _definition_items(_data_root(request))
    items.sort(key=lambda item: item["updatedAt"], reverse=True)
    return clean({"items": items, "total": len(items)})


@router.post("/validate")
def strategy_validate(request: Request, document: dict[str, Any]) -> dict[str, Any]:
    """Validate a full Strategy DSL document without persisting anything."""
    try:
        validated = validate_dsl(document)
    except StrategyDslError as error:
        raise HTTPException(status_code=400, detail=error.to_dict()) from error
    return clean(
        {
            "valid": True,
            "strategyId": validated.strategy_id,
            "inputs": list(validated.inputs),
            "parameters": validated.parameters,
        }
    )


@router.post("/run")
def strategy_run(request: Request, body: StrategyRunRequest) -> dict[str, Any]:
    """Scan local silver bars with a persisted strategy definition and write a run record."""
    data_root = _data_root(request)
    document = _load_definition(data_root, body.strategyId)
    try:
        validated = validate_dsl(document)
    except StrategyDslError as error:
        raise HTTPException(status_code=400, detail=error.to_dict()) from error

    period = body.period
    if period is not None:
        inventory = load_inventory(data_root)
        if period not in inventory.periods:
            raise HTTPException(status_code=400, detail=f"unknown period: {period}")

    instruments = bars_by_instrument(
        data_root,
        period=period,
        limit_per_instrument=body.limitPerInstrument,
        max_instruments=body.limitInstruments,
    )
    if not instruments:
        raise HTTPException(status_code=404, detail="no local bars available for this strategy run")

    report = scan_strategy(
        validated,
        instruments,
        parameters=dict(body.parameters),
        timeout_seconds=body.timeoutSeconds,
        max_ops=body.maxOps,
    )
    write_run_record(_runs_dir(data_root) / f"{report.run_id}.json", report)
    signals = [
        {
            "instrumentId": scan.instrument_id,
            "barCount": scan.bar_count,
            "signalCount": scan.signal_count,
            "signals": [asdict(signal) for signal in scan.signals[:_MAX_SIGNALS_PER_INSTRUMENT]],
        }
        for scan in report.instruments
    ]
    return clean({"report": _camel_keys(asdict(report)), "signals": _camel_keys(signals)})


@router.get("/history")
def strategy_history(
    request: Request,
    limit: int = Query(default=_DEFAULT_HISTORY_LIMIT, ge=1, le=_MAX_HISTORY_LIMIT),
) -> dict[str, Any]:
    """Return run-record summaries, newest first."""
    runs_directory = _runs_dir(_data_root(request))
    summaries: list[dict[str, Any]] = []
    if runs_directory.is_dir():
        paths = sorted(runs_directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in paths:
            record = load_json(path, default=None)
            if not isinstance(record, dict):
                continue
            instruments = record.get("instruments") or []
            summaries.append(
                {
                    "runId": str(record.get("run_id") or ""),
                    "strategyId": str(record.get("strategy_id") or ""),
                    "strategyVersion": str(record.get("strategy_version") or ""),
                    "dataVersion": str(record.get("data_version") or ""),
                    "parameterVersion": str(record.get("parameter_version") or ""),
                    "startedAt": str(record.get("started_at") or ""),
                    "finishedAt": str(record.get("finished_at") or ""),
                    "status": str(record.get("status") or "UNKNOWN"),
                    "error": record.get("error"),
                    "instrumentCount": len(instruments),
                    "signalCount": sum(
                        int(item.get("signal_count") or 0) for item in instruments if isinstance(item, dict)
                    ),
                }
            )
    return clean({"items": summaries[:limit], "total": len(summaries), "limit": limit})


__all__ = ("router",)
