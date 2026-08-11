"""Missing-field enrichment planner (pure logic, no network).

Given a company's current record, the planner decides which provider pages
could fill which missing canonical fields and returns the smallest practical
set of requests.  It never invents field coverage: only fields listed on a
provider's :class:`ProviderPage` are considered candidates.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .providers import F10Provider

# Canonical profile fields that the enrichment pipeline can fill.
CANONICAL_PROFILE_FIELDS = (
    "name",
    "org_name",
    "company_position",
    "company_highlight",
    "company_intro",
    "company_website",
    "industry_csrc",
    "industry_tdx",
    "industry_sw",
    "industry_em",
    "industry_hs",
    "main_business",
    "business_scope",
    "products",
    "total_shares",
    "float_shares",
    "total_market_cap",
    "float_market_cap",
)

REVENUE_FIELD = "revenue_breakdown"

#: Lower values win when two provider pages cover the same number of missing
#: canonical fields.  THS/TDX expose fields (company_intro, products,
#: company_position, ...) that Eastmoney cannot fill, so they are preferred
#: on ties; Eastmoney remains the fallback for CN revenue and for HK F10.
PROVIDER_PRIORITY: Mapping[str, int] = {
    "ths": 0,
    "tdx": 1,
    "eastmoney": 2,
    "tencent": 3,
}


def non_empty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def record_value(record: Mapping[str, Any], field: str) -> object:
    """Extract the effective value of a canonical field from a raw record."""
    if field == "company_intro":
        return record.get("company_intro") or record.get("org_profile") or record.get("profile")
    if field == "company_website":
        return record.get("company_website") or record.get("org_web")
    if field == "industry_csrc":
        return record.get("industry_csrc") or record.get("csrc_industry")
    if field == "industry_em":
        return record.get("industry_em") or record.get("industry")
    if field == "name":
        return record.get("name") or record.get("org_name")
    if field == "org_name":
        return record.get("org_name")
    if field in {"total_market_cap", "float_market_cap"}:
        direct = record.get(field)
        if non_empty(direct):
            return direct
        quote = record.get("quote") or {}
        source = "total_market_cap_yi" if field == "total_market_cap" else "float_market_cap_yi"
        return quote.get(source)
    return record.get(field)


def compute_missing_fields(record: Mapping[str, Any]) -> set[str]:
    """Return canonical profile fields that are missing/empty in ``record``."""
    return {field for field in CANONICAL_PROFILE_FIELDS if not non_empty(record_value(record, field))}


def plan_requests(
    missing_fields: Iterable[str],
    providers: Mapping[str, F10Provider],
    *,
    market: str = "CN",
) -> tuple[list[tuple[str, str]], set[str]]:
    """Return the minimal (provider, page) request list for missing fields.

    The greedy loop repeatedly picks the provider page that covers the most
    still-missing fields, breaking ties toward the preferred source in
    :data:`PROVIDER_PRIORITY`.  Fields that no available page covers remain
    in the returned ``remaining`` set (never guessed).
    """

    market_key = market.upper()
    missing = set(missing_fields)
    selected: list[tuple[str, str]] = []
    while missing:
        best: tuple[str, str, set[str]] | None = None
        best_rank: tuple[int, int] = (-1, -1)
        for provider in providers.values():
            if not provider.capabilities.supports("profile", market=market_key):
                continue
            for page in provider.pages:
                if page.market != "*" and page.market.upper() != market_key:
                    continue
                covered = missing.intersection(page.fields)
                if not covered:
                    continue
                priority = PROVIDER_PRIORITY.get(
                    provider.name, len(PROVIDER_PRIORITY)
                )
                rank = (len(covered), -priority)
                if best is None or rank > best_rank:
                    best = (provider.name, page.name, covered)
                    best_rank = rank
        if best is None:
            break
        selected.append((best[0], best[1]))
        missing.difference_update(best[2])
    return selected, missing


def plan_revenue_requests(
    providers: Mapping[str, F10Provider],
    *,
    market: str = "CN",
) -> list[tuple[str, str]]:
    """Return providers that can supply revenue rows for a market."""
    market_key = market.upper()
    requests: list[tuple[str, str]] = []
    for provider in providers.values():
        if not provider.capabilities.supports("revenue", market=market_key):
            continue
        for page in provider.pages:
            if page.market.upper() == market_key and REVENUE_FIELD in page.fields:
                requests.append((provider.name, page.name))
    return sorted(
        requests,
        key=lambda item: PROVIDER_PRIORITY.get(item[0], len(PROVIDER_PRIORITY)),
    )


def _merge_product_lists(*values: object) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, (list, tuple, set)):
            continue
        for item in value:
            text = str(item or "").strip()
            if text and text.casefold() not in seen:
                seen.add(text.casefold())
                merged.append(text)
    return merged


def merge_profile_results(
    base_record: Mapping[str, Any],
    results: Sequence[Any],
) -> dict[str, Any]:
    """Merge provider results into one enriched record (non-destructive).

    Existing non-empty values in ``base_record`` win; provider results only
    fill missing fields.  ``products`` is a union, deduplicated case-
    insensitively.  Every filled field gets provenance.
    """

    merged = dict(base_record)
    provenance = dict(merged.get("provenance") or {})
    for result in results:
        fields = getattr(result, "fields", None) or (result.get("fields") if isinstance(result, Mapping) else {})
        for field, value in fields.items():
            if not non_empty(value):
                continue
            if field == "products":
                current = merged.get("products") or []
                combined = _merge_product_lists(current, value)
                if combined:
                    merged["products"] = combined
            elif field in {"total_market_cap", "float_market_cap"}:
                _merge_money_snapshot(merged, field, value)
            else:
                current = merged.get(field)
                if not non_empty(current):
                    merged[field] = value
            if field not in provenance:
                provenance[field] = _provenance_entry(result, field)
    merged["provenance"] = provenance
    return merged


def _merge_money_snapshot(merged: dict[str, Any], field: str, value: object) -> None:
    current = merged.get(field)
    if non_empty(current):
        return
    if isinstance(value, Mapping):
        merged[field] = dict(value)
    else:
        merged[field] = value


def _provenance_entry(result: Any, field: str) -> dict[str, Any]:
    provider = getattr(result, "provider", "") or ""
    page = getattr(result, "page", "") or ""
    fetched_at = getattr(result, "fetched_at", "") or ""
    if isinstance(result, Mapping):
        provider = result.get("provider") or provider
        page = result.get("page") or page
        fetched_at = result.get("fetchedAt") or result.get("fetched_at") or fetched_at
    own = {}
    if isinstance(result, Mapping):
        own = result.get("provenance") or {}
        if isinstance(own, Mapping):
            own = own.get(field) or {}
    return {
        "source": provider or "unknown",
        "sourcePage": page or "unknown",
        "fetchedAt": fetched_at,
        **({} if not isinstance(own, Mapping) else {k: v for k, v in own.items() if k not in {"source", "sourcePage", "fetchedAt"}}),
    }


__all__ = (
    "CANONICAL_PROFILE_FIELDS",
    "PROVIDER_PRIORITY",
    "REVENUE_FIELD",
    "compute_missing_fields",
    "merge_profile_results",
    "non_empty",
    "plan_requests",
    "plan_revenue_requests",
    "record_value",
)
