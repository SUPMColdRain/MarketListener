"""Declarative Strategy DSL v1: schema validation, reference interpreter and scanner."""

from market_monitor.strategy_dsl.errors import DslErrorKind, StrategyDslError
from market_monitor.strategy_dsl.interpreter import DslEvaluation, evaluate
from market_monitor.strategy_dsl.scanner import (
    BacktestResult,
    InstrumentScan,
    ScanReport,
    backtest,
    scan_strategy,
    write_run_record,
)
from market_monitor.strategy_dsl.schema import DslDocument, validate_dsl

__all__ = [
    "BacktestResult",
    "DslDocument",
    "DslErrorKind",
    "DslEvaluation",
    "InstrumentScan",
    "ScanReport",
    "StrategyDslError",
    "backtest",
    "evaluate",
    "scan_strategy",
    "validate_dsl",
    "write_run_record",
]
