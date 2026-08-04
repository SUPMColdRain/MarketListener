"""Explicit, loss-aware migration for historical Provider Contract v1 reports."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from ..contracts import ContractValidationError, validate_contract
from .base import (
    Capability,
    CapabilityRegistration,
    CapabilityStatus,
    ErrorCategory,
    ProviderError,
    ProviderOperation,
    ProviderRequest,
    ProviderRunResult,
    SourceDescription,
    _migrated_v1_capability,
)


def migrate_v1_provider_run_result(document: Mapping[str, Any]) -> ProviderRunResult:
    """Convert one v1 result to v2 without discarding legacy status or errors.

    v1 had a source-wide status and could place a failure only at run level. In
    v2 that error becomes an explicit synthetic capability, while the old status
    remains visible in ``migration`` metadata. Unknown capability labels are
    retained as registration descriptions and routed to the explicit ``other``
    operation by the legacy registration mapper.
    """

    if not isinstance(document, dict):
        raise ValueError("v1 Provider report must be a JSON object")
    try:
        validate_contract("provider-run-result-v1.schema.json", document)
    except ContractValidationError as error:
        raise ValueError(f"invalid v1 Provider report: {error}") from error
    provider = _legacy_name(document, "provider")
    legacy_status = _status(document.get("status"), "status")
    source = SourceDescription(
        id=_technical_id("source", provider, 0),
        display_name=_source_display_name(provider),
        description=f"Migrated v1 source report for {provider}",
        legacy_name=provider,
    )
    identities_by_id: dict[str, tuple[str, str, int]] = {}
    occurrences: dict[str, int] = {}
    capabilities = []
    for item in _array(document, "capabilities"):
        legacy_name = _legacy_name(item, "name")
        occurrence = occurrences.get(legacy_name, 0)
        occurrences[legacy_name] = occurrence + 1
        technical_id = _technical_id("capability", legacy_name, occurrence)
        _reserve_technical_id(
            identities_by_id, technical_id, ("capability", legacy_name, occurrence)
        )
        capabilities.append(_migrate_capability(item, technical_id, occurrence))
    error = document.get("error")
    if error is not None:
        if not isinstance(error, Mapping):
            raise ValueError("v1 error must be an object")
        synthetic_name = _technical_id("root-error", "provider-run-error", 0)
        _reserve_technical_id(
            identities_by_id,
            synthetic_name,
            ("root-error", "provider-run-error", 0),
        )
        capabilities.append(
            Capability(
                synthetic_name,
                CapabilityStatus.FAILED,
                registration=CapabilityRegistration(
                    synthetic_name,
                    "Migrated v1 root-level error",
                    ProviderRequest(ProviderOperation.OTHER),
                ),
                error=ProviderError(
                    _error_category(error.get("category")), _string(error, "message")
                ),
            )
        )
    return ProviderRunResult(
        run_id=_string(document, "run_id"),
        source=source,
        started_at=_string(document, "started_at"),
        completed_at=_string(document, "completed_at"),
        capabilities=tuple(capabilities),
        migration={"from_schema_version": 1, "legacy_provider_status": legacy_status.value},
    )


def _migrate_capability(
    value: Mapping[str, Any], technical_id: str, occurrence: int
) -> Capability:
    if not isinstance(value, Mapping):
        raise ValueError("v1 capabilities must contain objects")
    allowed = {"name", "status", "detail", "row_count", "earliest", "latest"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"v1 capability has unsupported fields: {', '.join(sorted(unknown))}")
    row_count = value.get("row_count")
    if row_count is not None and (not isinstance(row_count, int) or isinstance(row_count, bool)):
        raise ValueError("v1 row_count must be an integer")
    return _migrated_v1_capability(
        _legacy_name(value, "name"),
        technical_id,
        occurrence,
        _status(value.get("status"), "capability status"),
        detail=_optional_string(value.get("detail"), "detail"),
        row_count=row_count,
        earliest=_optional_string(value.get("earliest"), "earliest"),
        latest=_optional_string(value.get("latest"), "latest"),
    )


def _string(value: Mapping[str, Any], key: str) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate.strip():
        raise ValueError(f"v1 {key} must be a non-empty string")
    return candidate


def _legacy_name(value: Mapping[str, Any], key: str) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate:
        raise ValueError(f"v1 {key} must be a minLength-1 string")
    return candidate


def _optional_string(value: object, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"v1 {key} must be a non-empty string when present")
    return value


def _array(value: Mapping[str, Any], key: str) -> list[object]:
    candidate = value.get(key)
    if not isinstance(candidate, list):
        raise ValueError(f"v1 {key} must be an array")
    return candidate


def _status(value: object, key: str) -> CapabilityStatus:
    try:
        return CapabilityStatus(str(value))
    except ValueError as error:
        raise ValueError(f"v1 {key} is invalid: {value!r}") from error


def _error_category(value: object) -> ErrorCategory:
    try:
        return ErrorCategory(str(value))
    except ValueError as error:
        raise ValueError(f"v1 error category is invalid: {value!r}") from error


def _technical_id(
    domain: str,
    legacy_name: str,
    occurrence: int,
) -> str:
    """Derive an order-independent v2 ID from raw UTF-8 identity bytes."""

    digest_input = (
        domain.encode("utf-8")
        + b"\0"
        + legacy_name.encode("utf-8")
        + b"\0"
        + occurrence.to_bytes(8, "big", signed=False)
    )
    prefix = "migration-root-error" if domain == "root-error" else "legacy"
    digest = sha256(digest_input).hexdigest()[: 64 - len(prefix) - 1]
    return f"{prefix}-{digest}"


def _reserve_technical_id(
    identities_by_id: dict[str, tuple[str, str, int]],
    technical_id: str,
    identity: tuple[str, str, int],
) -> None:
    existing = identities_by_id.setdefault(technical_id, identity)
    if existing != identity:
        raise ValueError("SHA-256 technical ID collision between distinct v1 identities")


def _source_display_name(legacy_name: str) -> str:
    return legacy_name if legacy_name.strip() else "Migrated v1 source (blank legacy name)"
