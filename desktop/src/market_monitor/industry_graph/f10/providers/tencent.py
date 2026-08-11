"""Tencent quote provider.

Tencent is a time-sensitive quote source, not a full F10 page source.  It
contributes name/price/market-cap snapshots whose ``asOf`` is the exchange
quote time, never the fetch time.
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

_YI = 100_000_000.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def tencent_quote_fields(quote: Mapping[str, Any], *, market: str) -> dict[str, Any]:
    """Convert a TencentQuote-like mapping to canonical snapshot fields."""
    market_key = market.upper()
    currency = "HKD" if market_key == "HK" else "CNY"
    as_of = str(quote.get("quote_time") or quote.get("fetched_at") or "").strip()
    fields: dict[str, Any] = {}
    code = str(quote.get("code") or "").strip()
    name = str(quote.get("name") or "").strip()
    if code:
        fields["code"] = code
    if name:
        fields["name"] = name
    if as_of:
        for target, source in (
            ("total_market_cap", "total_market_cap_yi"),
            ("float_market_cap", "float_market_cap_yi"),
        ):
            value = _positive_float(quote.get(source))
            if value is not None:
                fields[target] = {
                    "value": round(value * _YI, 2),
                    "currency": currency,
                    "asOf": as_of,
                    "source": "tencent_quote",
                    "derived": False,
                }
        price = _positive_float(quote.get("price"))
        if price is not None:
            fields["price"] = price
        prev_close = _positive_float(quote.get("prev_close"))
        if prev_close is not None:
            fields["prev_close"] = prev_close
    return fields


def _positive_float(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


class TencentQuoteProvider(F10Provider):
    name = "tencent"
    capabilities = ProviderCapabilities(profile=True, company=False, business=False, revenue=False, hk_supported=True)

    @property
    def pages(self) -> tuple[ProviderPage, ...]:
        return (
            ProviderPage(
                name="bulk_quote",
                fields=("name", "total_market_cap", "float_market_cap", "price"),
                url_pattern="https://qt.gtimg.cn/q=",
                market="*",
            ),
        )

    def fetch_quotes(self, codes: Sequence[str], *, market: str = "CN") -> dict[str, dict[str, Any]]:
        """Batch fetch quotes and return code -> canonical fields."""
        from market_monitor.f10 import fetch_tencent_quotes

        quotes = fetch_tencent_quotes(codes)
        result: dict[str, dict[str, Any]] = {}
        for code, quote in quotes.items():
            result[code] = tencent_quote_fields(vars(quote) if hasattr(quote, "__dict__") else quote, market=market)
        return result

    def fetch_profile(
        self,
        code: str,
        *,
        market: str = "CN",
        pages: Sequence[str] | None = None,
    ) -> ProviderResult:
        requested = {page for page in (pages or ("bulk_quote",))}
        if "bulk_quote" not in requested:
            raise ProviderError("tencent profile only has page bulk_quote")
        rows = self.fetch_quotes([code], market=market)
        fields = rows.get(code)
        fetched_at = _now_iso()
        if not fields:
            raise ProviderError(f"tencent returned no quote for {code}")
        provenance = {
            key: {
                "source": self.name,
                "sourcePage": "bulk_quote",
                "fetchedAt": fetched_at,
            }
            for key in fields
            if key not in {"code"}
        }
        return ProviderResult(
            provider=self.name,
            page="bulk_quote",
            market=market.upper(),
            code=code,
            fetched_at=fetched_at,
            fields=fields,
            provenance=provenance,
        )


__all__ = ("TencentQuoteProvider", "tencent_quote_fields")
