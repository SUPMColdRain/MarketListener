"""Version 2 source-neutral provider contract.

The contract deliberately has no provider-wide availability flag.  A source
may expose a working calendar while its bar capability is blocked, failed, or
unsupported; callers must inspect the matching capability record instead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


_CAPABILITY_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$")
_MIGRATED_CAPABILITY_ID_PREFIX = "legacy-"
_MIGRATION_ROOT_ERROR_ID_PREFIX = "migration-root-error-"
_LEGACY_ADAPTER_CAPABILITY_PATTERNS = (
    re.compile(r"health_check|a_share_(?:rise_fall|price_limit)_counts|market_fund_flow"),
    re.compile(r"trading_calendar|cn_stock_(?:sh\.600519|sz\.000001)_(?:1d|30m)|adjust_factor_(?:sh\.600519|sz\.000001)"),
    re.compile(r"health_check|cn_(?:stock|etf)_(?:600519\.XSHG|000001\.XSHE|510300\.XSHG|159915\.XSHE)_(?:1d|30m|1m)|cn_index_(?:1d|30m|1m)|cn_future_discovery|cn_future_[A-Za-z0-9.]+_(?:1d|30m|1m)"),
    re.compile(r"package_installation|license_and_maintenance|callable_api|hk_stock_index_future"),
)


class CapabilityStatus(StrEnum):
    PASS = "PASS"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"
    BLOCKED = "BLOCKED"


class ErrorCategory(StrEnum):
    AUTHENTICATION = "AUTH"
    QUOTA = "RATE_LIMIT"
    NETWORK = "NETWORK"
    FIELD_CHANGE = "PROVIDER"
    NO_COVERAGE = "NO_COVERAGE"
    CONFIGURATION = "CONFIGURATION"
    UNKNOWN = "UNKNOWN"


class ProviderOperation(StrEnum):
    HEALTH_CHECK = "health_check"
    INSTRUMENTS = "instruments"
    BARS = "bars"
    INDICATORS = "indicators"
    CALENDAR = "calendar"
    OTHER = "other"


class Market(StrEnum):
    GLOBAL = "GLOBAL"
    CN = "CN"
    HK = "HK"
    US = "US"


class AssetType(StrEnum):
    GENERAL = "GENERAL"
    STOCK = "STOCK"
    ETF = "ETF"
    INDEX = "INDEX"
    FUTURE = "FUTURE"


@dataclass(frozen=True)
class ProviderError(Exception):
    category: ErrorCategory
    message: str

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("ProviderError message must not be blank")

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, str]:
        return {"category": self.category.value, "message": self.message}


@dataclass(frozen=True)
class ProviderRequest:
    """A request identifies the capability it needs without source-specific names."""

    operation: ProviderOperation
    market: Market = Market.GLOBAL
    asset_type: AssetType = AssetType.GENERAL
    period: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    instrument: str | None = None
    parameters: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("period", "start_date", "end_date", "instrument"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field_name} must not be blank when provided")
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be supplied together")
        if self.start_date is not None and self.end_date is not None:
            try:
                if not _ISO_DATE.fullmatch(self.start_date) or not _ISO_DATE.fullmatch(self.end_date):
                    raise ValueError("dates must use YYYY-MM-DD")
                if date.fromisoformat(self.start_date) > date.fromisoformat(self.end_date):
                    raise ValueError("start_date must not be after end_date")
            except ValueError as error:
                if str(error) == "start_date must not be after end_date":
                    raise
                raise ValueError("dates must use YYYY-MM-DD") from error
        if not isinstance(self.parameters, Mapping):
            raise ValueError("request parameters must be an object")
        if any(
            not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip()
            for key, value in self.parameters.items()
        ):
            raise ValueError("request parameters must be non-blank string pairs")
        if self.operation is ProviderOperation.BARS:
            if self.market is Market.GLOBAL or self.asset_type is AssetType.GENERAL or self.period is None:
                raise ValueError("bars requests require market, asset_type, and period")
        elif self.operation in (ProviderOperation.HEALTH_CHECK, ProviderOperation.CALENDAR):
            if (
                self.period is not None
                or self.instrument is not None
                or self.start_date is not None
                or self.end_date is not None
                or self.asset_type is not AssetType.GENERAL
            ):
                raise ValueError(f"{self.operation.value} requests only allow market and parameters")
        elif self.period is not None:
            raise ValueError(f"{self.operation.value} requests must not specify period")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "operation": self.operation.value,
            "market": self.market.value,
            "asset_type": self.asset_type.value,
        }
        for key in ("period", "start_date", "end_date", "instrument"):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        if self.parameters:
            payload["parameters"] = dict(self.parameters)
        return payload


@dataclass(frozen=True)
class SourceDescription:
    id: str
    display_name: str
    description: str
    website: str | None = None
    legacy_name: str | None = None

    def __post_init__(self) -> None:
        if not _CAPABILITY_ID.fullmatch(self.id):
            raise ValueError("source id must be lowercase kebab-case")
        if not self.display_name.strip() or not self.description.strip():
            raise ValueError("source display_name and description must not be blank")
        if self.website and not urlparse(self.website).scheme:
            raise ValueError("source website must be a URI")
        if self.legacy_name is not None and (
            not isinstance(self.legacy_name, str) or not self.legacy_name
        ):
            raise ValueError("legacy source name must be a non-empty string when present")

    def to_dict(self) -> dict[str, str]:
        payload = {"id": self.id, "display_name": self.display_name, "description": self.description}
        if self.website:
            payload["website"] = self.website
        if self.legacy_name is not None:
            payload["legacy_name"] = self.legacy_name
        return payload


@dataclass(frozen=True)
class CapabilityRegistration:
    id: str
    description: str
    request: ProviderRequest
    required_permissions: Sequence[str] = ()
    legacy_name: str | None = None
    legacy_occurrence: int | None = None

    def __post_init__(self) -> None:
        if not _CAPABILITY_ID.fullmatch(self.id):
            raise ValueError("capability id must be lowercase kebab-case")
        if not self.description.strip():
            raise ValueError("capability description must not be blank")
        if any(not permission.strip() for permission in self.required_permissions):
            raise ValueError("required permissions must not be blank")
        if len(self.required_permissions) != len(set(self.required_permissions)):
            raise ValueError("required permissions must be unique")
        if (self.legacy_name is None) != (self.legacy_occurrence is None):
            raise ValueError("legacy_name and legacy_occurrence must be supplied together")
        if self.legacy_name is not None and (
            not isinstance(self.legacy_name, str) or not self.legacy_name
        ):
            raise ValueError("legacy capability name must be a non-empty string")
        if self.legacy_occurrence is not None and (
            not isinstance(self.legacy_occurrence, int)
            or isinstance(self.legacy_occurrence, bool)
            or self.legacy_occurrence < 0
        ):
            raise ValueError("legacy occurrence must be a non-negative integer")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "description": self.description,
            "request": self.request.to_dict(),
        }
        if self.required_permissions:
            payload["required_permissions"] = list(self.required_permissions)
        if self.legacy_name is not None:
            payload["legacy_name"] = self.legacy_name
            payload["legacy_occurrence"] = self.legacy_occurrence
        return payload


@dataclass(frozen=True)
class CapabilityEvidence:
    summary: str
    row_count: int | None = None
    earliest: str | None = None
    latest: str | None = None

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("evidence summary must not be blank")
        if self.row_count is not None and self.row_count < 0:
            raise ValueError("row_count must be non-negative")
        earliest = _parse_datetime(self.earliest, "earliest") if self.earliest is not None else None
        latest = _parse_datetime(self.latest, "latest") if self.latest is not None else None
        if earliest and latest and earliest > latest:
            raise ValueError("evidence earliest must not be after latest")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"summary": self.summary}
        for key in ("row_count", "earliest", "latest"):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload


@dataclass(frozen=True)
class Capability:
    """One independently probed capability.

    ``registration`` is mandatory. Legacy adapters and v1 migration use private
    compatibility bridges; new v2 callers cannot
    silently turn an unknown name into an ``other`` request.
    """

    name: str
    status: CapabilityStatus
    detail: str | None = None
    row_count: int | None = None
    earliest: str | None = None
    latest: str | None = None
    registration: CapabilityRegistration | None = None
    probed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    limitations: Sequence[str] = ()
    evidence: CapabilityEvidence | None = None
    error: ProviderError | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("capability name must not be blank")
        if self.row_count is not None and self.row_count < 0:
            raise ValueError("row_count must be non-negative")
        _parse_datetime(self.probed_at, "probed_at")
        registration = self.registration
        if registration is None:
            raise ValueError("v2 capabilities require an explicit registration")
        if registration.id != _normalise_capability_id(self.name):
            raise ValueError("capability name must match registration id")
        object.__setattr__(self, "registration", registration)
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("limitations must not be blank")
        if len(self.limitations) != len(set(self.limitations)):
            raise ValueError("limitations must be unique")
        if self.status is CapabilityStatus.PASS and self.error:
            raise ValueError("a PASS capability must not contain an error")
        if self.status is CapabilityStatus.BLOCKED and not self.limitations and not self.error:
            raise ValueError("a BLOCKED capability requires a limitation or error")

    def to_dict(self) -> dict[str, object]:
        evidence = self.evidence or CapabilityEvidence(
            summary=self.detail or "legacy adapter returned no detail",
            row_count=self.row_count,
            earliest=self.earliest,
            latest=self.latest,
        )
        payload: dict[str, object] = {
            "registration": self.registration.to_dict(),
            "status": self.status.value,
            "probed_at": self.probed_at,
            "evidence": evidence.to_dict(),
        }
        if self.limitations:
            payload["limitations"] = list(self.limitations)
        if self.error:
            payload["error"] = self.error.to_dict()
        return payload


@dataclass(frozen=True)
class FetchResult:
    records: Sequence[Mapping[str, Any]]
    earliest: str | None = None
    latest: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class ProviderRunResult:
    run_id: str
    source: SourceDescription
    started_at: str
    completed_at: str
    capabilities: Sequence[Capability]
    schema_version: int = 2
    migration: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not self.run_id.strip() or self.schema_version != 2:
            raise ValueError("ProviderRunResult requires a non-empty run_id and schema_version 2")
        started_at = _parse_datetime(self.started_at, "started_at")
        completed_at = _parse_datetime(self.completed_at, "completed_at")
        if started_at > completed_at:
            raise ValueError("started_at must not be after completed_at")
        identifiers = [capability.registration.id for capability in self.capabilities]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("capability registration ids must be unique per run")
        if self.migration is None:
            self._validate_normal_v2_report()
        else:
            expected = {"from_schema_version", "legacy_provider_status"}
            if set(self.migration) != set(expected) or self.migration.get("from_schema_version") != 1:
                raise ValueError("migration metadata must preserve v1 source status")
            try:
                legacy_status = CapabilityStatus(str(self.migration["legacy_provider_status"]))
            except ValueError as error:
                raise ValueError("migration legacy_provider_status is invalid") from error
            if legacy_status is CapabilityStatus.BLOCKED:
                raise ValueError("v1 migration cannot contain BLOCKED status")
            self._validate_v1_migration_report()

    def _validate_normal_v2_report(self) -> None:
        if self.source.legacy_name is not None or _has_reserved_migration_prefix(self.source.id):
            raise ValueError("ordinary v2 reports must not use migration source fields or identifiers")
        for capability in self.capabilities:
            registration = capability.registration
            if (
                registration.legacy_name is not None
                or registration.legacy_occurrence is not None
                or _has_reserved_migration_prefix(registration.id)
            ):
                raise ValueError("ordinary v2 reports must not use migration capability fields or identifiers")

    def _validate_v1_migration_report(self) -> None:
        if self.source.legacy_name is None or not self.source.id.startswith(_MIGRATED_CAPABILITY_ID_PREFIX):
            raise ValueError("v1 migration reports require a legacy source name and identifier")
        root_errors = 0
        for capability in self.capabilities:
            registration = capability.registration
            if registration.id.startswith(_MIGRATED_CAPABILITY_ID_PREFIX):
                if registration.legacy_name is None or registration.legacy_occurrence is None:
                    raise ValueError("migrated capabilities require legacy name and occurrence")
                continue
            if registration.id.startswith(_MIGRATION_ROOT_ERROR_ID_PREFIX):
                root_errors += 1
                self._validate_migration_root_error(capability)
                continue
            raise ValueError("v1 migration reports may contain only migrated capabilities and root error")
        if root_errors > 1:
            raise ValueError("v1 migration reports may contain at most one root error")

    @staticmethod
    def _validate_migration_root_error(capability: Capability) -> None:
        registration = capability.registration
        request = registration.request
        if registration.legacy_name is not None or registration.legacy_occurrence is not None:
            raise ValueError("migration root error must not carry legacy capability identity")
        if (
            capability.status is not CapabilityStatus.FAILED
            or capability.error is None
            or registration.description != "Migrated v1 root-level error"
        ):
            raise ValueError("migration root error must be a failed synthetic v1 error capability")
        if (
            request.operation is not ProviderOperation.OTHER
            or request.market is not Market.GLOBAL
            or request.asset_type is not AssetType.GENERAL
            or request.period is not None
            or request.start_date is not None
            or request.end_date is not None
            or request.instrument is not None
            or request.parameters
            or capability.limitations
            or capability.detail is not None
            or capability.row_count is not None
            or capability.earliest is not None
            or capability.latest is not None
        ):
            raise ValueError("migration root error must use the synthetic v1 error semantics")
        if capability.evidence is not None and capability.evidence != CapabilityEvidence(
            "legacy adapter returned no detail"
        ):
            raise ValueError("migration root error must use the synthetic v1 error evidence")

    @property
    def provider(self) -> str:
        """Compatibility read-only identifier; it is not an availability status."""

        return self.source.id

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": 2,
            "run_id": self.run_id,
            "source": self.source.to_dict(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "capabilities": [capability.to_dict() for capability in self.capabilities],
        }
        if self.migration:
            payload["migration"] = dict(self.migration)
        return payload


class Provider(ABC):
    """Provider implementations expose legacy operations behind a v2 request API."""

    name: str
    source_description: SourceDescription | None = None

    @property
    def source(self) -> SourceDescription:
        return self.source_description or SourceDescription(
            id=_normalise_capability_id(self.name),
            display_name=self.name,
            description=f"{self.name} external market-data source",
        )

    @abstractmethod
    def probe_capabilities(self) -> Sequence[Capability]:
        """Probe capabilities independently; never infer one result from another."""

    def fetch(self, request: ProviderRequest) -> FetchResult:
        """Dispatch a validated source-neutral request to the legacy adapter hooks."""

        if request.operation is ProviderOperation.HEALTH_CHECK:
            return self.health_check()
        if request.operation is ProviderOperation.INSTRUMENTS:
            return self.fetch_instruments()
        if request.operation is ProviderOperation.BARS:
            return self.fetch_bars()
        if request.operation is ProviderOperation.INDICATORS:
            return self.fetch_indicators()
        if request.operation is ProviderOperation.CALENDAR:
            return self.fetch_calendar()
        raise ProviderError(ErrorCategory.NO_COVERAGE, f"unsupported provider operation: {request.operation.value}")

    @abstractmethod
    def fetch_instruments(self) -> FetchResult: ...

    @abstractmethod
    def fetch_bars(self) -> FetchResult: ...

    @abstractmethod
    def fetch_indicators(self) -> FetchResult: ...

    @abstractmethod
    def fetch_calendar(self) -> FetchResult: ...

    @abstractmethod
    def health_check(self) -> FetchResult: ...


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def aggregate_status(capabilities: Sequence[Capability]) -> CapabilityStatus:
    """Legacy report presentation only; routing must use individual records."""

    if any(capability.status is CapabilityStatus.FAILED for capability in capabilities):
        return CapabilityStatus.FAILED
    if any(capability.status is CapabilityStatus.BLOCKED for capability in capabilities):
        return CapabilityStatus.BLOCKED
    if capabilities and all(item.status is CapabilityStatus.UNSUPPORTED for item in capabilities):
        return CapabilityStatus.UNSUPPORTED
    return CapabilityStatus.PASS


def _normalise_capability_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:64] or "legacy-capability"


def _has_reserved_migration_prefix(identifier: str) -> bool:
    return identifier.startswith((_MIGRATED_CAPABILITY_ID_PREFIX, _MIGRATION_ROOT_ERROR_ID_PREFIX))


def _legacy_registration(
    name: str,
    *,
    allow_other: bool,
    technical_id: str | None = None,
    legacy_name: str | None = None,
    legacy_occurrence: int | None = None,
) -> CapabilityRegistration:
    identifier = technical_id or _normalise_capability_id(name)
    operation = ProviderOperation.OTHER
    market = Market.GLOBAL
    asset_type = AssetType.GENERAL
    period: str | None = None
    lowered = name.lower()
    if "health" in lowered or "installation" in lowered or "license" in lowered or "callable_api" in lowered:
        operation = ProviderOperation.HEALTH_CHECK
    elif "calendar" in lowered:
        operation = ProviderOperation.CALENDAR
        market = Market.CN
    elif "fund" in lowered or "factor" in lowered or "indicator" in lowered or "a_share_" in lowered:
        operation = ProviderOperation.INDICATORS
        market = Market.CN
        asset_type = AssetType.STOCK
    elif "stock" in lowered or "future" in lowered or "etf" in lowered or "index" in lowered:
        operation = ProviderOperation.BARS
        market = Market.HK if "hk" in lowered else Market.CN
        asset_type = (
            AssetType.FUTURE if "future" in lowered else AssetType.ETF if "etf" in lowered else AssetType.INDEX if "index" in lowered else AssetType.STOCK
        )
        period = "1m" if "1m" in lowered else "30m" if "30m" in lowered else "1d"
    elif not allow_other:
        raise ValueError(f"unrecognized legacy adapter capability: {name}")
    request = ProviderRequest(operation, market, asset_type, period=period)
    return CapabilityRegistration(
        identifier,
        f"Migrated legacy capability: {name!r}",
        request,
        legacy_name=legacy_name,
        legacy_occurrence=legacy_occurrence,
    )


def _legacy_adapter_capability(
    name: str,
    status: CapabilityStatus,
    detail: str | None = None,
    row_count: int | None = None,
    earliest: str | None = None,
    latest: str | None = None,
    *,
    error: ProviderError | None = None,
) -> Capability:
    """Private bridge limited to the checked-in legacy Provider adapter names."""

    if not any(pattern.fullmatch(name) for pattern in _LEGACY_ADAPTER_CAPABILITY_PATTERNS):
        raise ValueError(f"unrecognized legacy adapter capability: {name}")

    return Capability(
        name,
        status,
        detail,
        row_count,
        earliest,
        latest,
        registration=_legacy_registration(name, allow_other=False),
        error=error,
    )


def _migrated_v1_capability(
    legacy_name: str,
    technical_id: str,
    legacy_occurrence: int,
    status: CapabilityStatus,
    detail: str | None = None,
    row_count: int | None = None,
    earliest: str | None = None,
    latest: str | None = None,
    *,
    error: ProviderError | None = None,
) -> Capability:
    """Private v1-only bridge retaining unknown old labels as explicit ``other``."""

    return Capability(
        technical_id,
        status,
        detail,
        row_count,
        earliest,
        latest,
        registration=_legacy_registration(
            legacy_name,
            allow_other=True,
            technical_id=technical_id,
            legacy_name=legacy_name,
            legacy_occurrence=legacy_occurrence,
        ),
        error=error,
    )


def _parse_datetime(value: str, field_name: str) -> datetime:
    try:
        if not isinstance(value, str) or not _ISO_DATETIME.fullmatch(value):
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except ValueError as error:
        raise ValueError(f"{field_name} must use ISO 8601 date-time") from error
