"""FULL-703 fixed samples: human review, revision, audit and concurrency."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from market_monitor.industry_graph.models import Relationship
from market_monitor.industry_graph.review import (
    ConcurrentModificationError,
    GraphReviewStore,
    HumanOverrideError,
    ReviewConflict,
)


NOW = datetime(2026, 8, 6, 2, 0, 0, tzinfo=timezone.utc)


def _relationship(
    relationship_id: str = "rel.0001",
    *,
    status: str = "AUTO_ACCEPTED",
    version: int = 1,
    confidence: float = 0.92,
) -> Relationship:
    return Relationship(
        relationship_id=relationship_id,
        relationship_type="SUPPLIES",
        source_entity_id="company.0001",
        target_entity_id="company.0002",
        direction="DIRECTED",
        confidence=confidence,
        confirmation_status=status,
        evidence_ids=("evidence.0001",),
        created_at="2026-08-06T01:00:00+00:00",
        updated_at="2026-08-06T01:00:00+00:00",
        version=version,
    )


def _store(relationship: Relationship | None = None) -> GraphReviewStore:
    return GraphReviewStore(
        relationships={relationship.relationship_id: relationship} if relationship else {},
        _now=NOW,
    )


def test_confirm_sets_human_confirmed_and_writes_audit_entry() -> None:
    store = _store(_relationship())
    confirmed = store.confirm("rel.0001", actor="auditor-a", reason="公告核对无误")

    assert confirmed.confirmation_status == "HUMAN_CONFIRMED"
    assert store.relationship("rel.0001").confirmation_status == "HUMAN_CONFIRMED"
    trail = store.audit_trail("rel.0001")
    assert len(trail) == 1
    entry = trail[0]
    assert entry.action == "CONFIRM"
    assert entry.actor == "auditor-a"
    assert entry.previous_document["confirmation_status"] == "AUTO_ACCEPTED"  # type: ignore[index]
    assert entry.new_document["confirmation_status"] == "HUMAN_CONFIRMED"  # type: ignore[index]
    assert entry.created_at == NOW.isoformat()


def test_reject_then_auto_pipeline_cannot_override() -> None:
    store = _store(_relationship())
    rejected = store.reject("rel.0001", actor="auditor-a", reason="证据定位错误")

    assert rejected.confirmation_status == "REJECTED"
    with pytest.raises(HumanOverrideError):
        store.propose(_relationship(status="AUTO_ACCEPTED"))


def test_auto_pipeline_cannot_override_human_confirmed() -> None:
    store = _store(_relationship())
    store.confirm("rel.0001", actor="auditor-a", reason="人工确认")

    with pytest.raises(HumanOverrideError):
        store.propose(_relationship(status="AUTO_ACCEPTED"))


def test_revise_supersedes_old_and_creates_versioned_replacement() -> None:
    store = _store(_relationship())
    replacement_document = _relationship().to_mapping()
    replacement_document["relationship_id"] = "rel.0001.v2"
    replacement_document["target_entity_id"] = "company.0003"

    replacement = store.revise(
        "rel.0001",
        replacement_document,
        actor="auditor-a",
        reason="更正目标公司",
    )

    assert replacement.relationship_id == "rel.0001.v2"
    assert replacement.version == 2
    assert replacement.confirmation_status == "HUMAN_CONFIRMED"
    assert store.relationship("rel.0001").confirmation_status == "SUPERSEDED"
    revisions = store.revisions("rel.0001")
    assert [item.relationship_id for item in revisions] == ["rel.0001", "rel.0001.v2"]
    trail = store.audit_trail("rel.0001")
    assert len(trail) == 1
    assert trail[0].action == "REVISE"
    assert trail[0].new_version == 2


def test_auto_propose_updates_pending_with_next_version() -> None:
    store = _store(_relationship(status="PENDING"))
    updated = store.propose(_relationship(status="AUTO_ACCEPTED", confidence=0.95))

    assert updated.version == 2
    assert store.relationship("rel.0001").version == 2
    assert len(store.audit) == 1


def test_expected_version_conflict_is_rejected() -> None:
    store = _store(_relationship())

    with pytest.raises(ConcurrentModificationError):
        store.confirm("rel.0001", actor="auditor-a", reason="过期版本", expected_version=2)


def test_confirm_already_human_confirmed_conflicts() -> None:
    store = _store(_relationship())
    store.confirm("rel.0001", actor="auditor-a", reason="第一次确认")

    with pytest.raises(ReviewConflict, match="already HUMAN_CONFIRMED"):
        store.confirm("rel.0001", actor="auditor-a", reason="重复确认")


def test_audit_trail_is_ordered_and_immutable() -> None:
    store = _store(_relationship(status="PENDING"))
    store.confirm("rel.0001", actor="auditor-a", reason="确认")
    store.reject("rel.0001", actor="auditor-a", reason="再次核对后否决")

    trail = store.audit_trail("rel.0001")
    assert [entry.sequence for entry in trail] == [1, 2]
    assert [entry.action for entry in trail] == ["CONFIRM", "REJECT"]
    with pytest.raises(AttributeError):
        trail[0].reason = "改写"  # type: ignore[misc]
