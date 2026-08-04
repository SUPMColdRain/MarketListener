"""Source-neutral provider interface used by all desktop collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping, Sequence


class CapabilityStatus(StrEnum):
    PASS = "PASS"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"


class ErrorCategory(StrEnum):
    AUTHENTICATION = "AUTH"
    QUOTA = "RATE_LIMIT"
    NETWORK = "NETWORK"
    FIELD_CHANGE = "PROVIDER"
    NO_COVERAGE = "NO_COVERAGE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProviderError(Exception):
    category: ErrorCategory
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class FetchResult:
    records: Sequence[Mapping[str, Any]]
    earliest: str | None = None
    latest: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class Capability:
    name: str
    status: CapabilityStatus
    detail: str | None = None
    row_count: int | None = None
    earliest: str | None = None
    latest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class ProviderRunResult:
    run_id: str
    provider: str
    status: CapabilityStatus
    started_at: str
    completed_at: str
    capabilities: Sequence[Capability]
    error: ProviderError | None = None
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "provider": self.provider,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "capabilities": [capability.to_dict() for capability in self.capabilities],
        }
        if self.error:
            payload["error"] = {
                "category": self.error.category.value,
                "message": self.error.message,
            }
        return payload


class Provider(ABC):
    """Every external source exposes the same six operations."""

    name: str

    @abstractmethod
    def probe_capabilities(self) -> Sequence[Capability]:
        """Probe only real reachable capabilities; never infer support from docs."""

    @abstractmethod
    def fetch_instruments(self) -> FetchResult:
        """Return source instruments, or raise ``ProviderError``."""

    @abstractmethod
    def fetch_bars(self) -> FetchResult:
        """Return source bars, or raise ``ProviderError``."""

    @abstractmethod
    def fetch_indicators(self) -> FetchResult:
        """Return source indicators, or raise ``ProviderError``."""

    @abstractmethod
    def fetch_calendar(self) -> FetchResult:
        """Return source trading calendar, or raise ``ProviderError``."""

    @abstractmethod
    def health_check(self) -> FetchResult:
        """Check source reachability and authentication without logging secrets."""


def utc_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def aggregate_status(capabilities: Sequence[Capability]) -> CapabilityStatus:
    if any(capability.status is CapabilityStatus.FAILED for capability in capabilities):
        return CapabilityStatus.FAILED
    if capabilities and all(
        capability.status is CapabilityStatus.UNSUPPORTED for capability in capabilities
    ):
        return CapabilityStatus.UNSUPPORTED
    return CapabilityStatus.PASS
