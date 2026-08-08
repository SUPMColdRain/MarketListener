"""Scan/backtest runner and versioned run records for Strategy DSL v1."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from market_monitor.strategy_dsl.errors import DslErrorKind, StrategyDslError
from market_monitor.strategy_dsl.interpreter import Number, evaluate
from market_monitor.strategy_dsl.schema import DslDocument


@dataclass(frozen=True)
class SignalEvent:
    instrument_id: str
    index: int
    bar_open_time: str
    label: str
    reason: str
    risk_tags: tuple[str, ...]


@dataclass(frozen=True)
class InstrumentScan:
    instrument_id: str
    bar_count: int
    signal_count: int
    signals: tuple[SignalEvent, ...]


@dataclass(frozen=True)
class ScanReport:
    run_id: str
    strategy_id: str
    strategy_version: str
    data_version: str
    parameter_version: str
    started_at: str
    finished_at: str
    status: str
    error: dict[str, str] | None = None
    instruments: tuple[InstrumentScan, ...] = ()


@dataclass(frozen=True)
class BacktestResult:
    report: ScanReport
    timeline: tuple[tuple[str, int, bool], ...]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _data_version(strategy_id: str, instruments: Mapping[str, Sequence[Mapping[str, Any]]]) -> str:
    payload = {
        "strategy_id": strategy_id,
        "instruments": {key: [dict(bar) for bar in bars] for key, bars in instruments.items()},
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _parameter_version(parameters: Mapping[str, Number]) -> str:
    return hashlib.sha256(_canonical_json(dict(parameters)).encode("utf-8")).hexdigest()


def _scan_one(
    document: DslDocument,
    instrument_id: str,
    bars: Sequence[Mapping[str, Any]],
    parameters: Mapping[str, Number] | None,
    timeout_seconds: float,
    max_ops: int,
) -> InstrumentScan:
    ordered = sorted(bars, key=lambda bar: str(bar["bar_open_time"]))
    series: dict[str, list[float]] = {}
    for input_name in document.inputs:
        try:
            series[input_name] = [float(bar[input_name]) for bar in ordered]
        except KeyError as error:
            raise StrategyDslError(DslErrorKind.SCHEMA, f"bar missing required field {input_name}") from error
        except (TypeError, ValueError) as error:
            raise StrategyDslError(DslErrorKind.SCHEMA, f"bar field {input_name} is not numeric") from error
    evaluation = evaluate(
        document,
        series,
        parameters=parameters,
        timeout_seconds=timeout_seconds,
        max_ops=max_ops,
    )
    signals = tuple(
        SignalEvent(
            instrument_id=instrument_id,
            index=index,
            bar_open_time=str(ordered[index]["bar_open_time"]),
            label=document.signal.label,
            reason=document.signal.reason,
            risk_tags=document.signal.risk_tags,
        )
        for index in evaluation.signal_indices
    )
    return InstrumentScan(
        instrument_id=instrument_id,
        bar_count=len(ordered),
        signal_count=len(signals),
        signals=signals,
    )


def _run(
    document: DslDocument,
    instruments: Mapping[str, Sequence[Mapping[str, Any]]],
    parameters: Mapping[str, Number] | None,
    timeout_seconds: float,
    max_ops: int,
) -> ScanReport:
    started = time.time()
    run_id = str(uuid.uuid4())
    resolved = dict(document.parameter_defaults())
    if parameters:
        resolved.update(parameters)
    data_version = _data_version(document.strategy_id, instruments)
    parameter_version = _parameter_version(resolved)
    scans: list[InstrumentScan] = []
    error: dict[str, str] | None = None
    status = "PASS"
    for instrument_id, bars in instruments.items():
        try:
            scans.append(_scan_one(document, instrument_id, bars, parameters, timeout_seconds, max_ops))
        except StrategyDslError as caught:
            status = {
                DslErrorKind.TIMEOUT: "TIMEOUT",
                DslErrorKind.CANCELLED: "CANCELLED",
            }.get(caught.kind, "FAILED")
            error = caught.to_dict()
            break
    return ScanReport(
        run_id=run_id,
        strategy_id=document.strategy_id,
        strategy_version=document.strategy_version,
        data_version=data_version,
        parameter_version=parameter_version,
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(started)),
        finished_at=time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time())),
        status=status,
        error=error,
        instruments=tuple(scans),
    )


def scan_strategy(
    document: DslDocument,
    instruments: Mapping[str, Sequence[Mapping[str, Any]]],
    parameters: Mapping[str, Number] | None = None,
    timeout_seconds: float = 2.0,
    max_ops: int = 500_000,
) -> ScanReport:
    """Scan every instrument and record per-bar signal events without future data."""

    return _run(document, instruments, parameters, timeout_seconds, max_ops)


def backtest(
    document: DslDocument,
    bars: Sequence[Mapping[str, Any]],
    parameters: Mapping[str, Number] | None = None,
    timeout_seconds: float = 2.0,
    max_ops: int = 500_000,
    instrument_id: str = "instrument",
) -> BacktestResult:
    """Replay a strategy on one instrument and return its observation timeline.

    The DSL produces candidate observations, not trade instructions, so this
    backtest intentionally does not simulate orders, fees or P&L.
    """

    ordered = sorted(bars, key=lambda bar: str(bar["bar_open_time"]))
    series: dict[str, list[float]] = {}
    for input_name in document.inputs:
        try:
            series[input_name] = [float(bar[input_name]) for bar in ordered]
        except KeyError as error:
            raise StrategyDslError(DslErrorKind.SCHEMA, f"bar missing required field {input_name}") from error
        except (TypeError, ValueError) as error:
            raise StrategyDslError(DslErrorKind.SCHEMA, f"bar field {input_name} is not numeric") from error
    evaluation = evaluate(document, series, parameters=parameters, timeout_seconds=timeout_seconds, max_ops=max_ops)
    report = _run(document, {instrument_id: ordered}, parameters, timeout_seconds, max_ops)
    timeline = tuple(
        (str(ordered[index]["bar_open_time"]), index, bool(value))
        for index, value in enumerate(evaluation.signal)
    )
    return BacktestResult(report=report, timeline=timeline)


def write_run_record(path: Path, report: ScanReport) -> Path:
    """Persist a run record including data and parameter versions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        **asdict(report),
        "instruments": [asdict(scan) for scan in report.instruments],
    }
    path.write_text(_canonical_json(payload) + "\n", encoding="utf-8")
    return path
