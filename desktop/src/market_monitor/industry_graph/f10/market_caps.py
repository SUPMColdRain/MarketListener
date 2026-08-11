"""Market-cap snapshot derivation (pure logic, no network).

Canonical market-cap snapshots bind value, currency, ``asOf`` and source
together.  Direct provider values always win; derived float market caps are
computed only when the inputs are trustworthy:

* ``price x float_shares`` when a same-market price and float share count are
  both positive (CN only by default; HK requires explicit share-class
  confirmation which the current providers do not expose);
* ``total_cap x float_shares / total_shares`` as a second-level CN fallback.

The quote's exchange ``quote_time`` is the only acceptable ``asOf`` for a
derived value; detail-page fetch times are never used as market-cap dates.
"""

from __future__ import annotations

from typing import Any, Mapping

_YI = 100_000_000.0


def _positive(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _snapshot(
    value: float,
    *,
    currency: str,
    as_of: str,
    source: str,
    derived: bool = False,
    calculation_method: str | None = None,
    inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    if value <= 0 or not currency or not as_of or not source:
        return None
    document: dict[str, Any] = {
        "value": round(value, 2),
        "currency": currency,
        "asOf": as_of,
        "source": source,
    }
    if derived:
        document["derived"] = True
    if calculation_method:
        document["calculationMethod"] = calculation_method
    if inputs:
        document["inputs"] = dict(inputs)
    return document


def _direct_snapshot(
    value: object,
    *,
    currency: str,
    as_of: str,
    source: str,
) -> dict[str, Any] | None:
    """Normalise a record-level snapshot or a legacy yi scalar."""
    if isinstance(value, Mapping):
        snapshot = dict(value)
        snapshot.setdefault("currency", currency)
        snapshot.setdefault("source", source or "tencent_quote")
        try:
            if float(snapshot.get("value", 0.0)) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        if not snapshot.get("asOf"):
            # A record snapshot without a real market date stays incomplete;
            # the quote date is only attached when the quote row carries one.
            if not as_of:
                return None
            snapshot["asOf"] = as_of
        return snapshot
    number = _positive(value)
    if number is None or not as_of:
        return None
    return _snapshot(
        number * _YI,
        currency=currency,
        as_of=as_of,
        source=source or "tencent_quote",
    )


def derive_market_caps(
    record: Mapping[str, Any],
    quote: Mapping[str, Any] | None,
    *,
    market: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, str]]:
    """Return (total_cap, float_cap, missing_reasons) for one company.

    Direct values (record snapshot first, then the Tencent quote's ``*_yi``
    scalars) always win.  A missing float cap is derived only for CN and only
    with positive inputs and a real quote date; HK stays missing with an
    explicit reason because the current sources cannot confirm the same
    share class for the price and the share count.
    """

    market_key = str(market or "CN").strip().upper()
    quote = dict(quote or {})
    currency = "HKD" if market_key == "HK" else "CNY"
    as_of = str(quote.get("quote_time") or "").strip()
    quote_source = str(quote.get("quote_source") or "tencent_quote").strip()
    reasons: dict[str, str] = {}

    total = _direct_snapshot(
        record.get("total_market_cap"),
        currency=currency,
        as_of=as_of,
        source=quote_source,
    ) or _direct_snapshot(
        quote.get("total_market_cap_yi"),
        currency=currency,
        as_of=as_of,
        source=quote_source,
    )
    float_cap = _direct_snapshot(
        record.get("float_market_cap"),
        currency=currency,
        as_of=as_of,
        source=quote_source,
    ) or _direct_snapshot(
        quote.get("float_market_cap_yi"),
        currency=currency,
        as_of=as_of,
        source=quote_source,
    )

    if float_cap is not None:
        return total, float_cap, reasons

    price = _positive(quote.get("price"))
    float_shares = _positive(record.get("float_shares"))
    total_shares = _positive(record.get("total_shares"))
    if market_key == "HK":
        reasons["float_market_cap"] = "hk_share_class_unconfirmed"
    elif not as_of:
        reasons["float_market_cap"] = "missing_quote_time"
    elif price is None or float_shares is None:
        reasons["float_market_cap"] = "missing_price_or_float_shares"
    else:
        float_cap = _snapshot(
            price * float_shares,
            currency=currency,
            as_of=as_of,
            source=quote_source,
            derived=True,
            calculation_method="price_x_float_shares",
            inputs={
                "price": price,
                "float_shares": float_shares,
                "input_asOf": as_of,
                "input_sources": {"price": quote_source, "float_shares": str(record.get("source") or "tdx")},
            },
        )

    if float_cap is None and total is not None and float_shares is not None and total_shares is not None:
        if market_key == "HK":
            reasons["float_market_cap"] = "hk_share_class_unconfirmed"
        elif not as_of:
            reasons["float_market_cap"] = "missing_quote_time"
        else:
            ratio = float_shares / total_shares
            float_cap = _snapshot(
                total["value"] * ratio,
                currency=currency,
                as_of=as_of,
                source=str(total.get("source") or quote_source),
                derived=True,
                calculation_method="total_cap_x_float_ratio",
                inputs={
                    "total_market_cap": total["value"],
                    "float_shares": float_shares,
                    "total_shares": total_shares,
                    "input_asOf": as_of,
                    "input_sources": {
                        "total_market_cap": str(total.get("source") or quote_source),
                        "float_shares": str(record.get("source") or "tdx"),
                        "total_shares": str(record.get("source") or "tdx"),
                    },
                },
            )
            reasons.pop("float_market_cap", None)
    return total, float_cap, reasons


__all__ = ("derive_market_caps",)
