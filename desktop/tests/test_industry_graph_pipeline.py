"""FULL-702 fixed samples: normalization, extraction, merge and evaluation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from market_monitor.industry_graph.evaluate import (
    PRECISION_THRESHOLD,
    RECALL_THRESHOLD,
    evaluate_fixtures,
    evaluate_gold_standard,
)
from market_monitor.industry_graph.importers import GraphImporter
from market_monitor.industry_graph.models import AUTO_ACCEPT_THRESHOLD, Relationship
from market_monitor.industry_graph.pipeline import (
    EntityResolver,
    GraphPipeline,
    RelationshipExtractor,
    build_entity,
    normalize_name,
)


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "graph"


def _records() -> list:
    importer = GraphImporter(now=datetime(2026, 8, 6, 1, 0, 0, tzinfo=timezone.utc))
    records = []
    for path in (
        FIXTURES / "announcement" / "2026-08-01-moutai.txt",
        FIXTURES / "html" / "supply-chain.html",
        FIXTURES / "pdf" / "supply-chain.pdf",
    ):
        records.extend(importer.import_file(path).records)
    return records


def test_normalize_name_handles_suffixes_width_and_punctuation() -> None:
    assert normalize_name("华致酒行连锁管理股份有限公司", company=True) == "华致酒行"
    assert normalize_name("宜宾五粮液股份有限公司", company=True) == "宜宾五粮液"
    assert normalize_name("贵州茅台酒股份有限公司", company=True) == "贵州茅台酒"
    assert normalize_name(" ＡＢＣ－公司 ", company=True) == "abc"
    assert normalize_name("茅台酒", company=False) == "茅台酒"
    assert normalize_name("Moutai  Liquor", company=False) == "moutailiquor"


def test_duplicate_company_merge_and_alias_resolution() -> None:
    resolver = EntityResolver()
    resolver.add(build_entity("company.1", "COMPANY", "华致酒行连锁管理股份有限公司", normalized_name="华致酒行"))
    resolver.add(build_entity("company.2", "COMPANY", "华致酒行", normalized_name="华致酒行"))

    assert "company.2" not in resolver.entities
    entity, pending = resolver.ensure("华致酒行", entity_type_hint="COMPANY")
    assert pending is None
    assert entity is not None and entity.entity_id == "company.1"


def test_terminology_type_wins_over_entity_type_hint() -> None:
    resolver = EntityResolver()
    resolver.add(build_entity("product.1", "PRODUCT", "茅台酒", normalized_name="茅台酒"))

    entity, pending = resolver.ensure("茅台酒", entity_type_hint="COMPANY")
    assert pending is None
    assert entity is not None and entity.entity_type == "PRODUCT"


def test_context_alias_binding_resolves_company_pronoun() -> None:
    records = _records()
    resolver = EntityResolver()
    outcome = RelationshipExtractor(resolver).extract(records)
    source_ids = {relationship.source_entity_id for relationship in outcome.relationships}
    target_ids = {relationship.target_entity_id for relationship in outcome.relationships}

    # The pronoun 本公司 must bind to the company entity, not stay unresolved.
    moutai_entities = [
        entity
        for entity in resolver.entities.values()
        if entity.entity_type == "COMPANY" and entity.normalized_name == "贵州茅台酒"
    ]
    assert len(moutai_entities) == 1
    assert any(relationship.relationship_type == "SUPPLIES" for relationship in outcome.relationships)
    assert moutai_entities[0].entity_id in source_ids | target_ids
    assert all(relationship.confidence > 0 for relationship in outcome.relationships)


def test_extractor_finds_chinese_and_english_relationships() -> None:
    resolver = EntityResolver()
    outcome = RelationshipExtractor(resolver).extract(_records())
    signatures = {
        (relationship.relationship_type, _normalized(resolver, relationship.source_entity_id), _normalized(resolver, relationship.target_entity_id))
        for relationship in outcome.relationships
    }
    expected = {
        ("SUPPLIES", "贵州茅台酒", "华致酒行"),
        ("CUSTOMER_OF", "华致酒行", "贵州茅台酒"),
        ("COMPETES_WITH", "贵州茅台酒", "宜宾五粮液"),
        ("PRODUCES", "贵州茅台酒", "茅台酒"),
        ("PART_OF", "贵州茅台酒", "白酒"),
        ("PRODUCES", "moutai", "moutailiquor"),
        ("PURCHASES", "catl", "ganfeng"),
        ("COMPETES_WITH", "wuliangye", "moutai"),
    }
    assert expected.issubset(signatures)


def test_low_confidence_relationship_is_pending() -> None:
    from market_monitor.industry_graph.importers import ImportedRecord, EvidenceLocation

    record = ImportedRecord(
        record_id="announcement.0001",
        source_id="announcement",
        source_type="ANNOUNCEMENT",
        location=EvidenceLocation(line=1),
        snippet="贵州茅台酒股份有限公司可能向宁德时代供应电池。",
        sha256="0" * 64,
        parsed_version="1.0.0",
        extracted_at="2026-08-06T01:00:00+00:00",
    )
    result = GraphPipeline(now="2026-08-06T01:00:00+00:00").run([record])
    low_confidence = [relationship for relationship in result.relationships if relationship.confidence < AUTO_ACCEPT_THRESHOLD]
    assert low_confidence
    assert low_confidence[0].relationship_type == "SUPPLIES"
    assert low_confidence[0].confirmation_status == "PENDING"


def test_pipeline_snapshot_is_referentially_valid() -> None:
    result = GraphPipeline(now="2026-08-06T01:00:00+00:00").run(_records())
    assert result.entities
    assert result.relationships
    for relationship in result.relationships:
        assert relationship.evidence_ids
        assert relationship.confirmation_status in {"PENDING", "AUTO_ACCEPTED"}


def test_gold_standard_metrics_pass_thresholds() -> None:
    sources, metrics, gold_standard = evaluate_fixtures()
    assert len(sources) == 4
    assert metrics.entity_precision >= PRECISION_THRESHOLD
    assert metrics.entity_recall >= RECALL_THRESHOLD
    assert metrics.relationship_precision >= PRECISION_THRESHOLD
    assert metrics.relationship_recall >= RECALL_THRESHOLD
    assert metrics.passes()


def test_gold_standard_metric_math_on_controlled_output() -> None:
    gold = {
        "entities": [
            {"entity_type": "COMPANY", "name": "A公司", "normalized_name": "a"},
            {"entity_type": "PRODUCT", "name": "甲", "normalized_name": "甲"},
        ],
        "relationships": [
            {"relationship_type": "PRODUCES", "source": "a", "target": "甲"},
        ],
    }
    entities = [
        build_entity("company.1", "COMPANY", "A公司", normalized_name="a"),
        build_entity("product.1", "PRODUCT", "甲", normalized_name="甲"),
        build_entity("product.2", "PRODUCT", "乙", normalized_name="乙"),
    ]
    relationships = [
        Relationship(
            relationship_id="rel.1",
            relationship_type="PRODUCES",
            source_entity_id="company.1",
            target_entity_id="product.1",
            direction="DIRECTED",
            confidence=0.9,
            confirmation_status="AUTO_ACCEPTED",
        ),
    ]
    metrics = evaluate_gold_standard(entities, relationships, gold)
    assert metrics.entity_precision == pytest.approx(2 / 3)
    assert metrics.entity_recall == 1.0
    assert metrics.relationship_precision == 1.0
    assert metrics.relationship_recall == 1.0


def _normalized(resolver: EntityResolver, entity_id: str) -> str:
    entity = resolver.entities[entity_id]
    return entity.normalized_name
