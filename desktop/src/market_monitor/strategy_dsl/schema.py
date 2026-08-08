"""Validation and semantic model for Strategy DSL v1 documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from market_monitor.contracts import ContractValidationError, validate_contract
from market_monitor.strategy_dsl.errors import DslErrorKind, StrategyDslError


DSL_SCHEMA = "strategy-dsl.schema.json"

INPUT_FIELDS = frozenset({"open", "high", "low", "close", "volume", "amount"})
NODE_REF_FIELDS = ("left", "right", "operand", "fast", "slow", "condition", "then", "else")
ROLLING_TYPES = frozenset({"sma", "ema", "sum", "stddev", "rolling_max", "rolling_min", "roc"})
NUMERIC_BINARY = frozenset({"add", "subtract", "multiply", "divide", "modulo", "pow", "max", "min"})
NUMERIC_UNARY = frozenset({"negate", "abs", "sqrt", "ln", "log10", "floor", "ceil", "round"})
COMPARISON_TYPES = frozenset({"eq", "neq", "lt", "lte", "gt", "gte"})
BOOLEAN_BINARY = frozenset({"and", "or"})
DEFAULT_MAX_NODES = 200
DEFAULT_MAX_DEPTH = 32


@dataclass(frozen=True)
class DslLimits:
    max_nodes: int = DEFAULT_MAX_NODES
    max_depth: int = DEFAULT_MAX_DEPTH


@dataclass(frozen=True)
class DslSignal:
    node: str
    label: str
    reason: str
    risk_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class DslDocument:
    """Validated DSL document with the data needed by both interpreters."""

    raw: dict[str, Any]
    strategy_id: str
    strategy_version: str
    inputs: tuple[str, ...]
    parameters: dict[str, dict[str, Any]]
    nodes: dict[str, dict[str, Any]]
    node_types: dict[str, str]
    signal: DslSignal
    limits: DslLimits = field(default_factory=DslLimits)

    def parameter_defaults(self) -> dict[str, Any]:
        return {name: definition["default"] for name, definition in self.parameters.items()}


def _fail(kind: DslErrorKind, message: str) -> None:
    raise StrategyDslError(kind, message)


def _refs(node: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in NODE_REF_FIELDS:
        value = node.get(key)
        if isinstance(value, str):
            refs.append(value)
    if node.get("type") in ROLLING_TYPES and isinstance(node.get("window"), str):
        refs.append(node["window"])
    return refs


def _depth_of(
    node_id: str,
    nodes: dict[str, dict[str, Any]],
    node_types: dict[str, str],
    limits: DslLimits,
    memo: dict[str, int],
    visiting: set[str],
) -> int:
    if node_id in memo:
        return memo[node_id]
    if node_id in visiting:
        _fail(DslErrorKind.CYCLE, f"node cycle detected through {node_id}")
    visiting.add(node_id)
    refs = _refs(nodes[node_id])
    child_depths = [0]
    for ref in refs:
        child_depths.append(_depth_of(ref, nodes, node_types, limits, memo, visiting))
    depth = 1 + max(child_depths)
    visiting.remove(node_id)
    if depth > limits.max_depth:
        _fail(DslErrorKind.LIMIT, f"node {node_id} depth {depth} exceeds max_depth {limits.max_depth}")
    memo[node_id] = depth
    return depth


def _infer_type(
    node_id: str,
    nodes: dict[str, dict[str, Any]],
    parameters: dict[str, dict[str, Any]],
    inputs: frozenset[str],
    memo: dict[str, str],
    visiting: set[str],
) -> str:
    if node_id in memo:
        return memo[node_id]
    if node_id in visiting:
        _fail(DslErrorKind.CYCLE, f"node cycle detected through {node_id}")
    if node_id not in nodes:
        _fail(DslErrorKind.UNKNOWN_NODE, f"node {node_id} is referenced but not defined")
    visiting.add(node_id)
    node = nodes[node_id]
    node_type = node["type"]
    if node_type == "series":
        if node["input"] not in inputs:
            _fail(DslErrorKind.UNKNOWN_NODE, f"series node {node_id} uses undeclared input {node['input']}")
        result = "number"
    elif node_type == "value":
        result = "boolean" if isinstance(node["value"], bool) else "number"
    elif node_type == "parameter":
        name = node["name"]
        if name not in parameters:
            _fail(DslErrorKind.UNKNOWN_NODE, f"parameter node {node_id} references unknown parameter {name}")
        result = "boolean" if parameters[name]["type"] == "boolean" else "number"
    elif node_type in NUMERIC_BINARY or node_type in NUMERIC_UNARY:
        result = "number"
    elif node_type in COMPARISON_TYPES or node_type in BOOLEAN_BINARY or node_type in {"not", "crosses_above", "crosses_below"}:
        result = "boolean"
    elif node_type == "ifelse":
        then_type = _infer_type(node["then"], nodes, parameters, inputs, memo, visiting)
        else_type = _infer_type(node["else"], nodes, parameters, inputs, memo, visiting)
        if then_type != else_type:
            _fail(
                DslErrorKind.TYPE,
                f"ifelse node {node_id} mixes {then_type} and {else_type} branches",
            )
        result = then_type
    elif node_type in ROLLING_TYPES or node_type == "lag":
        result = "number"
    else:  # pragma: no cover - schema guarantees membership
        _fail(DslErrorKind.UNKNOWN_NODE, f"unsupported node type {node_type}")
    memo[node_id] = result
    visiting.remove(node_id)
    return result


def _validate_operand_kinds(
    node_id: str,
    node: dict[str, Any],
    node_types: dict[str, str],
) -> None:
    kind = node["type"]
    expected_number = (
        kind in NUMERIC_BINARY
        or kind in NUMERIC_UNARY
        or kind in COMPARISON_TYPES
        or kind in ROLLING_TYPES
        or kind == "lag"
        or kind in {"crosses_above", "crosses_below"}
    )
    refs = _refs(node)
    for ref in refs:
        if expected_number and node_types[ref] != "number":
            _fail(DslErrorKind.TYPE, f"node {node_id} requires numeric operand {ref}, got {node_types[ref]}")
    if kind in BOOLEAN_BINARY:
        for ref in (node["left"], node["right"]):
            if node_types[ref] != "boolean":
                _fail(DslErrorKind.TYPE, f"node {node_id} requires boolean operand {ref}, got {node_types[ref]}")
    if kind == "not":
        if node_types[node["operand"]] != "boolean":
            _fail(DslErrorKind.TYPE, f"not node {node_id} requires boolean operand, got {node_types[node['operand']]}")
    if kind == "ifelse":
        if node_types[node["condition"]] != "boolean":
            _fail(DslErrorKind.TYPE, f"ifelse node {node_id} requires boolean condition")


def _validate_window_refs(
    node_id: str,
    node: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
    parameters: dict[str, dict[str, Any]],
) -> None:
    if node.get("type") not in ROLLING_TYPES or not isinstance(node.get("window"), str):
        return
    window_ref = node["window"]
    if window_ref not in nodes:
        _fail(DslErrorKind.UNKNOWN_NODE, f"rolling node {node_id} references missing window node {window_ref}")
    if nodes[window_ref]["type"] != "parameter":
        _fail(DslErrorKind.TYPE, f"rolling node {node_id} window must reference an integer parameter node")
    name = nodes[window_ref]["name"]
    definition = parameters[name]
    if definition["type"] != "integer":
        _fail(DslErrorKind.TYPE, f"rolling node {node_id} window parameter {name} must be integer")
    default = definition["default"]
    if default < 1:
        _fail(DslErrorKind.PARAMETER, f"window parameter {name} default must be >= 1")


def _validate_parameters(parameters: dict[str, dict[str, Any]]) -> None:
    for name, definition in parameters.items():
        default = definition["default"]
        minimum = definition.get("minimum")
        maximum = definition.get("maximum")
        if minimum is not None and default < minimum:
            _fail(DslErrorKind.PARAMETER, f"parameter {name} default {default} is below minimum {minimum}")
        if maximum is not None and default > maximum:
            _fail(DslErrorKind.PARAMETER, f"parameter {name} default {default} is above maximum {maximum}")


def validate_dsl(document: dict[str, Any]) -> DslDocument:
    """Validate a DSL document against the public schema and semantic rules."""

    try:
        validate_contract(DSL_SCHEMA, document)
    except ContractValidationError as error:
        _fail(DslErrorKind.SCHEMA, str(error))

    inputs = tuple(document["inputs"])
    input_set = frozenset(inputs)
    parameters: dict[str, dict[str, Any]] = {
        str(name): dict(definition) for name, definition in document["parameters"].items()
    }
    nodes: dict[str, dict[str, Any]] = {
        str(name): dict(node) for name, node in document["nodes"].items()
    }
    limits_data = document.get("limits", {})
    limits = DslLimits(
        max_nodes=int(limits_data.get("max_nodes", DEFAULT_MAX_NODES)),
        max_depth=int(limits_data.get("max_depth", DEFAULT_MAX_DEPTH)),
    )

    if len(nodes) > limits.max_nodes:
        _fail(DslErrorKind.LIMIT, f"node count {len(nodes)} exceeds max_nodes {limits.max_nodes}")

    _validate_parameters(parameters)

    node_types: dict[str, str] = {}
    memo: dict[str, str] = {}
    visiting: set[str] = set()
    for node_id in nodes:
        node_types[node_id] = _infer_type(node_id, nodes, parameters, input_set, memo, visiting)

    depth_memo: dict[str, int] = {}
    for node_id in nodes:
        _depth_of(node_id, nodes, node_types, limits, depth_memo, set())

    for node_id, node in nodes.items():
        _validate_operand_kinds(node_id, node, node_types)
        _validate_window_refs(node_id, node, nodes, parameters)

    signal_data = document["signal"]
    signal_node = str(signal_data["node"])
    if signal_node not in nodes:
        _fail(DslErrorKind.UNKNOWN_NODE, f"signal node {signal_node} is not defined")
    if node_types[signal_node] != "boolean":
        _fail(DslErrorKind.TYPE, f"signal node {signal_node} must produce boolean, got {node_types[signal_node]}")

    return DslDocument(
        raw=document,
        strategy_id=str(document["strategy_id"]),
        strategy_version=str(document["strategy_version"]),
        inputs=inputs,
        parameters=parameters,
        nodes=nodes,
        node_types=node_types,
        signal=DslSignal(
            node=signal_node,
            label=str(signal_data["label"]),
            reason=str(signal_data["reason"]),
            risk_tags=tuple(str(tag) for tag in signal_data.get("risk_tags", [])),
        ),
        limits=limits,
    )
