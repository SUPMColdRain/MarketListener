"""Unit tests for offline revenue-row canonicalisation (no network)."""

from __future__ import annotations

import pytest

from market_monitor.industry_graph.f10.segments import (
    largest_revenue_segment,
    migrate_revenue_rows,
    revenue_classification,
    upgrade_revenue_row,
)


def test_explicit_classification_wins() -> None:
    row = {"classification": "business", "classification_label": "主营业务"}
    assert revenue_classification(row) == ("business", "主营业务")


def test_type_taxonomy_maps_to_classification() -> None:
    assert revenue_classification({"type": "1"}) == ("industry", "行业")
    assert revenue_classification({"type": "2"}) == ("product", "产品")
    assert revenue_classification({"type": "3"}) == ("region", "地区")


def test_label_text_fallback() -> None:
    assert revenue_classification({"classification_label": "按产品分类"}) == ("product", "按产品分类")
    assert revenue_classification({"classification_label": "按地区分类"}) == ("region", "按地区分类")
    assert revenue_classification({"item": "医药制造业"}) is None


def test_upgrade_revenue_row_is_non_destructive() -> None:
    row = {
        "type": "2",
        "item": "LPDDR系列",
        "income": 40_703_545_008.2,
        "ratio": 0.658641,
        "period": "2025-12-31 00:00:00",
    }
    upgraded = upgrade_revenue_row(row)
    assert upgraded["item"] == "LPDDR系列"
    assert upgraded["item_name"] == "LPDDR系列"
    assert upgraded["income"] == 40_703_545_008.2
    assert upgraded["revenue"] == 40_703_545_008.2
    assert upgraded["classification"] == "product"
    assert upgraded["classification_label"] == "产品"
    assert upgraded["revenue_share_pct"] == pytest.approx(65.8641)
    assert upgraded["period"] == "2025-12-31"
    # Original keys keep their exact values.
    assert upgraded["type"] == "2"
    assert upgraded["ratio"] == 0.658641


def test_upgrade_revenue_row_preserves_existing_canonical_values() -> None:
    row = {
        "item_name": "DRAM",
        "classification": "product",
        "revenue": 100.0,
        "revenue_share_pct": 42.0,
        "period": "2025-12-31",
    }
    upgraded = upgrade_revenue_row(row)
    assert upgraded["revenue"] == 100.0
    assert upgraded["revenue_share_pct"] == 42.0
    assert upgraded["classification"] == "product"


def test_percentage_never_double_converted() -> None:
    row = {"ratio": 86.7695, "income": 100.0}
    upgraded = upgrade_revenue_row(row)
    assert upgraded["revenue_share_pct"] == 86.7695


def test_migrate_revenue_rows_counts_changes() -> None:
    rows = [
        {"type": "2", "item": "A", "income": 10.0, "ratio": 0.5, "period": "2025-12-31"},
        {"classification": "product", "item": "B", "revenue": 20.0, "period": "2025-12-31"},
    ]
    migrated, changed = migrate_revenue_rows(rows)
    assert changed == 2
    assert migrated[0]["classification"] == "product"
    assert migrated[1]["item_name"] == "B"
    assert migrated[1]["income"] == 20.0


def test_largest_revenue_segment_prefers_latest_period_and_product() -> None:
    rows = [
        {"item": "地区A", "type": "3", "income": 900.0, "ratio": 0.9, "period": "2025-12-31"},
        {"item": "产品B", "type": "2", "income": 500.0, "ratio": 0.5, "period": "2025-12-31"},
        {"item": "行业C", "type": "1", "income": 800.0, "ratio": 0.8, "period": "2024-12-31"},
        {"item": "产品D", "type": "2", "income": 700.0, "ratio": 0.7, "period": "2025-12-31"},
    ]
    top = largest_revenue_segment(rows)
    assert top["item"] == "产品D"


def test_largest_revenue_segment_ignores_region_only_breakdown() -> None:
    rows = [
        {"item": "中国大陆", "type": "3", "income": 800.0, "ratio": 0.8, "period": "2025-12-31"},
        {"item": "境外", "type": "3", "income": 200.0, "ratio": 0.2, "period": "2025-12-31"},
    ]
    assert largest_revenue_segment(rows) is None
