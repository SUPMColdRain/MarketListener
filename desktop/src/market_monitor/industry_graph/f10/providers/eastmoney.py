"""Eastmoney provider wrapper around the existing F10 fetchers.

The actual network + parsing logic stays in :mod:`market_monitor.f10`; this
provider only adapts its output to the shared ProviderResult contract so the
missing-field planner can treat Eastmoney like any other source.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .base import (
    F10Provider,
    ProviderCapabilities,
    ProviderError,
    ProviderPage,
    ProviderResult,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class EastmoneyF10Provider(F10Provider):
    name = "eastmoney"
    capabilities = ProviderCapabilities(
        profile=True,
        company=True,
        business=True,
        revenue=True,
        hk_supported=True,
    )

    @property
    def pages(self) -> tuple[ProviderPage, ...]:
        return (
            ProviderPage(
                name="company_survey",
                fields=(
                    "name",
                    "org_name",
                    "company_website",
                    "company_intro",
                    "business_scope",
                    "industry_em",
                    "industry_csrc",
                ),
                url_pattern="https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax",
                market="*",
            ),
            ProviderPage(
                name="business_analysis",
                fields=("revenue_breakdown",),
                url_pattern="https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax",
            ),
        )

    def fetch_profile(
        self,
        code: str,
        *,
        market: str = "CN",
        pages: Sequence[str] | None = None,
    ) -> ProviderResult:
        market_key = market.upper()
        requested = {page for page in (pages or ("company_survey",))}
        if "company_survey" not in requested:
            raise ProviderError("eastmoney profile only has page company_survey")
        # Lazy import keeps the provider package independent of f10.py's
        # module-load order.
        from market_monitor.f10 import fetch_company_survey

        try:
            record = fetch_company_survey(code, market=market_key)
        except Exception as error:
            raise ProviderError(f"eastmoney profile failed for {code}: {error}") from error
        fields = _profile_fields(record)
        fetched_at = _now_iso()
        provenance = {
            key: {
                "source": self.name,
                "sourcePage": "company_survey",
                "fetchedAt": fetched_at,
            }
            for key in fields
        }
        return ProviderResult(
            provider=self.name,
            page="company_survey",
            market=market_key,
            code=str(record.get("code") or code),
            fetched_at=fetched_at,
            fields=fields,
            provenance=provenance,
        )

    def fetch_revenue(self, code: str, *, market: str = "CN") -> ProviderResult:
        if market.upper() != "CN":
            raise ProviderError("eastmoney revenue breakdown is only implemented for CN")
        from market_monitor.f10 import fetch_business_analysis

        try:
            payload = fetch_business_analysis(code)
        except Exception as error:
            raise ProviderError(f"eastmoney revenue failed for {code}: {error}") from error
        rows = payload.get("revenue_breakdown") or []
        fetched_at = _now_iso()
        return ProviderResult(
            provider=self.name,
            page="business_analysis",
            market="CN",
            code=code,
            fetched_at=fetched_at,
            fields={},
            revenue_breakdown=tuple(rows),
            provenance={
                "revenue_breakdown": {
                    "source": self.name,
                    "sourcePage": "business_analysis",
                    "fetchedAt": fetched_at,
                }
            },
        )


def _profile_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    mapping = {
        "code": "code",
        "name": "name",
        "org_name": "org_name",
        "org_name_en": "org_name_en",
        "company_website": "org_web",
        "company_intro": "org_profile",
        "business_scope": "business_scope",
        "industry_em": "industry_em",
        "industry_csrc": "industry_csrc",
    }
    for target, source in mapping.items():
        value = record.get(source)
        if value not in (None, ""):
            fields[target] = value
    return fields


__all__ = ("EastmoneyF10Provider",)
