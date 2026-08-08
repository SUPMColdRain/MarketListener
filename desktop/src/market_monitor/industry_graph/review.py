"""FULL-703 human review, revision and immutable audit chain.

Human decisions (CONFIRM / REJECT / REVISE) are authoritative: the automatic
pipeline may update a relationship only while it is still ``PENDING`` or
``AUTO_ACCEPTED``, and must never overwrite ``HUMAN_CONFIRMED`` or ``REJECTED``
results.  Every mutation appends an audit entry with the previous and next
document states, the actor and a reason.  Concurrent edits are rejected by an
expected-version guard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from .models import Relationship, validate_relationship_document


class ReviewAction(Enum):
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"
    REVISE = "REVISE"
    AUTO_PROPOSE = "AUTO_PROPOSE"


class ReviewConflict(ValueError):
    """Raised when a human action is invalid for the current confirmation state."""


class HumanOverrideError(ValueError):
    """Raised when the automatic pipeline tries to overwrite a human decision."""


class ConcurrentModificationError(ValueError):
    """Raised when the caller's expected version does not match the current one."""


@dataclass(frozen=True)
class AuditEntry:
    sequence: int
    action: str
    actor: str
    target_kind: str
    target_id: str
    previous_version: int | None
    new_version: int | None
    previous_document: Mapping[str, Any] | None
    new_document: Mapping[str, Any] | None
    reason: str
    created_at: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "action": self.action,
            "actor": self.actor,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "previous_version": self.previous_version,
            "new_version": self.new_version,
            "previous_document": self.previous_document,
            "new_document": self.new_document,
            "reason": self.reason,
            "created_at": self.created_at,
        }


@dataclass
class GraphReviewStore:
    """Relationship review store with versioned revisions and an audit chain."""

    relationships: dict[str, Relationship] = field(default_factory=dict)
    audit: list[AuditEntry] = field(default_factory=list)
    _now: datetime | None = None

    def __post_init__(self) -> None:
        self.relationships = {
            relationship_id: validate_relationship_document(relationship.to_mapping())
            for relationship_id, relationship in self.relationships.items()
        }

    def relationship(self, relationship_id: str) -> Relationship:
        try:
            return self.relationships[relationship_id]
        except KeyError as error:
            raise KeyError(f"unknown relationship {relationship_id}") from error

    def confirm(
        self,
        relationship_id: str,
        actor: str,
        reason: str,
        *,
        expected_version: int | None = None,
    ) -> Relationship:
        current = self._check_version(relationship_id, expected_version)
        if current.confirmation_status == "HUMAN_CONFIRMED":
            raise ReviewConflict(f"{relationship_id} is already HUMAN_CONFIRMED")
        if current.confirmation_status not in {"PENDING", "AUTO_ACCEPTED", "REJECTED"}:
            raise ReviewConflict(
                f"cannot confirm {relationship_id} in status {current.confirmation_status}"
            )
        updated = _with_status(current, "HUMAN_CONFIRMED", self._now)
        return self._commit(ReviewAction.CONFIRM, actor, reason, current, updated)

    def reject(
        self,
        relationship_id: str,
        actor: str,
        reason: str,
        *,
        expected_version: int | None = None,
    ) -> Relationship:
        current = self._check_version(relationship_id, expected_version)
        if current.confirmation_status == "REJECTED":
            raise ReviewConflict(f"{relationship_id} is already REJECTED")
        updated = _with_status(current, "REJECTED", self._now)
        return self._commit(ReviewAction.REJECT, actor, reason, current, updated)

    def revise(
        self,
        relationship_id: str,
        new_document: Mapping[str, Any],
        actor: str,
        reason: str,
        *,
        expected_version: int | None = None,
    ) -> Relationship:
        current = self._check_version(relationship_id, expected_version)
        if current.confirmation_status == "SUPERSEDED":
            raise ReviewConflict(f"{relationship_id} is SUPERSEDED and cannot be revised")
        replacement = _as_relationship(new_document, version=current.version + 1)
        replacement = _with_status(replacement, "HUMAN_CONFIRMED", self._now)
        superseded = _with_status(current, "SUPERSEDED", self._now)
        self.relationships[relationship_id] = superseded
        self.relationships[replacement.relationship_id] = replacement
        self._append_audit(
            ReviewAction.REVISE,
            actor,
            reason,
            superseded,
            replacement,
        )
        return replacement

    def propose(
        self,
        relationship: Relationship,
        actor: str = "auto-pipeline",
        reason: str = "automatic pipeline update",
        *,
        expected_version: int | None = None,
    ) -> Relationship:
        """Apply an automatic pipeline update without overriding human decisions."""

        incoming = validate_relationship_document(relationship.to_mapping())
        current = self.relationships.get(incoming.relationship_id)
        if current is None:
            self.relationships[incoming.relationship_id] = incoming
            self._append_audit(ReviewAction.AUTO_PROPOSE, actor, reason, None, incoming)
            return incoming
        if current.confirmation_status in {"HUMAN_CONFIRMED", "REJECTED"}:
            raise HumanOverrideError(
                f"automatic pipeline cannot overwrite {current.relationship_id} "
                f"in status {current.confirmation_status}"
            )
        if expected_version is not None and expected_version != current.version:
            raise ConcurrentModificationError(
                f"expected version {expected_version}, current version {current.version}"
            )
        updated = _as_relationship(incoming.to_mapping(), version=current.version + 1)
        return self._commit(ReviewAction.AUTO_PROPOSE, actor, reason, current, updated)

    def audit_trail(self, target_id: str) -> tuple[AuditEntry, ...]:
        return tuple(entry for entry in self.audit if entry.target_id == target_id)

    def revisions(self, relationship_id: str) -> tuple[Relationship, ...]:
        trail = self.audit_trail(relationship_id)
        ids = {relationship_id}
        for entry in trail:
            if entry.new_document is not None:
                ids.add(str(entry.new_document["relationship_id"]))
            if entry.previous_document is not None:
                ids.add(str(entry.previous_document["relationship_id"]))
        return tuple(
            sorted(
                (self.relationships[item] for item in ids if item in self.relationships),
                key=lambda item: item.version,
            )
        )

    def _check_version(self, relationship_id: str, expected_version: int | None) -> Relationship:
        current = self.relationship(relationship_id)
        if expected_version is not None and expected_version != current.version:
            raise ConcurrentModificationError(
                f"expected version {expected_version}, current version {current.version}"
            )
        return current

    def _commit(
        self,
        action: ReviewAction,
        actor: str,
        reason: str,
        previous: Relationship,
        updated: Relationship,
    ) -> Relationship:
        self.relationships[updated.relationship_id] = updated
        self._append_audit(action, actor, reason, previous, updated)
        return updated

    def _append_audit(
        self,
        action: ReviewAction,
        actor: str,
        reason: str,
        previous: Relationship | None,
        updated: Relationship | None,
    ) -> None:
        self.audit.append(
            AuditEntry(
                sequence=len(self.audit) + 1,
                action=action.value,
                actor=actor,
                target_kind="RELATIONSHIP",
                target_id=(previous or updated).relationship_id,  # type: ignore[union-attr]
                previous_version=previous.version if previous else None,
                new_version=updated.version if updated else None,
                previous_document=previous.to_mapping() if previous else None,
                new_document=updated.to_mapping() if updated else None,
                reason=reason,
                created_at=_iso(self._now),
            )
        )

    @property
    def now(self) -> datetime:
        return self._now or datetime.now(timezone.utc)


def _with_status(relationship: Relationship, status: str, now: datetime | None) -> Relationship:
    timestamp = _iso(now)
    return Relationship(
        relationship_id=relationship.relationship_id,
        relationship_type=relationship.relationship_type,
        source_entity_id=relationship.source_entity_id,
        target_entity_id=relationship.target_entity_id,
        direction=relationship.direction,
        confidence=relationship.confidence,
        confirmation_status=status,
        evidence_ids=relationship.evidence_ids,
        created_at=relationship.created_at,
        updated_at=timestamp or relationship.updated_at,
        version=relationship.version,
    )


def _as_relationship(document: Mapping[str, Any], *, version: int | None = None) -> Relationship:
    validated = validate_relationship_document(document)
    return Relationship(
        relationship_id=validated.relationship_id,
        relationship_type=validated.relationship_type,
        source_entity_id=validated.source_entity_id,
        target_entity_id=validated.target_entity_id,
        direction=validated.direction,
        confidence=validated.confidence,
        confirmation_status=validated.confirmation_status,
        evidence_ids=validated.evidence_ids,
        created_at=validated.created_at,
        updated_at=validated.updated_at,
        version=version or validated.version,
    )


def _iso(value: datetime | None) -> str:
    now = value or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.isoformat()
