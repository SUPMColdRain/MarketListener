"""Provider abstraction for the multi-source F10 enrichment pipeline.

Every provider returns canonical field names plus field-level provenance so
the missing-field planner and the canonical merge step can reason about
what was actually observed and when.  Providers never invent facts: absent
values are simply missing keys.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


class ProviderError(RuntimeError):
    """A provider failed; another source may still succeed."""


class ProviderBlocked(ProviderError):
    """The provider is rate-limited/blocked or its circuit breaker is open."""


@dataclass(frozen=True)
class ProviderCapabilities:
    """Which F10 capabilities a provider can supply for a market."""

    profile: bool = False
    company: bool = False
    business: bool = False
    revenue: bool = False
    hk_supported: bool = False

    def supports(self, capability: str, *, market: str = "CN") -> bool:
        capability = capability.strip().lower()
        if capability not in {"profile", "company", "business", "revenue"}:
            return False
        if market.upper() == "HK" and not self.hk_supported:
            return False
        return bool(getattr(self, capability))


@dataclass(frozen=True)
class ProviderPage:
    """One page type understood by a provider.

    ``fields`` lists the canonical field names the page can contribute and is
    used by the missing-field planner to avoid requesting pages that cannot
    fill anything.
    """

    name: str
    fields: tuple[str, ...] = ()
    url_pattern: str | None = None
    market: str = "CN"


@dataclass(frozen=True)
class ProviderResult:
    """A single provider fetch, already parsed into canonical fields."""

    provider: str
    page: str
    market: str
    code: str
    fetched_at: str
    fields: dict[str, Any] = field(default_factory=dict)
    revenue_breakdown: tuple[Mapping[str, Any], ...] = ()
    provenance: dict[str, Mapping[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "page": self.page,
            "market": self.market,
            "code": self.code,
            "fetchedAt": self.fetched_at,
            "fields": dict(self.fields),
            "revenueBreakdown": [dict(row) for row in self.revenue_breakdown],
            "provenance": {key: dict(value) for key, value in self.provenance.items()},
        }


class F10Provider(ABC):
    """Interface implemented by Eastmoney / TDX / THS / Tencent sources."""

    name: str = "base"
    capabilities: ProviderCapabilities = ProviderCapabilities()

    @property
    def pages(self) -> tuple[ProviderPage, ...]:
        return ()

    @abstractmethod
    def fetch_profile(
        self,
        code: str,
        *,
        market: str = "CN",
        pages: Sequence[str] | None = None,
    ) -> ProviderResult:
        """Fetch company/profile fields for one security.

        ``pages`` optionally restricts the fetch to the named page types so
        the missing-field planner can avoid requesting pages that cannot fill
        any missing field.  ``None`` means fetch every page this provider
        supports for the market.

        The returned :class:`ProviderResult` carries only fields this provider
        actually observed; missing values are omitted.
        """

    def fetch_revenue(self, code: str, *, market: str = "CN") -> ProviderResult:
        """Fetch structured revenue breakdown for one security."""
        raise ProviderError(f"{self.name} does not provide revenue data for {market}")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<F10Provider {self.name} capabilities={self.capabilities!r}>"


def normalize_provider_result(result: ProviderResult | Mapping[str, Any]) -> ProviderResult:
    """Coerce a dict into a ProviderResult without trusting its shape."""
    if isinstance(result, ProviderResult):
        return result
    document = dict(result)
    return ProviderResult(
        provider=str(document.get("provider") or "unknown"),
        page=str(document.get("page") or "unknown"),
        market=str(document.get("market") or "CN").upper(),
        code=str(document.get("code") or ""),
        fetched_at=str(document.get("fetchedAt") or document.get("fetched_at") or ""),
        fields=dict(document.get("fields") or {}),
        revenue_breakdown=tuple(document.get("revenueBreakdown") or document.get("revenue_breakdown") or ()),
        provenance=dict(document.get("provenance") or {}),
    )


__all__ = (
    "F10Provider",
    "ProviderCapabilities",
    "ProviderError",
    "ProviderPage",
    "ProviderResult",
    "normalize_provider_result",
)
