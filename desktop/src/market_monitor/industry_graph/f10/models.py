"""Shared F10 domain models used by APIs and every company presentation.

The models deliberately carry money value, currency, timestamp and source as
one object.  A consumer must therefore never render a market-cap number
without also knowing what it means and when it was observed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _omit_empty(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if value not in (None, "", [], {})}


@dataclass(frozen=True)
class MoneySnapshot:
    """One monetary fact in base currency units, with provenance."""

    value: float
    currency: str
    as_of: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "currency": self.currency,
            "asOf": self.as_of,
            "source": self.source,
        }


@dataclass(frozen=True)
class RevenueSegment:
    """One structured revenue composition item; no inferred business rank."""

    name: str
    amount: MoneySnapshot | None = None
    ratio: float | None = None
    segment_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _omit_empty(
            {
                "name": self.name,
                "amount": self.amount.to_dict() if self.amount is not None else None,
                "ratio": self.ratio,
                "segmentType": self.segment_type,
            }
        )


@dataclass(frozen=True)
class CompanySummary:
    """The one compact company view embedded by list and chain responses."""

    instrument_key: str
    name: str
    code: str
    market: str
    company_highlight: str | None = None
    total_market_cap: MoneySnapshot | None = None
    float_market_cap: MoneySnapshot | None = None
    company_intro: str | None = None
    industry: str | None = None
    csrc_industry: str | None = None
    main_business: str | None = None
    top_revenue_segment: RevenueSegment | None = None
    products: tuple[str, ...] = ()
    source: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _omit_empty(
            {
                "instrumentKey": self.instrument_key,
                "name": self.name,
                "code": self.code,
                "market": self.market,
                "companyHighlight": self.company_highlight,
                "totalMarketCap": self.total_market_cap.to_dict() if self.total_market_cap else None,
                "floatMarketCap": self.float_market_cap.to_dict() if self.float_market_cap else None,
                "companyIntro": self.company_intro,
                "industry": self.industry,
                "csrcIndustry": self.csrc_industry,
                "mainBusiness": self.main_business,
                "topRevenueSegment": self.top_revenue_segment.to_dict() if self.top_revenue_segment else None,
                "products": list(self.products),
                "source": self.source,
                "updatedAt": self.updated_at,
            }
        )


@dataclass(frozen=True)
class CompanyDetail:
    """The complete company view.  It extends, rather than duplicates, Summary."""

    summary: CompanySummary
    business_scope: str | None = None
    revenue_segments: tuple[RevenueSegment, ...] = ()
    chain_locations: tuple[dict[str, str], ...] = ()
    sources: tuple[str, ...] = ()
    raw_status: str | None = None
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        document = self.summary.to_dict()
        document.update(
            _omit_empty(
                {
                    "businessScope": self.business_scope,
                    "revenueSegments": [segment.to_dict() for segment in self.revenue_segments],
                    "chainLocations": list(self.chain_locations),
                    "sources": list(self.sources),
                    "status": self.raw_status,
                }
            )
        )
        return document


__all__ = ("CompanyDetail", "CompanySummary", "MoneySnapshot", "RevenueSegment", "_clean_text")
