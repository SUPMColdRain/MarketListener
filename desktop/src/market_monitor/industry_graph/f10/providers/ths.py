"""THS (同花顺) F10 provider built on the basic.10jqka.com.cn pages.

The provider fetches two GBK-encoded HTML pages and one UTF-8 JSON API
directly (no akshare dependency):

- ``company.html``: company survey (name, org names, website, intro,
  SW industry, main business, products).
- ``operate.html``: business intro list (main business, business scope,
  products) plus the hidden stock code / market id used by the API.
- ``operate/index/v1/product_index_query``: structured revenue breakdown by
  product for every reported period.

All requests go through the shared rate limiter / circuit breaker.  Revenue
values are reported in base CNY currency units; ``account`` is the 0-1 share
of total income and ``gross_profit_rate`` is a 0-1 ratio, both converted to
the canonical percentages used by the repository.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any, Mapping, Sequence

from .base import (
    F10Provider,
    ProviderCapabilities,
    ProviderError,
    ProviderPage,
    ProviderResult,
)
from .governance import governed_get

_THS_BASIC = "https://basic.10jqka.com.cn"

_PROFILE_PAGE_NAMES = frozenset({"company_survey", "operate_business"})

_PAGE_URLS: dict[str, str] = {
    "company_survey": f"{_THS_BASIC}/{{code}}/company.html",
    "operate_business": f"{_THS_BASIC}/{{code}}/operate.html",
}

# Labels are matched after collapsing whitespace, so labels such as
# "董　　秘：" become "董 秘：" and the trailing colon is stripped.
_COMPANY_LABEL_FIELDS: dict[str, str] = {
    "公司名称": "org_name",
    "英文名称": "org_name_en",
    "所属申万行业": "industry_sw",
    "主营业务": "main_business",
    "产品名称": "products",
    "公司网址": "company_website",
    "公司简介": "company_intro",
}

_OPERATE_LABEL_FIELDS: dict[str, str] = {
    "主营业务": "main_business",
    "经营范围": "business_scope",
}


def ths_market_id(code: str) -> int:
    """Map a 6-digit CN code to the THS ``market`` API parameter.

    The mapping was verified against the hidden ``marketId`` input on the
    operate pages for SH A (17), SZ A (33), BJ (151), SH B (18) and SZ B
    (105) securities.
    """
    if code.startswith("900"):
        return 18
    if code.startswith("200"):
        return 105
    if code.startswith(("4", "8", "92")):
        return 151
    if code.startswith("6"):
        return 17
    if code.startswith(("0", "2", "3")):
        return 33
    raise ProviderError(f"ths cannot map code {code!r} to a CN market")


def parse_company_survey(html_text: str) -> dict[str, Any]:
    """Parse the GBK-decoded company.html body into canonical fields."""
    fields: dict[str, Any] = {}
    stock_name = _hidden_input_value(html_text, "stockName")
    if stock_name:
        fields["name"] = stock_name
    table = _company_survey_table(html_text)
    rows = _survey_rows(table)
    for label, target in _COMPANY_LABEL_FIELDS.items():
        value = rows.get(label)
        if not value:
            continue
        if target == "products":
            products = _split_products(value)
            if products:
                fields["products"] = products
        else:
            fields[target] = value
    return fields


def parse_operate_business(html_text: str) -> dict[str, Any]:
    """Parse the GBK-decoded operate.html business-intro list."""
    fields: dict[str, Any] = {}
    stock_name = _hidden_input_value(html_text, "stockName")
    if stock_name:
        fields["name"] = stock_name
    rows: dict[str, str] = {}
    for li in re.findall(r"<li[^>]*>(.*?)</li>", html_text, re.S | re.I):
        label_match = re.search(
            r'<span[^>]*class="[^"]*hltip[^"]*"[^>]*>(.*?)</span>',
            li,
            re.S | re.I,
        )
        if not label_match:
            continue
        label = _strip_label(label_match.group(1))
        if not label:
            continue
        value = _clean_text(li[label_match.end() :])
        if value:
            rows[label] = value
    for label, target in _OPERATE_LABEL_FIELDS.items():
        value = rows.get(label)
        if value:
            fields[target] = value
    for label in ("产品名称", "产品类型"):
        value = rows.get(label)
        if value:
            products = _split_products(value)
            if products:
                fields["products"] = products
            break
    return fields


def parse_revenue_payload(
    payload: Mapping[str, Any],
    *,
    fetched_at: str,
) -> list[dict[str, Any]]:
    """Convert the product-index query response into canonical revenue rows.

    Only the ``product`` analysis type is emitted; area and industry entries
    are ignored so the breakdown stays on one comparable dimension.  Rows
    whose names are aggregate totals (e.g. ``其他业务总计``) are skipped
    because they would otherwise win the largest-segment selection.
    """
    rows: list[dict[str, Any]] = []
    data = payload.get("data")
    if not isinstance(data, list):
        return rows
    for entry in data:
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("analysis_type") or "").strip() != "product":
            continue
        for period in entry.get("time_operate_index_item_list") or []:
            if not isinstance(period, Mapping):
                continue
            period_text = str(period.get("time") or "").strip()[:10] or None
            for item in period.get("product_index_item_list") or []:
                if not isinstance(item, Mapping):
                    continue
                name = _clean_text(item.get("product_name"))
                if not name or _is_aggregate_row(name):
                    continue
                metrics = _metric_map(item.get("index_analysis_list"))
                income = metrics.get("income") or {}
                revenue = _float_or_none(income.get("index_value"))
                ratio = _float_or_none(income.get("account"))
                cost = _metric_float(metrics.get("cost"))
                gross_profit = _metric_float(metrics.get("gross_profit"))
                gross_margin = _metric_float(metrics.get("gross_profit_rate"))
                currency = str(income.get("index_currency") or "CNY").strip() or "CNY"
                row: dict[str, Any] = {
                    "item": name,
                    "item_name": name,
                    "revenue": revenue,
                    "income": revenue,
                    "currency": currency,
                    "ratio": ratio,
                    "revenue_share_pct": (ratio * 100.0) if ratio is not None else None,
                    "cost": cost,
                    "gross_profit": gross_profit,
                    "gross_margin_pct": (gross_margin * 100.0) if gross_margin is not None else None,
                    "period": period_text,
                    "classification": "product",
                    "classification_label": "产品",
                    "source": "ths_f10",
                    "fetched_at": fetched_at,
                }
                rows.append(row)
    return rows


def _hidden_input_value(html_text: str, input_id: str) -> str:
    match = re.search(
        rf'<input[^>]+id=["\']{re.escape(input_id)}["\'][^>]*value=["\']([^"\']*)["\']',
        html_text,
        re.I,
    )
    if not match:
        return ""
    return _clean_text(match.group(1))


def _company_survey_table(html_text: str) -> str:
    """Return the document region containing survey label-value cells.

    Live THS pages split the company survey across two adjacent tables: the
    identity table holds ``公司名称`` while ``主营业务``/``产品名称``/``公司简介``
    live in a later ``m_tab_content2`` table.  Slicing from the first table
    before the ``公司名称`` label up to the 高管介绍 marker keeps both survey
    tables while excluding later sections (such as 发行相关) that reuse
    ``hltip`` labels.  If the anchor or marker is missing, fall back to the
    whole document so the parse remains robust for unusual layouts.
    """
    anchor = html_text.find("公司名称：")
    table_start = html_text.rfind("<table", 0, anchor) if anchor >= 0 else -1
    if table_start < 0:
        return html_text
    end = len(html_text)
    for marker in ('id="manager"', "高管介绍"):
        marker_index = html_text.find(marker, table_start)
        if 0 <= marker_index < end:
            end = marker_index
    return html_text[table_start:end]


def _survey_rows(table_html: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for td in re.findall(r"<td[^>]*>(.*?)</td>", table_html, re.S | re.I):
        label_match = re.search(
            r'<strong[^>]*class="[^"]*hltip[^"]*"[^>]*>(.*?)</strong>',
            td,
            re.S | re.I,
        )
        if not label_match:
            continue
        label = _strip_label(label_match.group(1))
        if not label:
            continue
        value = _clean_text(td[label_match.end() :])
        if value:
            rows[label] = value
    return rows


def _strip_label(text: str) -> str:
    return _clean_text(text).rstrip(":：").strip()


def _clean_text(value: object) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _split_products(value: str) -> tuple[str, ...]:
    parts = re.split(r"[、，,;；\n]+", value)
    return tuple(part.strip() for part in parts if part.strip())


def _metric_map(metrics: object) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    if not isinstance(metrics, list):
        return result
    for metric in metrics:
        if not isinstance(metric, Mapping):
            continue
        index_id = str(metric.get("index_id") or "").strip()
        if index_id:
            result[index_id] = metric
    return result


def _metric_float(metric: Mapping[str, Any] | None) -> float | None:
    if not metric:
        return None
    return _float_or_none(metric.get("index_value"))


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _is_aggregate_row(name: str) -> bool:
    normalized = name.strip().replace(" ", "")
    return normalized.endswith(("总计", "合计"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _revenue_url(code: str, market_id: int) -> str:
    return (
        f"{_THS_BASIC}/basicapi/operate/index/v1/product_index_query/"
        f"?code={code}&market={market_id}&type=stock&account=1&timeField=date"
        "&analysisTypes=product,area,industry&sortIndex=income&currency=CNY"
        "&level=1&expands=product_introduction&locale=zh_CN"
    )


def _normalize_code(code: str) -> str:
    digits = re.sub(r"\D", "", str(code or ""))
    if len(digits) != 6:
        raise ProviderError(f"ths expects a 6-digit CN code, got {code!r}")
    return digits


class ThsF10Provider(F10Provider):
    name = "ths"
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
                    "name",
                    "org_name",
                    "org_name_en",
                    "company_website",
                    "company_intro",
                    "main_business",
                    "industry_sw",
                    "products",
                ),
                url_pattern=_PAGE_URLS["company_survey"],
                market="CN",
            ),
            ProviderPage(
                name="operate_business",
                fields=("business_scope", "main_business", "products"),
                url_pattern=_PAGE_URLS["operate_business"],
                market="CN",
            ),
            ProviderPage(
                name="operate_revenue",
                fields=("revenue_breakdown",),
                url_pattern=(
                    f"{_THS_BASIC}/basicapi/operate/index/v1/product_index_query/"
                    "?code={code}&market={market}"
                ),
                market="CN",
            ),
        )

    def fetch_profile(
        self,
        code: str,
        *,
        market: str = "CN",
        pages: Sequence[str] | None = None,
    ) -> ProviderResult:
        if market.upper() != "CN":
            raise ProviderError(f"ths profile is only implemented for CN, not {market}")
        code = _normalize_code(code)
        requested = set(pages) if pages is not None else set(_PROFILE_PAGE_NAMES)
        if not requested:
            raise ProviderError("ths profile needs at least one page")
        unknown = requested - _PROFILE_PAGE_NAMES
        if unknown:
            raise ProviderError(
                f"ths does not support profile page(s): {sorted(unknown)}"
            )

        fields: dict[str, Any] = {}
        provenance: dict[str, dict[str, Any]] = {}
        page_names = sorted(requested)
        for page_name in page_names:
            url = _PAGE_URLS[page_name].format(code=code)
            try:
                html_text = governed_get(url, provider=self.name, encoding="gbk")
            except ProviderError as error:
                raise ProviderError(
                    f"ths {page_name} failed for {code}: {error}"
                ) from error
            parsed = (
                parse_company_survey(html_text)
                if page_name == "company_survey"
                else parse_operate_business(html_text)
            )
            fetched_at = _now_iso()
            for key, value in parsed.items():
                if value and key not in fields:
                    fields[key] = value
                    provenance[key] = {
                        "source": self.name,
                        "sourcePage": page_name,
                        "fetchedAt": fetched_at,
                    }
        fields.setdefault("code", code)
        provenance.setdefault(
            "code",
            {
                "source": self.name,
                "sourcePage": page_names[0] if len(page_names) == 1 else "profile",
                "fetchedAt": _now_iso(),
            },
        )
        return ProviderResult(
            provider=self.name,
            page=page_names[0] if len(page_names) == 1 else "profile",
            market="CN",
            code=code,
            fetched_at=_now_iso(),
            fields=fields,
            provenance=provenance,
        )

    def fetch_revenue(self, code: str, *, market: str = "CN") -> ProviderResult:
        if market.upper() != "CN":
            raise ProviderError(
                f"ths revenue breakdown is only implemented for CN, not {market}"
            )
        code = _normalize_code(code)
        market_id = ths_market_id(code)
        url = _revenue_url(code, market_id)
        try:
            body = governed_get(url, provider=self.name, encoding="utf-8")
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise ProviderError(
                f"ths revenue returned invalid JSON for {code}: {error}"
            ) from error
        except ProviderError:
            raise
        status = payload.get("status_code")
        if status is not None and str(status) not in {"0", ""}:
            message = str(payload.get("status_msg") or "").strip()
            detail = f" {message}" if message else ""
            raise ProviderError(
                f"ths revenue API error for {code}: status={status}{detail}"
            )
        fetched_at = _now_iso()
        rows = parse_revenue_payload(payload, fetched_at=fetched_at)
        return ProviderResult(
            provider=self.name,
            page="operate_revenue",
            market="CN",
            code=code,
            fetched_at=fetched_at,
            fields={},
            revenue_breakdown=tuple(rows),
            provenance={
                "revenue_breakdown": {
                    "source": self.name,
                    "sourcePage": "operate_revenue",
                    "fetchedAt": fetched_at,
                }
            },
        )


__all__ = (
    "ThsF10Provider",
    "parse_company_survey",
    "parse_operate_business",
    "parse_revenue_payload",
    "ths_market_id",
)
