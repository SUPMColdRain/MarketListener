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
PROVIDER_V1_SCHEMA = "provider-run-result-v1.schema.json"


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
    if schema_name == "provider-run-result.schema.json":
        _validate_provider_run_result_semantics(document)
    if schema_name == PROVIDER_V1_SCHEMA:
        _validate_provider_v1_format_semantics(document)


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


def _validate_provider_run_result_semantics(document: dict[str, Any]) -> None:
    """Apply v2 cross-field constraints that JSON Schema cannot express alone."""

    try:
        from .providers.base import (
            AssetType,
            CapabilityEvidence,
            CapabilityRegistration,
            CapabilityStatus,
            ErrorCategory,
            Market,
            ProviderError,
            ProviderOperation,
            ProviderRequest,
            ProviderRunResult,
            SourceDescription,
        )

        source_data = document["source"]
        source = SourceDescription(**source_data)
        capabilities = []
        for item in document["capabilities"]:
            registration_data = item["registration"]
            request_data = registration_data["request"]
            request = ProviderRequest(
                ProviderOperation(request_data["operation"]),
                Market(request_data["market"]),
                AssetType(request_data["asset_type"]),
                period=request_data.get("period"),
                start_date=request_data.get("start_date"),
                end_date=request_data.get("end_date"),
                instrument=request_data.get("instrument"),
                parameters=request_data.get("parameters", {}),
            )
            registration = CapabilityRegistration(
                registration_data["id"],
                registration_data["description"],
                request,
                tuple(registration_data.get("required_permissions", [])),
                legacy_name=registration_data.get("legacy_name"),
                legacy_occurrence=registration_data.get("legacy_occurrence"),
            )
            evidence_data = item["evidence"]
            evidence = CapabilityEvidence(**evidence_data)
            error_data = item.get("error")
            error = ProviderError(ErrorCategory(error_data["category"]), error_data["message"]) if error_data else None
            from .providers.base import Capability

            capabilities.append(
                Capability(
                    registration.id,
                    CapabilityStatus(item["status"]),
                    registration=registration,
                    probed_at=item["probed_at"],
                    limitations=tuple(item.get("limitations", [])),
                    evidence=evidence,
                    error=error,
                )
            )
        ProviderRunResult(
            document["run_id"], source, document["started_at"], document["completed_at"], tuple(capabilities),
            migration=document.get("migration"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ContractValidationError(str(error)) from error


def _validate_provider_v1_format_semantics(document: dict[str, Any]) -> None:
    """Make historical v1 date-time format checks as strict as v2 migration."""

    try:
        from .providers.base import _parse_datetime

        _parse_datetime(document["started_at"], "started_at")
        _parse_datetime(document["completed_at"], "completed_at")
        for capability in document["capabilities"]:
            for field_name in ("earliest", "latest"):
                if field_name in capability:
                    _parse_datetime(capability[field_name], f"capability {field_name}")
    except (KeyError, TypeError, ValueError) as error:
        raise ContractValidationError(str(error)) from error
