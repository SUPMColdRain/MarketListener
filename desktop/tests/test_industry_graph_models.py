"""FULL-700 fixed samples: schema semantics, evidence location, terminology."""

from __future__ import annotations

import pytest

from market_monitor.contracts import ContractValidationError
from market_monitor.industry_graph.models import (
    AUTO_ACCEPT_THRESHOLD,
    Entity,
    Evidence,
    EvidenceLocation,
    Relationship,
    validate_entity_document,
    validate_evidence_document,
    validate_graph_snapshot,
    validate_relationship_document,
)
from market_monitor.industry_graph.terminology import (
    AMBIGUOUS_SAMPLES,
    TERMINOLOGY_SAMPLES,
    entity_type_for_mention,
)


def _entity_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "entity_id": "company.600519",
        "entity_type": "COMPANY",
        "name": "贵州茅台酒股份有限公司",
        "normalized_name": "贵州茅台",
        "aliases": ["茅台", "贵州茅台酒股份"],
        "attributes": {"exchange": "SSE", "code": "600519"},
        "created_at": "2026-08-05T09:00:00+08:00",
        "updated_at": "2026-08-05T09:00:00+08:00",
    }


def _evidence_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "evidence_id": "evidence.0001",
        "source_id": "announcement-2026-0001",
        "source_type": "PDF",
        "location": {"page": 2, "line": 15},
        "parsed_version": "1.0.0",
        "extracted_at": "2026-08-05T09:00:00+08:00",
    }


def _relationship_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "relationship_id": "rel.0001",
        "relationship_type": "SUPPLIES",
        "source_entity_id": "company.0001",
        "target_entity_id": "company.600519",
        "direction": "DIRECTED",
        "confidence": 0.9,
        "confirmation_status": "AUTO_ACCEPTED",
        "evidence_ids": ["evidence.0001"],
        "created_at": "2026-08-05T09:00:00+08:00",
        "updated_at": "2026-08-05T09:00:00+08:00",
    }


def test_entity_schema_round_trip_and_alias_rules() -> None:
    entity = validate_entity_document(_entity_document())
    assert entity.normalized_name == "贵州茅台"
    assert entity.aliases == ("茅台", "贵州茅台酒股份")

    bad = _entity_document()
    bad["aliases"] = ["贵州茅台"]
    with pytest.raises(ContractValidationError, match="normalized_name"):
        validate_entity_document(bad)

    bad["aliases"] = ["茅台", "茅台"]
    with pytest.raises(ContractValidationError, match="unique"):
        validate_entity_document(bad)


def test_evidence_location_rules_are_source_specific() -> None:
    pdf = _evidence_document()
    assert validate_evidence_document(pdf).location.page == 2

    html = _evidence_document()
    html["source_type"] = "HTML"
    html["location"] = {"page": 1}
    with pytest.raises(ContractValidationError, match="HTML.*dom"):
        validate_evidence_document(html)

    excel = _evidence_document()
    excel["source_type"] = "EXCEL"
    excel["location"] = {"cell": "Sheet1!B2"}
    assert validate_evidence_document(excel).location.cell == "Sheet1!B2"

    empty = _evidence_document()
    empty["location"] = {}
    with pytest.raises(ContractValidationError, match="at least one"):
        validate_evidence_document(empty)

    offset_only = _evidence_document()
    offset_only["location"] = {"offset": 3}
    with pytest.raises(ContractValidationError, match="offset without line"):
        validate_evidence_document(offset_only)


def test_relationship_constraints_self_loop_confidence_and_evidence() -> None:
    relationship = validate_relationship_document(_relationship_document())
    assert relationship.confidence == 0.9

    self_loop = _relationship_document()
    self_loop["target_entity_id"] = "company.0001"
    with pytest.raises(ContractValidationError, match="must differ"):
        validate_relationship_document(self_loop)

    no_evidence = _relationship_document()
    no_evidence["evidence_ids"] = []
    with pytest.raises(ContractValidationError, match="evidence id"):
        validate_relationship_document(no_evidence)

    low_confidence = _relationship_document()
    low_confidence["confidence"] = AUTO_ACCEPT_THRESHOLD - 0.01
    with pytest.raises(ContractValidationError, match="AUTO_ACCEPTED"):
        validate_relationship_document(low_confidence)

    duplicate_evidence = _relationship_document()
    duplicate_evidence["evidence_ids"] = ["evidence.0001", "evidence.0001"]
    with pytest.raises(ContractValidationError, match="unique"):
        validate_relationship_document(duplicate_evidence)


def test_graph_snapshot_referential_integrity() -> None:
    entity = Entity(
        entity_id="company.0001",
        entity_type="COMPANY",
        name="测试供应商",
        normalized_name="测试供应商",
    )
    evidence = Evidence(
        evidence_id="evidence.0001",
        source_id="source-1",
        source_type="TEXT",
        location=EvidenceLocation(line=1),
        parsed_version="1.0.0",
        extracted_at="2026-08-05T09:00:00+08:00",
    )
    relationship = Relationship(
        relationship_id="rel.0001",
        relationship_type="SUPPLIES",
        source_entity_id="company.0001",
        target_entity_id="company.600519",
        direction="DIRECTED",
        confidence=0.9,
        confirmation_status="AUTO_ACCEPTED",
        evidence_ids=("evidence.0001",),
    )
    with pytest.raises(ContractValidationError, match="unknown target"):
        validate_graph_snapshot([entity], [evidence], [relationship])

    target = Entity(
        entity_id="company.600519",
        entity_type="COMPANY",
        name="贵州茅台",
        normalized_name="贵州茅台",
    )
    validate_graph_snapshot([entity, target], [evidence], [relationship])

    dangling = Relationship(
        relationship_id="rel.0002",
        relationship_type="SUPPLIES",
        source_entity_id="company.0001",
        target_entity_id="company.600519",
        direction="DIRECTED",
        confidence=0.9,
        confirmation_status="AUTO_ACCEPTED",
        evidence_ids=("evidence.missing",),
    )
    with pytest.raises(ContractValidationError, match="unknown evidence"):
        validate_graph_snapshot([entity, target], [evidence], [dangling])


def test_terminology_fixed_samples_are_unambiguous() -> None:
    seen: dict[str, str] = {}
    for mention, expected_type in TERMINOLOGY_SAMPLES:
        assert entity_type_for_mention(mention) == expected_type
        previous = seen.get(mention)
        assert previous is None or previous == expected_type, f"ambiguous mention {mention}"
        seen[mention] = expected_type

    for mention, context in AMBIGUOUS_SAMPLES:
        assert mention in {sample[0] for sample in TERMINOLOGY_SAMPLES}, f"{mention} ({context}) missing from table"
        assert entity_type_for_mention(mention) is not None

    assert entity_type_for_mention("不存在的实体") is None


def test_timestamp_ordering_is_enforced() -> None:
    relationship = _relationship_document()
    relationship["created_at"] = "2026-08-06T09:00:00+08:00"
    relationship["updated_at"] = "2026-08-05T09:00:00+08:00"
    with pytest.raises(ContractValidationError, match="must not be after"):
        validate_relationship_document(relationship)
