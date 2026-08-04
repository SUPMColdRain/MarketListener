"""Validation entry points for the versioned D0 data contracts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from datetime import datetime

from jsonschema import Draft202012Validator, FormatChecker


CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"
BAR_SCHEMA = "bar.schema.json"


class ContractValidationError(ValueError):
    """Raised when a document does not satisfy its public contract."""


@lru_cache
def load_schema(schema_name: str) -> dict[str, Any]:
    """Load one checked-in schema without accepting arbitrary file paths."""

    path = CONTRACTS_DIR / schema_name
    if path.parent != CONTRACTS_DIR or not path.is_file():
        raise ContractValidationError(f"Unknown contract schema: {schema_name}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(schema_name: str, document: dict[str, Any]) -> None:
    """Validate schema rules and the small set of cross-field bar rules."""

    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        raise ContractValidationError(errors[0].message)
    if schema_name == BAR_SCHEMA:
        _validate_bar_semantics(document)


def _validate_bar_semantics(bar: dict[str, Any]) -> None:
    low = bar["low"]
    high = bar["high"]
    open_price = bar["open"]
    close = bar["close"]
    if low > min(open_price, close) or high < max(open_price, close) or low > high:
        raise ContractValidationError("bar low/high must bound open and close")
    open_time = datetime.fromisoformat(bar["bar_open_time"].replace("Z", "+00:00"))
    close_time = datetime.fromisoformat(bar["bar_close_time"].replace("Z", "+00:00"))
    if open_time >= close_time:
        raise ContractValidationError("bar_open_time must be before bar_close_time")
