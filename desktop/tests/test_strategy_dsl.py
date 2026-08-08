"""FULL-400/401 desktop evidence: schema, safety boundary, reference interpreter, scanner."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from market_monitor.strategy_dsl import (
    DslErrorKind,
    StrategyDslError,
    backtest,
    evaluate,
    scan_strategy,
    validate_dsl,
    write_run_record,
)


ROOT = Path(__file__).resolve().parents[2]
DSL_FIXTURES = ROOT / "tests" / "fixtures" / "dsl"
CASES = json.loads((DSL_FIXTURES / "cases.json").read_text(encoding="utf-8"))


def load_document(fixture: str) -> dict:
    fixture = fixture if fixture.startswith("dsl/") else f"dsl/{fixture}"
    return json.loads((ROOT / "tests" / "fixtures" / fixture).read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_dsl_fixture_cases(case: dict) -> None:
    document = load_document(str(case["fixture"]))
    if case["valid"]:
        validate_dsl(document)
    else:
        with pytest.raises(StrategyDslError):
            validate_dsl(document)


@pytest.mark.parametrize(
    ("fixture", "kind"),
    [
        ("invalid/unknown-node-type.json", DslErrorKind.SCHEMA),
        ("invalid/network-node.json", DslErrorKind.SCHEMA),
        ("invalid/file-node.json", DslErrorKind.SCHEMA),
        ("invalid/arbitrary-code.json", DslErrorKind.SCHEMA),
        ("invalid/missing-input.json", DslErrorKind.UNKNOWN_NODE),
        ("invalid/unknown-parameter.json", DslErrorKind.UNKNOWN_NODE),
        ("invalid/non-boolean-signal.json", DslErrorKind.TYPE),
        ("invalid/missing-signal-node.json", DslErrorKind.UNKNOWN_NODE),
        ("invalid/cycle.json", DslErrorKind.CYCLE),
        ("invalid/too-deep.json", DslErrorKind.LIMIT),
        ("invalid/too-many-nodes.json", DslErrorKind.LIMIT),
        ("invalid/bad-parameter-default.json", DslErrorKind.PARAMETER),
        ("invalid/ifelse-type-mismatch.json", DslErrorKind.TYPE),
    ],
)
def test_dsl_rejection_kinds(fixture: str, kind: DslErrorKind) -> None:
    with pytest.raises(StrategyDslError) as caught:
        validate_dsl(load_document(fixture))
    assert caught.value.kind == kind


def test_unknown_node_type_with_code_is_rejected_before_evaluation() -> None:
    document = load_document("invalid/arbitrary-code.json")
    with pytest.raises(StrategyDslError) as caught:
        validate_dsl(document)
    assert caught.value.kind in {DslErrorKind.SCHEMA, DslErrorKind.UNKNOWN_NODE}


def test_ma_cross_reference_semantics() -> None:
    document = validate_dsl(load_document("valid/ma-cross.json"))
    closes = [10.0, 10.5, 10.2, 10.8, 11.2, 11.0, 10.6, 10.9, 11.5, 12.0]
    evaluation = evaluate(
        document,
        {"close": closes},
        parameters={"fast_window": 2, "slow_window": 3},
        output_nodes=["fast_sma", "slow_sma"],
    )
    assert evaluation.signal_indices == (4, 8)
    assert evaluation.node_values["fast_sma"] == (
        None,
        10.25,
        10.35,
        10.5,
        11.0,
        11.1,
        10.8,
        10.75,
        11.2,
        11.75,
    )
    assert evaluation.node_values["slow_sma"][2] == pytest.approx(10.233333333333333)


def test_roc_and_threshold_semantics() -> None:
    document = validate_dsl(
        {
            "schema_version": 1,
            "strategy_id": "roc_test",
            "strategy_version": "1.0.0",
            "inputs": ["close"],
            "parameters": {"threshold": {"type": "number", "default": 0.05}},
            "nodes": {
                "close_series": {"type": "series", "input": "close"},
                "threshold_param": {"type": "parameter", "name": "threshold"},
                "close_roc": {"type": "roc", "operand": "close_series", "window": 2},
                "above": {"type": "gt", "left": "close_roc", "right": "threshold_param"},
            },
            "signal": {"node": "above", "label": "roc", "reason": "test", "risk_tags": []},
        }
    )
    evaluation = evaluate(
        document,
        {"close": [10.0, 10.5, 10.2, 10.8, 11.2, 11.0, 10.6, 10.9, 11.5, 12.0]},
        output_nodes=["close_roc"],
    )
    assert evaluation.signal_indices == (4, 8, 9)
    roc = evaluation.node_values["close_roc"]
    assert roc[0] is None and roc[1] is None
    assert roc[2] == pytest.approx(0.02)


def test_no_future_function_window_uses_only_current_and_previous_bars() -> None:
    document = validate_dsl(
        {
            "schema_version": 1,
            "strategy_id": "no_future",
            "strategy_version": "1.0.0",
            "inputs": ["close"],
            "parameters": {},
            "nodes": {
                "close_series": {"type": "series", "input": "close"},
                "fast_sma": {"type": "sma", "operand": "close_series", "window": 2},
                "value_100": {"type": "value", "value": 100.0},
                "above": {"type": "gte", "left": "fast_sma", "right": "value_100"},
            },
            "signal": {"node": "above", "label": "x", "reason": "y", "risk_tags": []},
        }
    )
    # The first signal must depend only on bars 0..t. If the interpreter peeked
    # one bar ahead, adding a large future close would change earlier results.
    short = evaluate(document, {"close": [99.0, 101.0]})
    long_series = evaluate(document, {"close": [99.0, 101.0, 1000.0, 1000.0, 1000.0]})
    assert short.signal == (False, True)
    assert long_series.signal[:2] == (False, True)


def test_division_by_zero_is_classified_as_numeric_error() -> None:
    document = validate_dsl(
        {
            "schema_version": 1,
            "strategy_id": "div_zero",
            "strategy_version": "1.0.0",
            "inputs": ["close"],
            "parameters": {},
            "nodes": {
                "close_series": {"type": "series", "input": "close"},
                "zero": {"type": "value", "value": 0.0},
                "bad": {"type": "divide", "left": "close_series", "right": "zero"},
                "value_1": {"type": "value", "value": 1.0},
                "above": {"type": "gt", "left": "bad", "right": "value_1"},
            },
            "signal": {"node": "above", "label": "x", "reason": "y", "risk_tags": []},
        }
    )
    with pytest.raises(StrategyDslError) as caught:
        evaluate(document, {"close": [1.0, 2.0]})
    assert caught.value.kind == DslErrorKind.NUMERIC


def test_parameter_bounds_and_types_are_enforced() -> None:
    document = validate_dsl(load_document("valid/ma-cross.json"))
    with pytest.raises(StrategyDslError) as caught:
        evaluate(document, {"close": [1.0, 2.0]}, parameters={"fast_window": 1})
    assert caught.value.kind == DslErrorKind.PARAMETER
    with pytest.raises(StrategyDslError) as caught:
        evaluate(document, {"close": [1.0, 2.0]}, parameters={"unknown": 3})
    assert caught.value.kind == DslErrorKind.PARAMETER


def test_timeout_and_operation_budget_are_enforced() -> None:
    document = validate_dsl(load_document("valid/ma-cross.json"))
    long_series = {"close": [100.0 + index * 0.01 for index in range(200_000)]}
    with pytest.raises(StrategyDslError) as caught:
        evaluate(document, long_series, timeout_seconds=0.000001)
    assert caught.value.kind == DslErrorKind.TIMEOUT
    with pytest.raises(StrategyDslError) as caught:
        evaluate(document, {"close": [100.0, 101.0, 102.0]}, max_ops=5)
    assert caught.value.kind == DslErrorKind.LIMIT


def test_cancellation_stops_evaluation() -> None:
    document = validate_dsl(load_document("valid/ma-cross.json"))
    cancelled = False

    def request_cancel() -> bool:
        return cancelled

    cancelled = True
    with pytest.raises(StrategyDslError) as caught:
        evaluate(document, {"close": [1.0, 2.0, 3.0, 4.0]}, is_cancelled=request_cancel)
    assert caught.value.kind == DslErrorKind.CANCELLED


def test_empty_or_missing_series_is_no_data() -> None:
    document = validate_dsl(load_document("valid/ma-cross.json"))
    with pytest.raises(StrategyDslError) as caught:
        evaluate(document, {"close": []})
    assert caught.value.kind == DslErrorKind.NO_DATA
    with pytest.raises(StrategyDslError) as caught:
        evaluate(document, {"open": [1.0]})
    assert caught.value.kind == DslErrorKind.NO_DATA


def test_scan_records_versions_and_writes_run_record(tmp_path) -> None:
    document = validate_dsl(load_document("valid/ma-cross.json"))
    bars = [
        {
            "instrument_id": "CN.SSE.STOCK.600519",
            "bar_open_time": f"2026-08-{day:02d}T09:30:00+08:00",
            "close": close,
        }
        for day, close in enumerate([10.0, 10.5, 10.2, 10.8, 11.2, 11.0, 10.6, 10.9, 11.5, 12.0], start=1)
    ]
    report = scan_strategy(
        document,
        {"CN.SSE.STOCK.600519": bars},
        parameters={"fast_window": 2, "slow_window": 3},
    )
    assert report.status == "PASS"
    assert report.strategy_version == "1.0.0"
    assert report.data_version and report.parameter_version
    assert report.instruments[0].signal_count == 2
    assert report.instruments[0].signals[0].label == "快线上穿慢线"
    assert report.instruments[0].signals[0].risk_tags
    assert report.error is None

    path = write_run_record(tmp_path / "runs" / "run.json", report)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 1
    assert saved["data_version"] == report.data_version
    assert saved["parameter_version"] == report.parameter_version
    assert saved["status"] == "PASS"
    assert saved["strategy_id"] == "ma_cross_demo"


def test_scan_partial_failure_keeps_prior_instrument_results() -> None:
    document = validate_dsl(load_document("valid/ma-cross.json"))
    good = [{"bar_open_time": "2026-08-01T09:30:00+08:00", "close": 10.0}]
    bad = [{"bar_open_time": "2026-08-01T09:30:00+08:00"}]  # missing close
    report = scan_strategy(document, {"good": good, "bad": bad})
    assert report.status == "FAILED"
    assert report.error is not None
    assert report.instruments[0].instrument_id == "good"


def test_backtest_timeline_is_observation_only() -> None:
    document = validate_dsl(load_document("valid/ma-cross.json"))
    bars = [
        {
            "bar_open_time": f"2026-08-{day:02d}T09:30:00+08:00",
            "close": close,
        }
        for day, close in enumerate([10.0, 10.5, 10.2, 10.8, 11.2], start=1)
    ]
    result = backtest(document, bars, parameters={"fast_window": 2, "slow_window": 3})
    assert result.report.status == "PASS"
    assert result.timeline[0] == ("2026-08-01T09:30:00+08:00", 0, False)
    assert any(signal for _, _, signal in result.timeline)


def _assert_vector_matches(vector: dict) -> None:
    document = validate_dsl(vector["strategy"])
    series = {name: [float(value) for value in values] for name, values in vector["series"].items()}
    evaluation = evaluate(
        document,
        series,
        parameters=vector["parameters"],
        output_nodes=list(vector["expected"]["node_values"]),
    )
    expected = vector["expected"]
    assert list(evaluation.signal) == expected["signals"]
    assert evaluation.signal_indices == tuple(expected["signal_indices"])
    tolerance = float(expected.get("numeric_tolerance", 1e-9))
    for node_id, values in expected["node_values"].items():
        actual = evaluation.node_values[node_id]
        assert node_id in evaluation.node_values, f"node {node_id} was not captured"
        for expected_value, actual_value in zip(values, actual):
            if expected_value is None:
                assert actual_value is None
            else:
                assert actual_value is not None
                assert math.isclose(float(actual_value), float(expected_value), rel_tol=tolerance, abs_tol=tolerance)


@pytest.mark.parametrize(
    "vector",
    json.loads((DSL_FIXTURES / "vectors.json").read_text(encoding="utf-8"))["vectors"],
    ids=lambda vector: vector["id"],
)
def test_shared_vectors_pass_desktop_reference(vector: dict) -> None:
    _assert_vector_matches(vector)
