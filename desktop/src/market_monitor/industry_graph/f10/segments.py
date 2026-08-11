"""Revenue-segment helpers shared by the fetch and read pipelines.

This module owns the offline (no-network) revenue-row rules: conservative
classification resolution, canonical percentage normalisation and the
append-safe migration used to upgrade legacy ``revenue_*.jsonl`` rows.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

_CLASSIFICATION_BY_TYPE = {
    "1": ("industry", "行业"),
    "2": ("product", "产品"),
    "3": ("region", "地区"),
}

_CLASSIFICATION_PREFERENCE = ("product", "business", "industry", "project", "other")


def _normalized_period(value: object) -> str:
    text = str(value or "").strip()
    return text[:10] if text else ""


def _positive_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def revenue_classification(row: Mapping[str, Any]) -> tuple[str, str] | None:
    """Resolve a conservative (classification, label) for a revenue row.

    Explicit ``classification`` wins; otherwise the provider's own type
    taxonomy is used.  The 1=industry / 2=product / 3=region mapping was
    verified against real payloads: the Eastmoney 688825 fixture and the
    whole CN revenue cache contain type-1 rows whose item names are
    industries (``医药制造业``, ``新能源``), type-2 rows whose items are
    products (``LPDDR系列``) and type-3 rows whose items are regions
    (``中国大陆地区``, ``境外``); the TDX fixture labels type 2 as
    ``按产品(项目)``.  When neither an explicit field nor a known type
    exists, the label text is used conservatively.
    """
    value = str(row.get("classification") or "").strip().lower()
    if value:
        label = str(row.get("classification_label") or "").strip()
        return value, label or None
    raw_type = str(row.get("type") or "").strip()
    if raw_type in _CLASSIFICATION_BY_TYPE:
        return _CLASSIFICATION_BY_TYPE[raw_type]
    label = str(row.get("classification_label") or "").strip()
    if "产品" in label:
        return "product", label
    if "业务" in label:
        return "business", label
    if "行业" in label:
        return "industry", label
    if "项目" in label:
        return "project", label
    if "地区" in label or "区域" in label:
        return "region", label
    return None


def _clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def upgrade_revenue_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return a non-destructive canonical copy of one revenue row.

    Only derivations that require no network access are added: item name
    aliasing, conservative classification/label, revenue amount from the
    legacy ``income`` field, the 0-100 ``revenue_share_pct`` and a normalised
    report period.  Everything already present in the row is preserved; no
    fact is invented and no value is overwritten.
    """

    upgraded = dict(row)
    name = (
        _clean_text(row.get("item_name"))
        or _clean_text(row.get("item"))
        or _clean_text(row.get("name"))
    )
    if name:
        upgraded.setdefault("item_name", name)
        upgraded.setdefault("item", name)
    classification = revenue_classification(row)
    if classification:
        upgraded.setdefault("classification", classification[0])
        if classification[1]:
            upgraded.setdefault("classification_label", classification[1])
    amount = _positive_number(row.get("revenue") or row.get("income") or row.get("amount"))
    if amount is not None:
        upgraded.setdefault("revenue", amount)
        upgraded.setdefault("income", amount)
    if upgraded.get("revenue_share_pct") in (None, ""):
        ratio = _positive_number(row.get("ratio"))
        if ratio is not None:
            # Canonical share is 0-100; a value already > 1 is treated as a
            # percentage from another source, never multiplied again.
            upgraded["revenue_share_pct"] = ratio * 100.0 if ratio <= 1.0 else ratio
    period = _normalized_period(row.get("period"))
    if period:
        current_period = str(upgraded.get("period") or "").strip()
        if not current_period or current_period.startswith(period):
            upgraded["period"] = period
    return upgraded


def migrate_revenue_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Upgrade legacy revenue rows in place and report how many changed."""
    migrated: list[dict[str, Any]] = []
    changed = 0
    for row in rows:
        upgraded = upgrade_revenue_row(row)
        if upgraded != dict(row):
            changed += 1
        migrated.append(upgraded)
    return migrated, changed


def _classification_of(item: Mapping[str, Any]) -> str | None:
    """Backward-compatible classification-only view of a revenue row."""
    resolved = revenue_classification(item)
    return resolved[0] if resolved else None


def largest_revenue_segment(items: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Pick the largest-revenue item from one period and one classification.

    Only items with an explicit positive revenue amount and a report period
    are considered.  The most recent period wins; within that period the
    first reasonable classification (product > business > industry > project
    > other) that has amounts is used.  Region-only breakdowns are not used
    as "largest business/product" because that would compare incomparable
    dimensions.
    """

    valid: list[Mapping[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        period = _normalized_period(item.get("period"))
        amount = _positive_number(item.get("revenue") or item.get("income") or item.get("amount"))
        if _classification_of(item) == "region":
            continue
        if period and amount is not None:
            valid.append(item)
    if not valid:
        return None
    latest_period = max(_normalized_period(item.get("period")) for item in valid)
    same_period = [item for item in valid if _normalized_period(item.get("period")) == latest_period]
    for classification in _CLASSIFICATION_PREFERENCE:
        group = [item for item in same_period if _classification_of(item) == classification]
        if group:
            return max(
                group,
                key=lambda item: float(item.get("revenue") or item.get("income") or item.get("amount") or 0),
            )
    untyped = [item for item in same_period if _classification_of(item) is None]
    if untyped:
        return max(
            untyped,
            key=lambda item: float(item.get("revenue") or item.get("income") or item.get("amount") or 0),
        )
    return None


__all__ = (
    "largest_revenue_segment",
    "migrate_revenue_rows",
    "revenue_classification",
    "upgrade_revenue_row",
)
