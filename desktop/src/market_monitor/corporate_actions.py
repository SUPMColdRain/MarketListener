"""Corporate actions and deterministic price-adjustment factors.

Definitions (per old share, applied on the ex-date):

* ``cash_per_share``: cash dividend paid per old share.
* ``bonus_ratio``: bonus shares issued per old share (10 送 10 -> 1.0).
* ``split_ratio``: total shares per old share after a split (1 拆 2 -> 2.0).
* ``rights_ratio`` / ``rights_price``: new shares purchased per old share.

The single-action price factor is

``k = (P - cash + rights_price * rights_ratio) / (P * (split_ratio + bonus_ratio + rights_ratio))``

where ``P`` is the close on the trading day before the ex-date.  The adjusted
series is continuous across the ex-date by construction:
``adjusted_prev_close == adjusted_ex_open``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping, Sequence

from .contracts import validate_contract


@dataclass(frozen=True)
class CorporateAction:
    instrument_key: Mapping[str, str]
    action_type: str
    ex_date: date
    cash_per_share: float = 0.0
    bonus_ratio: float = 0.0
    split_ratio: float = 1.0
    rights_ratio: float = 0.0
    rights_price: float = 0.0
    provider: str = ""
    retrieved_at: str = ""

    @classmethod
    def from_mapping(cls, document: Mapping[str, object]) -> "CorporateAction":
        validate_contract("corporate-action.schema.json", dict(document))
        return cls(
            instrument_key=dict(document["instrument_key"]),  # type: ignore[arg-type]
            action_type=str(document["action_type"]),
            ex_date=date.fromisoformat(str(document["ex_date"])),
            cash_per_share=float(document.get("cash_per_share", 0.0)),
            bonus_ratio=float(document.get("bonus_ratio", 0.0)),
            split_ratio=float(document.get("split_ratio", 1.0)),
            rights_ratio=float(document.get("rights_ratio", 0.0)),
            rights_price=float(document.get("rights_price", 0.0)),
            provider=str(document["source"].get("provider", "")),
            retrieved_at=str(document["source"].get("retrieved_at", "")),
        )


@dataclass(frozen=True)
class AdjustmentFactor:
    effective_date: date
    factor: float


def single_action_factor(
    *,
    previous_close: float,
    cash_per_share: float = 0.0,
    bonus_ratio: float = 0.0,
    split_ratio: float = 1.0,
    rights_ratio: float = 0.0,
    rights_price: float = 0.0,
) -> float:
    """Return ``k`` for one corporate action (see module docstring)."""

    if previous_close <= 0:
        raise ValueError("previous_close must be positive")
    denominator = split_ratio + bonus_ratio + rights_ratio
    if denominator <= 0:
        raise ValueError("split/bonus/rights ratios must yield positive total shares")
    numerator = previous_close - cash_per_share + rights_price * rights_ratio
    if numerator <= 0:
        raise ValueError("action leaves non-positive theoretical value")
    return numerator / (previous_close * denominator)


def build_adjustment_factors(
    actions: Sequence[CorporateAction],
    previous_closes: Mapping[date, float],
    *,
    mode: str,
) -> list[AdjustmentFactor]:
    """Build a step-function factor series for ``mode``.

    The returned entries are ordered by effective date.  The multiplier for a
    bar with trading day ``d`` is the entry with the largest ``effective_date
    <= d``, or ``1.0`` before the first entry.  For ``FORWARD_ADJUSTED`` an
    epoch anchor entry carries the product of
    every action factor, so bars before the first ex-date are scaled by the
    full cumulative factor while later segments step down to ``1.0``.
    """

    if mode not in ("FORWARD_ADJUSTED", "BACKWARD_ADJUSTED"):
        raise ValueError(f"Unknown adjustment mode: {mode}")
    if not actions:
        raise ValueError("at least one corporate action is required")
    sorted_actions = sorted(actions, key=lambda action: action.ex_date)
    factors: list[tuple[date, float]] = []
    if mode == "BACKWARD_ADJUSTED":
        cumulative = 1.0
        for action in sorted_actions:
            previous_close = _previous_close(previous_closes, action.ex_date)
            k = single_action_factor(
                previous_close=previous_close,
                cash_per_share=action.cash_per_share,
                bonus_ratio=action.bonus_ratio,
                split_ratio=action.split_ratio,
                rights_ratio=action.rights_ratio,
                rights_price=action.rights_price,
            )
            cumulative /= k
            factors.append((action.ex_date, cumulative))
    else:
        ks: list[tuple[date, float]] = []
        for action in sorted_actions:
            previous_close = _previous_close(previous_closes, action.ex_date)
            ks.append(
                (
                    action.ex_date,
                    single_action_factor(
                        previous_close=previous_close,
                        cash_per_share=action.cash_per_share,
                        bonus_ratio=action.bonus_ratio,
                        split_ratio=action.split_ratio,
                        rights_ratio=action.rights_ratio,
                        rights_price=action.rights_price,
                    ),
                )
            )
        total = 1.0
        for _, k in ks:
            total *= k
        # Epoch anchor: every historical bar (before the first ex-date) is
        # scaled by the full cumulative factor in forward-adjustment mode.
        factors.append((date.min, total))
        cumulative = total
        for ex_date, k in ks:
            factors.append((ex_date, cumulative / k))
            cumulative /= k
    return [AdjustmentFactor(effective_date, factor) for effective_date, factor in factors]


def factor_for_day(factors: Sequence[AdjustmentFactor], trading_day: date) -> float:
    selected = [item.factor for item in factors if item.effective_date <= trading_day]
    return selected[-1] if selected else 1.0


def apply_adjustment(
    bars: Iterable[Mapping[str, object]],
    factors: Sequence[AdjustmentFactor],
    *,
    mode: str,
) -> list[dict[str, object]]:
    """Return new bars with OHLC multiplied by the factor for their trading day."""

    adjusted: list[dict[str, object]] = []
    for bar in bars:
        trading_day = date.fromisoformat(str(bar["trading_day"]))
        factor = factor_for_day(factors, trading_day)
        output = dict(bar)
        for field in ("open", "high", "low", "close"):
            output[field] = round(float(bar[field]) * factor, 12)
        output["price_mode"] = mode
        adjusted.append(output)
    return adjusted


def _previous_close(previous_closes: Mapping[date, float], ex_date: date) -> float:
    candidates = [day for day in previous_closes if day < ex_date]
    if not candidates:
        raise ValueError(f"missing previous close before ex-date {ex_date}")
    previous_day = max(candidates)
    return previous_closes[previous_day]
