"""TDX (通达信) F10 provider.

TDX serves F10 pages as HTML that embeds datasets in JavaScript string
literals assigned to ``window[...]`` keys.  Each literal is a JSON document
whose ``ResultSets`` is a list of ``{"ColName": [...], "Content": [[...]]}``
tables.  This provider parses those embedded datasets and maps them to the
canonical fields shared by the F10 enrichment pipeline.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .base import (
    F10Provider,
    ProviderBlocked,
    ProviderCapabilities,
    ProviderError,
    ProviderPage,
    ProviderResult,
)
from .governance import governed_get

#: Hosts that returned 200 for the same F10 page payloads during live
#: probing.  ``page3.tdx.com.cn`` returns 404 and is deliberately absent.
BASE_URLS = ("http://static.tdx.com.cn:7615", "http://page1.tdx.com.cn:7610")

_PROFILE_PAGES = ("company_survey", "company_summary")

_PAGE_NAMES = {
    "company_survey": "gg_gsgk",
    "company_summary": "gg_zxts",
    "business_analysis": "gg_jyfx",
}

_DATASET_PATTERN = re.compile(r"""window\[['"]([^'"]+)['"]\]\s*=\s*("(?:[^"\\]|\\.)*")""")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def url_for_page(page: str, code: str, *, base_url: str | None = None) -> str:
    """Build the TDX F10 URL for one page and security code."""
    try:
        page_name = _PAGE_NAMES[page]
    except KeyError as error:
        raise ProviderError(f"unknown tdx page: {page}") from error
    base = (base_url or BASE_URLS[0]).rstrip("/")
    return (
        f"{base}/site/tdxf10/{page_name}/{code}.html"
        f"?version=000001&vertype=0&style=black&gp={code}&ispc=1"
    )


def parse_tdx_datasets(html: str) -> dict[str, dict[str, Any]]:
    """Extract the embedded JSON documents from a TDX F10 HTML page."""
    datasets: dict[str, dict[str, Any]] = {}
    for match in _DATASET_PATTERN.finditer(html or ""):
        key, raw = match.group(1), match.group(2)
        try:
            document = json.loads(json.loads(raw))
        except (TypeError, ValueError):
            continue
        if isinstance(document, dict):
            datasets[key] = document
    return datasets


def parse_tdx_company_survey(datasets: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Map the 公司概况 (``gg_gsgk``) datasets to canonical profile fields."""
    document = _dataset_by_fragment(datasets, "tdxf10_gg_gsgk_0_")
    rows = _table(document, 0)
    if not rows:
        raise ProviderError("tdx company_survey has no company row")
    fields: dict[str, Any] = {}
    mapping = {
        "org_name": "T003",
        "org_name_en": "T006",
        "company_website": "url",
        "industry_tdx": "yjhy",
        "industry_csrc": "T040",
        "main_business": "T017",
        "business_scope": "T018",
    }
    for target, column in mapping.items():
        value = _text(_first(rows, column))
        if value:
            fields[target] = value
    return fields


def parse_tdx_company_summary(
    datasets: Mapping[str, Mapping[str, Any]],
    *,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Map the 公司摘要 (``gg_zxts``) datasets to canonical profile fields."""
    gsgy_key = _dataset_key(datasets, "tdxf10_gg_zxts_", "_gsgy_")
    if gsgy_key is None:
        raise ProviderError("tdx company_summary is missing the gsgy dataset")
    summary_doc = datasets[gsgy_key]
    zxts_key = _dataset_key(datasets, "tdxf10_gg_zxts_", "_zxts_")
    quote_doc = datasets[zxts_key] if zxts_key else None

    fields: dict[str, Any] = {}
    name = _text(_first(_table(summary_doc, 8), "name"))
    if name:
        fields["name"] = name
    position = _text(_first(_table(summary_doc, 0), "gsdw"))
    if position:
        fields["company_position"] = position
    hy1 = _text(_first(_table(summary_doc, 1), "hy1"))
    hy2 = _text(_first(_table(summary_doc, 1), "hy2"))
    if hy1 and hy2:
        fields["industry_tdx"] = f"{hy1}-{hy2}"
    elif hy2:
        fields["industry_tdx"] = hy2
    elif hy1:
        fields["industry_tdx"] = hy1
    csrc = _text(_first(_table(summary_doc, 8), "zzhy"))
    if csrc:
        fields["industry_csrc"] = csrc
    main_business = _text(_first(_table(summary_doc, 1), "T017"))
    if main_business:
        fields["main_business"] = main_business
    total_shares = _number(_first(_table(summary_doc, 6), "zgb"))
    if total_shares:
        fields["total_shares"] = total_shares
    float_shares = _number(_first(_table(summary_doc, 6), "ltag"))
    if float_shares:
        fields["float_shares"] = float_shares
    market_cap = _number(_first(_table(summary_doc, 6), "zsz"))
    if market_cap:
        as_of = None
        if quote_doc is not None:
            as_of = _text(_first(_table(quote_doc, 5), "jzr"))
        if not as_of:
            as_of = _text(_first(_table(summary_doc, 8), "gxrq"))
        if not as_of:
            as_of = fetched_at
        if as_of:
            fields["total_market_cap"] = {
                "value": market_cap,
                "currency": "CNY",
                "asOf": as_of,
                "source": "tdx",
                "derived": False,
            }
    return fields


def parse_tdx_revenue(
    datasets: Mapping[str, Mapping[str, Any]],
    *,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Map the 经营分析 (``gg_jyfx``) datasets to canonical revenue rows.

    Returns ``{"fields": ..., "revenue_breakdown": [...]}``; ``fields``
    carries the page's main-business text and ``revenue_breakdown`` carries
    one row per report-period product/region item.
    """

    periods_doc = _dataset_by_fragment(datasets, "tdxf10_gg_comreq_zygcfx_")
    periods = [
        text
        for text in (_text(row.get("T002")) for row in _table(periods_doc, 0))
        if text
    ]
    breakdown: list[dict[str, Any]] = []
    for period in periods:
        key = next(
            (candidate for candidate in datasets if candidate.endswith(f"_zygc_{period}")),
            None,
        )
        if key is None:
            continue
        for row in _table(datasets[key], 0):
            item = _text(row.get("N002"))
            if not item:
                continue
            raw_type = str(row.get("N001") or "").strip()
            entry: dict[str, Any] = {
                "period": _normalize_period(period),
                "type": raw_type or None,
                "classification_label": _text(row.get("N000")),
                "item": item,
                "item_name": item,
                "currency": "CNY",
                "source": "tdx",
            }
            classification = _classification(raw_type)
            if classification:
                entry["classification"] = classification
            _set_number(entry, "revenue", row.get("N003"))
            _set_number(entry, "income", row.get("N003"))
            share = _number(row.get("N004"))
            if share is not None:
                entry["ratio"] = share / 100.0
                entry["revenue_share_pct"] = share
            _set_number(entry, "cost", row.get("N005"))
            _set_number(entry, "cost_share_pct", row.get("N006"))
            _set_number(entry, "gross_profit", row.get("N007"))
            _set_number(entry, "gross_profit_share_pct", row.get("N008"))
            _set_number(entry, "gross_margin_pct", row.get("N009"))
            if fetched_at:
                entry["fetched_at"] = fetched_at
            breakdown.append(entry)
    if not breakdown:
        raise ProviderError("tdx business_analysis has no revenue breakdown rows")

    fields: dict[str, Any] = {}
    zyyw_key = _dataset_key(datasets, "tdxf10_gg_jyfx_", "_zyyw_")
    if zyyw_key is not None:
        main_business = _text(_first(_table(datasets[zyyw_key], 0), "T017"))
        if main_business:
            fields["main_business"] = main_business
    return {"fields": fields, "revenue_breakdown": breakdown}


class TdxF10Provider(F10Provider):
    """F10 provider backed by TDX's public F10 pages."""

    name = "tdx"
    capabilities = ProviderCapabilities(
        profile=True,
        company=True,
        business=True,
        revenue=True,
        hk_supported=False,
    )

    @property
    def pages(self) -> tuple[ProviderPage, ...]:
        return (
            ProviderPage(
                name="company_survey",
                fields=(
                    "org_name",
                    "org_name_en",
                    "company_website",
                    "industry_tdx",
                    "industry_csrc",
                    "main_business",
                    "business_scope",
                ),
                url_pattern=f"{BASE_URLS[0]}/site/tdxf10/gg_gsgk/{{code}}.html",
            ),
            ProviderPage(
                name="company_summary",
                fields=(
                    "name",
                    "company_position",
                    "industry_tdx",
                    "industry_csrc",
                    "main_business",
                    "total_shares",
                    "float_shares",
                    "total_market_cap",
                ),
                url_pattern=f"{BASE_URLS[0]}/site/tdxf10/gg_zxts/{{code}}.html",
            ),
            ProviderPage(
                name="business_analysis",
                fields=("revenue_breakdown",),
                url_pattern=f"{BASE_URLS[0]}/site/tdxf10/gg_jyfx/{{code}}.html",
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
        if market_key != "CN":
            raise ProviderError(f"tdx F10 is only implemented for CN, got {market_key}")
        code = str(code or "").strip()
        if not code:
            raise ProviderError("tdx requires a non-empty code")
        requested = tuple(pages) if pages is not None else _PROFILE_PAGES
        unknown = [page for page in requested if page not in _PROFILE_PAGES]
        if unknown:
            raise ProviderError(
                f"tdx profile only has pages {', '.join(_PROFILE_PAGES)}; got {unknown[0]!r}"
            )
        ordered = list(dict.fromkeys(requested))
        if not ordered:
            raise ProviderError("tdx profile requires at least one page")

        combined: dict[str, Any] = {}
        provenance: dict[str, dict[str, Any]] = {}
        latest_fetched_at = ""
        for page in ordered:
            html = _fetch_page(self.name, page, code)
            datasets = parse_tdx_datasets(html)
            if not datasets:
                raise ProviderError(f"tdx {page} returned no embedded datasets")
            fetched_at = _now_iso()
            latest_fetched_at = fetched_at
            if page == "company_survey":
                fields = parse_tdx_company_survey(datasets)
            else:
                fields = parse_tdx_company_summary(datasets, fetched_at=fetched_at)
            for field, value in fields.items():
                if field not in combined:
                    combined[field] = value
                    provenance[field] = {
                        "source": self.name,
                        "sourcePage": page,
                        "fetchedAt": fetched_at,
                    }
        return ProviderResult(
            provider=self.name,
            page=",".join(ordered),
            market=market_key,
            code=code,
            fetched_at=latest_fetched_at,
            fields=combined,
            provenance=provenance,
        )

    def fetch_revenue(self, code: str, *, market: str = "CN") -> ProviderResult:
        market_key = market.upper()
        if market_key != "CN":
            raise ProviderError(f"tdx F10 is only implemented for CN, got {market_key}")
        code = str(code or "").strip()
        if not code:
            raise ProviderError("tdx requires a non-empty code")
        html = _fetch_page(self.name, "business_analysis", code)
        datasets = parse_tdx_datasets(html)
        if not datasets:
            raise ProviderError("tdx business_analysis returned no embedded datasets")
        fetched_at = _now_iso()
        parsed = parse_tdx_revenue(datasets, fetched_at=fetched_at)
        provenance: dict[str, dict[str, Any]] = {
            "revenue_breakdown": {
                "source": self.name,
                "sourcePage": "business_analysis",
                "fetchedAt": fetched_at,
            }
        }
        if "main_business" in parsed["fields"]:
            provenance["main_business"] = {
                "source": self.name,
                "sourcePage": "business_analysis",
                "fetchedAt": fetched_at,
            }
        return ProviderResult(
            provider=self.name,
            page="business_analysis",
            market="CN",
            code=code,
            fetched_at=fetched_at,
            fields=parsed["fields"],
            revenue_breakdown=tuple(parsed["revenue_breakdown"]),
            provenance=provenance,
        )


def _fetch_page(provider_name: str, page: str, code: str) -> str:
    """Fetch one page, falling back to the next host when one is down."""
    last_error: Exception | None = None
    for base_url in BASE_URLS:
        url = url_for_page(page, code, base_url=base_url)
        try:
            return governed_get(url, provider=provider_name)
        except ProviderBlocked:
            raise
        except ProviderError as error:
            last_error = error
    raise ProviderError(f"tdx {page} failed on all F10 hosts: {last_error}") from last_error


def _dataset_key(
    datasets: Mapping[str, Mapping[str, Any]],
    prefix: str,
    suffix: str,
) -> str | None:
    return next(
        (key for key in datasets if prefix in key and key.endswith(suffix)),
        None,
    )


def _dataset_by_fragment(
    datasets: Mapping[str, Mapping[str, Any]],
    fragment: str,
) -> dict[str, Any]:
    for key, document in datasets.items():
        if fragment in key:
            return document
    raise ProviderError(f"tdx page is missing dataset containing {fragment!r}")


def _table(document: Mapping[str, Any], index: int = 0) -> list[dict[str, Any]]:
    result_sets = document.get("ResultSets") or []
    if isinstance(result_sets, Mapping):
        result_sets = [result_sets]
    if not isinstance(result_sets, list) or index >= len(result_sets):
        return []
    result_set = result_sets[index]
    if not isinstance(result_set, Mapping):
        return []
    columns = result_set.get("ColName") or []
    if not isinstance(columns, list):
        return []
    rows: list[dict[str, Any]] = []
    for content in result_set.get("Content") or []:
        if isinstance(content, list):
            rows.append({str(column): value for column, value in zip(columns, content)})
    return rows


def _first(rows: Sequence[Mapping[str, Any]], column: str) -> object:
    for row in rows:
        value = row.get(column)
        if value not in (None, ""):
            return value
    return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def _set_number(target: dict[str, Any], field: str, value: object) -> None:
    number = _number(value)
    if number is not None:
        target[field] = number


def _normalize_period(value: str) -> str:
    digits = value.strip()
    if len(digits) == 8 and digits.isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return digits


def _classification(raw_type: str) -> str | None:
    if raw_type == "1":
        return "industry"
    if raw_type == "2":
        return "product"
    if raw_type == "3":
        return "region"
    return None


__all__ = (
    "BASE_URLS",
    "TdxF10Provider",
    "parse_tdx_company_summary",
    "parse_tdx_company_survey",
    "parse_tdx_datasets",
    "parse_tdx_revenue",
    "url_for_page",
)
