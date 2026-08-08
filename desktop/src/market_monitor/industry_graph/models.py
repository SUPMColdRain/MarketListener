"""Core industry-graph domain models and cross-field semantics.

The public JSON Schemas in ``contracts/`` describe document shape; this module
enforces the cross-field rules that JSON Schema cannot express alone: evidence
location completeness per source type, relationship referential integrity,
self-loop rejection, confidence/status consistency and timestamp ordering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from market_monitor.contracts import ContractValidationError, validate_contract

ENTITY_TYPES = ("COMPANY", "PRODUCT", "INDUSTRY", "SUPPLIER", "CUSTOMER", "RAW_MATERIAL", "SERVICE", "REGION")
RELATIONSHIP_TYPES = (
    "SUPPLIES",
    "PURCHASES",
    "PRODUCES",
    "PART_OF",
    "COMPETES_WITH",
    "DISTRIBUTES",
    "USES",
    "OWNS",
    "CUSTOMER_OF",
)
CONFIRMATION_STATUSES = ("PENDING", "AUTO_ACCEPTED", "HUMAN_CONFIRMED", "REJECTED", "SUPERSEDED")

#: A relationship at or above this confidence may be AUTO_ACCEPTED; below it
#: the automatic pipeline must leave the relationship PENDING for human review.
AUTO_ACCEPT_THRESHOLD = 0.8


class EntityType(Enum):
    COMPANY = "COMPANY"
    PRODUCT = "PRODUCT"
    INDUSTRY = "INDUSTRY"
    SUPPLIER = "SUPPLIER"
    CUSTOMER = "CUSTOMER"
    RAW_MATERIAL = "RAW_MATERIAL"
    SERVICE = "SERVICE"
    REGION = "REGION"


class RelationshipType(Enum):
    SUPPLIES = "SUPPLIES"
    PURCHASES = "PURCHASES"
    PRODUCES = "PRODUCES"
    PART_OF = "PART_OF"
    COMPETES_WITH = "COMPETES_WITH"
    DISTRIBUTES = "DISTRIBUTES"
    USES = "USES"
    OWNS = "OWNS"
    CUSTOMER_OF = "CUSTOMER_OF"


class ConfirmationStatus(Enum):
    PENDING = "PENDING"
    AUTO_ACCEPTED = "AUTO_ACCEPTED"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class Entity:
    entity_id: str
    entity_type: str
    name: str
    normalized_name: str
    aliases: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class EvidenceLocation:
    page: int | None = None
    cell: str | None = None
    dom: str | None = None
    line: int | None = None
    offset: int | None = None

    def as_mapping(self) -> dict[str, int | str]:
        result: dict[str, int | str] = {}
        if self.page is not None:
            result["page"] = self.page
        if self.cell is not None:
            result["cell"] = self.cell
        if self.dom is not None:
            result["dom"] = self.dom
        if self.line is not None:
            result["line"] = self.line
        if self.offset is not None:
            result["offset"] = self.offset
        return result


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source_id: str
    source_type: str
    location: EvidenceLocation
    parsed_version: str
    extracted_at: str
    sha256: str = ""

    def to_mapping(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema_version": 1,
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "location": self.location.as_mapping(),
            "parsed_version": self.parsed_version,
            "extracted_at": self.extracted_at,
        }
        if self.sha256:
            document["sha256"] = self.sha256
        return document


@dataclass(frozen=True)
class Relationship:
    relationship_id: str
    relationship_type: str
    source_entity_id: str
    target_entity_id: str
    direction: str
    confidence: float
    confirmation_status: str
    evidence_ids: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    version: int = 1

    def to_mapping(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema_version": 1,
            "relationship_id": self.relationship_id,
            "relationship_type": self.relationship_type,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "direction": self.direction,
            "confidence": self.confidence,
            "confirmation_status": self.confirmation_status,
        }
        if self.evidence_ids:
            document["evidence_ids"] = list(self.evidence_ids)
        if self.created_at:
            document["created_at"] = self.created_at
        if self.updated_at:
            document["updated_at"] = self.updated_at
        return document


def validate_entity_document(document: Mapping[str, Any]) -> Entity:
    validate_contract("industry-graph-entity.schema.json", dict(document))
    aliases = tuple(str(item) for item in document.get("aliases", ()))
    if document["normalized_name"] in aliases:
        raise ContractValidationError("normalized_name must not appear in aliases")
    if len(set(aliases)) != len(aliases):
        raise ContractValidationError("aliases must be unique")
    return Entity(
        entity_id=str(document["entity_id"]),
        entity_type=str(document["entity_type"]),
        name=str(document["name"]),
        normalized_name=str(document["normalized_name"]),
        aliases=aliases,
        attributes=dict(document.get("attributes", {})),
        created_at=str(document.get("created_at", "")),
        updated_at=str(document.get("updated_at", "")),
    )


def validate_evidence_document(document: Mapping[str, Any]) -> Evidence:
    validate_contract("industry-graph-evidence.schema.json", dict(document))
    location = _parse_location(document["location"])
    _validate_location_for_source(str(document["source_type"]), location)
    _validate_timestamps(document, ("extracted_at",))
    return Evidence(
        evidence_id=str(document["evidence_id"]),
        source_id=str(document["source_id"]),
        source_type=str(document["source_type"]),
        location=location,
        parsed_version=str(document["parsed_version"]),
        extracted_at=str(document["extracted_at"]),
        sha256=str(document.get("sha256", "")),
    )


def validate_relationship_document(document: Mapping[str, Any]) -> Relationship:
    validate_contract("industry-graph-relationship.schema.json", dict(document))
    source = str(document["source_entity_id"])
    target = str(document["target_entity_id"])
    if source == target:
        raise ContractValidationError("relationship source_entity_id and target_entity_id must differ")
    status = str(document["confirmation_status"])
    confidence = float(document["confidence"])
    evidence_ids = tuple(str(item) for item in document.get("evidence_ids", ()))
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ContractValidationError("evidence_ids must be unique")
    if status in {"AUTO_ACCEPTED", "HUMAN_CONFIRMED"} and not evidence_ids:
        raise ContractValidationError(f"{status} relationships must cite at least one evidence id")
    if status == "AUTO_ACCEPTED" and confidence < AUTO_ACCEPT_THRESHOLD:
        raise ContractValidationError(
            f"AUTO_ACCEPTED requires confidence >= {AUTO_ACCEPT_THRESHOLD}; got {confidence}"
        )
    _validate_timestamps(document, ("created_at", "updated_at"), allow_partial=True)
    return Relationship(
        relationship_id=str(document["relationship_id"]),
        relationship_type=str(document["relationship_type"]),
        source_entity_id=source,
        target_entity_id=target,
        direction=str(document["direction"]),
        confidence=confidence,
        confirmation_status=status,
        evidence_ids=evidence_ids,
        created_at=str(document.get("created_at", "")),
        updated_at=str(document.get("updated_at", "")),
    )


def validate_graph_snapshot(
    entities: Mapping[str, Entity] | list[Entity],
    evidence: Mapping[str, Evidence] | list[Evidence],
    relationships: list[Relationship],
) -> None:
    """Cross-document referential integrity for one graph snapshot.

    Relationship endpoints must exist, evidence references must exist, and a
    relationship may not be its own supplier/customer (self-loop).
    """

    entity_map = {entity.entity_id: entity for entity in entities.values()} if isinstance(entities, Mapping) else {
        entity.entity_id: entity for entity in entities
    }
    evidence_map = {item.evidence_id: item for item in evidence.values()} if isinstance(evidence, Mapping) else {
        item.evidence_id: item for item in evidence
    }
    if len(entity_map) != len(entities):
        raise ContractValidationError("entity ids must be unique")
    if len(evidence_map) != len(evidence):
        raise ContractValidationError("evidence ids must be unique")
    for relationship in relationships:
        if relationship.source_entity_id not in entity_map:
            raise ContractValidationError(
                f"relationship {relationship.relationship_id} references unknown source entity "
                f"{relationship.source_entity_id}"
            )
        if relationship.target_entity_id not in entity_map:
            raise ContractValidationError(
                f"relationship {relationship.relationship_id} references unknown target entity "
                f"{relationship.target_entity_id}"
            )
        for evidence_id in relationship.evidence_ids:
            if evidence_id not in evidence_map:
                raise ContractValidationError(
                    f"relationship {relationship.relationship_id} references unknown evidence {evidence_id}"
                )
        validate_relationship_document(relationship.to_mapping())


def _parse_location(raw: Mapping[str, Any]) -> EvidenceLocation:
    return EvidenceLocation(
        page=raw.get("page"),
        cell=raw.get("cell"),
        dom=raw.get("dom"),
        line=raw.get("line"),
        offset=raw.get("offset"),
    )


def _validate_location_for_source(source_type: str, location: EvidenceLocation) -> None:
    if location.offset is not None and location.line is None:
        raise ContractValidationError("offset without line is not a precise location")
    present = {
        name
        for name, value in {
            "page": location.page,
            "cell": location.cell,
            "dom": location.dom,
            "line": location.line,
        }.items()
        if value is not None
    }
    if not present:
        raise ContractValidationError("evidence location must contain at least one of page/cell/dom/line")
    per_source: dict[str, set[str]] = {
        "HTML": {"dom"},
        "EXCEL": {"cell"},
        "PDF": {"page", "line"},
        "ANNOUNCEMENT": {"line", "page"},
        "TEXT": {"line", "page"},
    }
    required = per_source.get(source_type)
    if required is not None and not required.issubset(present):
        raise ContractValidationError(f"{source_type} evidence location requires {sorted(required)}; got {sorted(present)}")


def _validate_timestamps(
    document: Mapping[str, Any],
    fields: tuple[str, ...],
    allow_partial: bool = False,
) -> None:
    values = []
    for field_name in fields:
        value = document.get(field_name)
        if value in (None, ""):
            if allow_partial:
                continue
            raise ContractValidationError(f"{field_name} is required")
        values.append(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    if len(values) == 2 and values[0] > values[1]:
        raise ContractValidationError(f"{fields[0]} must not be after {fields[1]}")
