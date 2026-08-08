"""Reference interpreter for Strategy DSL v1 (desktop, Python 3.11)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from market_monitor.strategy_dsl.errors import DslErrorKind, StrategyDslError
from market_monitor.strategy_dsl.schema import (
    BOOLEAN_BINARY,
    COMPARISON_TYPES,
    NUMERIC_BINARY,
    NUMERIC_UNARY,
    ROLLING_TYPES,
    DslDocument,
)


Number = float | bool
SeriesValue = list[Number | None]
_BATCH_CHECK = 65536


@dataclass(frozen=True)
class DslEvaluation:
    signal: tuple[bool, ...]
    signal_indices: tuple[int, ...]
    node_values: dict[str, tuple[Number | None, ...]]
    parameters: dict[str, Number]
    elapsed_seconds: float
    ops: int
    output_nodes: tuple[str, ...] = field(default=())


class _Evaluator:
    def __init__(
        self,
        document: DslDocument,
        series: Mapping[str, Sequence[float]],
        parameters: dict[str, Number],
        timeout_seconds: float,
        max_ops: int,
        is_cancelled: Callable[[], bool] | None,
        output_nodes: Sequence[str],
    ) -> None:
        self.document = document
        self.series = series
        self.parameters = parameters
        self.timeout_seconds = timeout_seconds
        self.max_ops = max_ops
        self.is_cancelled = is_cancelled
        self.output_nodes = frozenset(output_nodes)
        self.order = _topological_order(document)
        self.values: dict[str, SeriesValue] = {}
        self.n = len(next(iter(series.values())))
        self.ops = 0
        self.deadline = time.monotonic() + timeout_seconds

    def _check_limits(self) -> None:
        if self.is_cancelled is not None and self.is_cancelled():
            raise StrategyDslError(DslErrorKind.CANCELLED, "strategy evaluation cancelled")
        if time.monotonic() > self.deadline:
            raise StrategyDslError(DslErrorKind.TIMEOUT, f"strategy evaluation exceeded {self.timeout_seconds:g}s")

    def _bump(self, amount: int = 1) -> None:
        self.ops += amount
        if self.ops > self.max_ops:
            raise StrategyDslError(DslErrorKind.LIMIT, f"strategy exceeded operation budget {self.max_ops}")

    def evaluate(self) -> DslEvaluation:
        for node_id in self.order:
            self._check_limits()
            self.values[node_id] = self._node(node_id)
        started = time.monotonic()
        signal_values = self.values[self.document.signal.node]
        signal = tuple(bool(value) for value in signal_values)
        signal_indices = tuple(i for i, value in enumerate(signal) if value)
        node_values = {
            node_id: tuple(self.values[node_id])
            for node_id in self.output_nodes
            if node_id in self.values
        }
        return DslEvaluation(
            signal=signal,
            signal_indices=signal_indices,
            node_values=node_values,
            parameters=dict(self.parameters),
            elapsed_seconds=time.monotonic() - started,
            ops=self.ops,
            output_nodes=tuple(sorted(self.output_nodes)),
        )

    def _node(self, node_id: str) -> SeriesValue:
        node = self.document.nodes[node_id]
        kind = node["type"]
        if kind == "series":
            return [float(value) for value in self.series[node["input"]]]
        if kind == "value":
            return [node["value"]] * self.n
        if kind == "parameter":
            return [self.parameters[node["name"]]] * self.n
        if kind in NUMERIC_BINARY:
            return self._binary_numeric(node_id, node, kind)
        if kind in NUMERIC_UNARY:
            return self._unary_numeric(node_id, node, kind)
        if kind in COMPARISON_TYPES:
            return self._comparison(node_id, node, kind)
        if kind in BOOLEAN_BINARY:
            return self._boolean(node_id, node, kind)
        if kind == "not":
            operand = self.values[node["operand"]]
            return [False if value is None else (not _as_boolean(value, node_id)) for value in operand]
        if kind == "ifelse":
            return self._ifelse(node_id, node)
        if kind in ROLLING_TYPES:
            return self._rolling(node_id, node, kind)
        if kind == "lag":
            return self._lag(node_id, node)
        if kind in {"crosses_above", "crosses_below"}:
            return self._crosses(node_id, node, kind)
        raise StrategyDslError(DslErrorKind.UNKNOWN_NODE, f"unknown node type {kind}")  # pragma: no cover

    def _binary_numeric(self, node_id: str, node: dict, kind: str) -> SeriesValue:
        left = self.values[node["left"]]
        right = self.values[node["right"]]
        result: SeriesValue = []
        for index, (a, b) in enumerate(zip(left, right)):
            if index % _BATCH_CHECK == 0:
                self._check_limits()
            self._bump()
            if a is None or b is None:
                result.append(None)
                continue
            result.append(_binary_number(node_id, kind, float(a), float(b)))
        return result

    def _unary_numeric(self, node_id: str, node: dict, kind: str) -> SeriesValue:
        operand = self.values[node["operand"]]
        result: SeriesValue = []
        for index, value in enumerate(operand):
            if index % _BATCH_CHECK == 0:
                self._check_limits()
            self._bump()
            if value is None:
                result.append(None)
                continue
            result.append(_unary_number(node_id, kind, float(value)))
        return result

    def _comparison(self, node_id: str, node: dict, kind: str) -> SeriesValue:
        left = self.values[node["left"]]
        right = self.values[node["right"]]
        result: SeriesValue = []
        for index, (a, b) in enumerate(zip(left, right)):
            if index % _BATCH_CHECK == 0:
                self._check_limits()
            self._bump()
            if a is None or b is None:
                result.append(False)
                continue
            result.append(_compare(kind, float(a), float(b)))
        return result

    def _boolean(self, node_id: str, node: dict, kind: str) -> SeriesValue:
        left = self.values[node["left"]]
        right = self.values[node["right"]]
        result: SeriesValue = []
        for index, (a, b) in enumerate(zip(left, right)):
            if index % _BATCH_CHECK == 0:
                self._check_limits()
            self._bump()
            if kind == "and":
                result.append(_as_boolean(a, node_id) and _as_boolean(b, node_id))
            else:
                result.append(_as_boolean(a, node_id) or _as_boolean(b, node_id))
        return result

    def _ifelse(self, node_id: str, node: dict) -> SeriesValue:
        condition = self.values[node["condition"]]
        then_values = self.values[node["then"]]
        else_values = self.values[node["else"]]
        result: SeriesValue = []
        for index, (cond, yes, no) in enumerate(zip(condition, then_values, else_values)):
            if index % _BATCH_CHECK == 0:
                self._check_limits()
            self._bump()
            result.append(yes if _as_boolean(cond, node_id) else no)
        return result

    def _rolling(self, node_id: str, node: dict, kind: str) -> SeriesValue:
        operand = self.values[node["operand"]]
        window = self._window(node_id, node)
        if kind == "ema":
            return self._ema(node_id, operand, window)
        result: SeriesValue = []
        for index in range(self.n):
            if index % _BATCH_CHECK == 0:
                self._check_limits()
            self._bump(min(window, index + 1))
            if kind == "roc":
                if index < window:
                    result.append(None)
                    continue
                previous = operand[index - window]
                current = operand[index]
                if previous is None or current is None or float(previous) == 0.0:
                    result.append(None)
                    continue
                result.append((float(current) - float(previous)) / float(previous))
                continue
            if index < window - 1:
                result.append(None)
                continue
            window_values = operand[index - window + 1 : index + 1]
            if any(value is None for value in window_values):
                result.append(None)
                continue
            numbers = [float(value) for value in window_values]
            result.append(_rolling_value(kind, numbers, window))
        return result

    def _ema(self, node_id: str, operand: SeriesValue, window: int) -> SeriesValue:
        result: SeriesValue = []
        alpha = 2.0 / (window + 1)
        previous: float | None = None
        for index, value in enumerate(operand):
            if index % _BATCH_CHECK == 0:
                self._check_limits()
            self._bump()
            if index < window - 1:
                result.append(None)
                continue
            if index == window - 1:
                seed_values = operand[:window]
                if any(item is None for item in seed_values):
                    previous = None
                else:
                    previous = sum(float(item) for item in seed_values) / window
                result.append(previous)
                continue
            if value is None or previous is None:
                result.append(None)
                previous = None
                continue
            previous = alpha * float(value) + (1.0 - alpha) * previous
            result.append(previous)
        return result

    def _window(self, node_id: str, node: dict) -> int:
        window = node["window"]
        if isinstance(window, int):
            return window
        resolved = self.values[window][0]
        if not isinstance(resolved, (int, float)) or isinstance(resolved, bool):
            raise StrategyDslError(DslErrorKind.TYPE, f"window node {window} did not resolve to a number")
        value = int(resolved)
        if value < 1 or float(value) != float(resolved):
            raise StrategyDslError(DslErrorKind.PARAMETER, f"window parameter resolved to invalid value {resolved}")
        return value

    def _lag(self, node_id: str, node: dict) -> SeriesValue:
        operand = self.values[node["operand"]]
        offset = int(node["offset"])
        return [None] * offset + list(operand[: self.n - offset])

    def _crosses(self, node_id: str, node: dict, kind: str) -> SeriesValue:
        fast = self.values[node["fast"]]
        slow = self.values[node["slow"]]
        result: SeriesValue = []
        for index, (fast_now, slow_now) in enumerate(zip(fast, slow)):
            if index % _BATCH_CHECK == 0:
                self._check_limits()
            self._bump()
            if index == 0 or fast_now is None or slow_now is None:
                result.append(False)
                continue
            fast_prev = fast[index - 1]
            slow_prev = slow[index - 1]
            if fast_prev is None or slow_prev is None:
                result.append(False)
                continue
            if kind == "crosses_above":
                result.append(float(fast_prev) <= float(slow_prev) and float(fast_now) > float(slow_now))
            else:
                result.append(float(fast_prev) >= float(slow_prev) and float(fast_now) < float(slow_now))
        return result


def _as_boolean(value: Number | None, node_id: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise StrategyDslError(DslErrorKind.TYPE, f"node {node_id} expected boolean, got {type(value).__name__}")
    return value


def _binary_number(node_id: str, kind: str, left: float, right: float) -> float:
    try:
        if kind == "add":
            return left + right
        if kind == "subtract":
            return left - right
        if kind == "multiply":
            return left * right
        if kind == "divide":
            if right == 0.0:
                raise ZeroDivisionError
            return left / right
        if kind == "modulo":
            if right == 0.0:
                raise ZeroDivisionError
            return math.fmod(left, right)
        if kind == "pow":
            return math.pow(left, right)
        if kind == "max":
            return max(left, right)
        return min(left, right)
    except (ZeroDivisionError, ValueError, OverflowError) as error:
        raise StrategyDslError(DslErrorKind.NUMERIC, f"numeric error in node {node_id} ({kind}): {error}") from error


def _unary_number(node_id: str, kind: str, value: float) -> float:
    try:
        if kind == "negate":
            return -value
        if kind == "abs":
            return abs(value)
        if kind == "sqrt":
            return math.sqrt(value)
        if kind == "ln":
            return math.log(value)
        if kind == "log10":
            return math.log10(value)
        if kind == "floor":
            return float(math.floor(value))
        if kind == "ceil":
            return float(math.ceil(value))
        return float(round(value))
    except (ValueError, OverflowError) as error:
        raise StrategyDslError(DslErrorKind.NUMERIC, f"numeric error in node {node_id} ({kind}): {error}") from error


def _compare(kind: str, left: float, right: float) -> bool:
    if kind == "eq":
        return left == right
    if kind == "neq":
        return left != right
    if kind == "lt":
        return left < right
    if kind == "lte":
        return left <= right
    if kind == "gt":
        return left > right
    return left >= right


def _rolling_value(kind: str, values: list[float], window: int) -> float:
    if kind == "sma":
        return sum(values) / window
    if kind == "sum":
        return sum(values)
    if kind == "rolling_max":
        return max(values)
    if kind == "rolling_min":
        return min(values)
    if kind == "stddev":
        mean = sum(values) / window
        return math.sqrt(sum((value - mean) ** 2 for value in values) / window)
    raise StrategyDslError(DslErrorKind.UNKNOWN_NODE, f"unsupported rolling node {kind}")  # pragma: no cover


def _topological_order(document: DslDocument) -> list[str]:
    visited: set[str] = set()
    order: list[str] = []

    def visit(node_id: str, stack: set[str]) -> None:
        if node_id in visited:
            return
        if node_id in stack:
            raise StrategyDslError(DslErrorKind.CYCLE, f"node cycle detected through {node_id}")
        stack.add(node_id)
        for ref in _node_refs(document.nodes[node_id]):
            visit(ref, stack)
        stack.remove(node_id)
        visited.add(node_id)
        order.append(node_id)

    for node_id in document.nodes:
        visit(node_id, set())
    return order


def _node_refs(node: dict) -> list[str]:
    refs = []
    for key in ("left", "right", "operand", "fast", "slow", "condition", "then", "else"):
        value = node.get(key)
        if isinstance(value, str):
            refs.append(value)
    if node.get("type") in ROLLING_TYPES and isinstance(node.get("window"), str):
        refs.append(node["window"])
    return refs


def _validate_parameters(document: DslDocument, provided: Mapping[str, Number] | None) -> dict[str, Number]:
    merged = dict(document.parameter_defaults())
    for name, value in (provided or {}).items():
        if name not in document.parameters:
            raise StrategyDslError(DslErrorKind.PARAMETER, f"unknown parameter {name}")
        merged[name] = value
    for name, definition in document.parameters.items():
        value = merged[name]
        kind = definition["type"]
        if kind == "boolean":
            if not isinstance(value, bool):
                raise StrategyDslError(DslErrorKind.PARAMETER, f"parameter {name} must be boolean")
        elif kind == "integer":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not float(value).is_integer():
                raise StrategyDslError(DslErrorKind.PARAMETER, f"parameter {name} must be an integer")
            value = int(value)
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise StrategyDslError(DslErrorKind.PARAMETER, f"parameter {name} must be a number")
            value = float(value)
        minimum = definition.get("minimum")
        maximum = definition.get("maximum")
        if minimum is not None and value < minimum:
            raise StrategyDslError(DslErrorKind.PARAMETER, f"parameter {name}={value} below minimum {minimum}")
        if maximum is not None and value > maximum:
            raise StrategyDslError(DslErrorKind.PARAMETER, f"parameter {name}={value} above maximum {maximum}")
        merged[name] = value
    return merged


def evaluate(
    document: DslDocument,
    series: Mapping[str, Sequence[float]],
    parameters: Mapping[str, Number] | None = None,
    timeout_seconds: float = 2.0,
    max_ops: int = 500_000,
    is_cancelled: Callable[[], bool] | None = None,
    output_nodes: Sequence[str] = (),
) -> DslEvaluation:
    """Evaluate a validated DSL over aligned input series (no future bars)."""

    missing = [name for name in document.inputs if name not in series]
    if missing:
        raise StrategyDslError(DslErrorKind.NO_DATA, f"missing input series: {', '.join(missing)}")
    lengths = {len(series[name]) for name in document.inputs}
    if len(lengths) != 1:
        raise StrategyDslError(DslErrorKind.NO_DATA, "all input series must have the same length")
    if next(iter(lengths)) == 0:
        raise StrategyDslError(DslErrorKind.NO_DATA, "input series are empty")
    resolved = _validate_parameters(document, parameters)
    evaluator = _Evaluator(
        document=document,
        series={name: [float(value) for value in series[name]] for name in document.inputs},
        parameters=resolved,
        timeout_seconds=timeout_seconds,
        max_ops=max_ops,
        is_cancelled=is_cancelled,
        output_nodes=tuple(output_nodes),
    )
    return evaluator.evaluate()
