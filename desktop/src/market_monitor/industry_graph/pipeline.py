"""FULL-702 normalization, disambiguation, extraction and merge pipeline.

The pipeline turns imported evidence records into graph entities and
relationships.  It keeps every relationship traceable to evidence, routes
low-confidence or ambiguous mentions to ``PENDING`` and merges duplicate
entities by canonical name while refusing to merge across entity types.
Evaluation against a gold standard is provided by :mod:`evaluate`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from hashlib import sha1
from typing import Iterable, Mapping

from .importers import ImportedRecord
from .models import AUTO_ACCEPT_THRESHOLD, Entity, Evidence, Relationship, validate_graph_snapshot
from .terminology import TERMINOLOGY_SAMPLES, entity_type_for_mention

COMPANY_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "集团有限公司",
    "有限公司",
    "集团",
    "公司",
)

COMPANY_TAILS = (
    "连锁管理",
    "连锁",
    "管理",
    "科技",
    "新能源",
    "实业",
    "控股",
    "投资",
    "发展",
    "集团",
)

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[，。、；：（）()【】\[\]·•－—-]+")
_FULLWIDTH = {ord(char): ord(ascii_char) for char, ascii_char in zip("０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ", "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")}


def normalize_name(name: str, *, company: bool = False) -> str:
    """Return a canonical comparison key for a mention or entity name.

    Company names have legal suffixes removed so ``华致酒行`` and
    ``华致酒行连锁管理股份有限公司`` compare equal; other entity types only
    collapse whitespace, punctuation and full-width characters.
    """

    value = name.strip().translate(_FULLWIDTH)
    value = _WHITESPACE.sub("", value)
    value = _PUNCTUATION.sub("", value)
    value = value.lower()
    if company:
        for suffix in COMPANY_SUFFIXES:
            if value.endswith(suffix) and len(value) > len(suffix):
                value = value[: -len(suffix)]
                break
        while True:
            previous = value
            for tail in COMPANY_TAILS:
                if value.endswith(tail) and len(value) > len(tail) + 1:
                    value = value[: -len(tail)]
                    break
            if value == previous:
                break
    return value.strip()


def _normalized_key(entity: Entity) -> str:
    return normalize_name(entity.name, company=entity.entity_type == "COMPANY")


@dataclass(frozen=True)
class Mention:
    """One entity mention that could not be resolved to a unique entity."""

    mention: str
    source_id: str
    reason: str
    snippet: str


@dataclass
class EntityResolver:
    """Resolves mentions to entities and merges duplicate entities."""

    entities: dict[str, Entity] = field(default_factory=dict)
    _aliases: dict[str, str] = field(default_factory=dict)
    _by_key: dict[str, str] = field(default_factory=dict)
    _context_aliases: dict[str, str] = field(default_factory=dict)

    def seed(self, entities: Iterable[Entity]) -> None:
        for entity in entities:
            self.add(entity)

    def add(self, entity: Entity) -> None:
        self.entities[entity.entity_id] = entity
        self._register_terminology_aliases(entity)
        key = _normalized_key(entity)
        previous = self._by_key.get(key)
        if previous is not None and previous != entity.entity_id:
            existing = self.entities[previous]
            if existing.entity_type == entity.entity_type:
                self._merge_into(previous, entity)
                return
        self._by_key[key] = entity.entity_id
        for alias in (entity.name, entity.normalized_name, *entity.aliases):
            normalized = normalize_name(alias, company=entity.entity_type == "COMPANY")
            if normalized:
                current = self._aliases.get(normalized)
                if current is not None and current != entity.entity_id:
                    current_entity = self.entities[current]
                    if current_entity.entity_type != entity.entity_type:
                        # Ambiguous alias across types: never choose silently.
                        continue
                    if _normalized_key(current_entity) == key:
                        self._merge_into(current, entity)
                        continue
                self._aliases[normalized] = entity.entity_id

    def _merge_into(self, keep_id: str, other: Entity) -> None:
        keep = self.entities[keep_id]
        merged_aliases = tuple(dict.fromkeys((*keep.aliases, *other.aliases, other.name, other.normalized_name)))
        merged = Entity(
            entity_id=keep.entity_id,
            entity_type=keep.entity_type,
            name=keep.name,
            normalized_name=keep.normalized_name,
            aliases=merged_aliases,
            attributes={**other.attributes, **keep.attributes},
            created_at=min(keep.created_at, other.created_at) if keep.created_at and other.created_at else keep.created_at,
            updated_at=max(keep.updated_at, other.updated_at) if keep.updated_at and other.updated_at else keep.updated_at,
        )
        self.entities[keep_id] = merged
        self.entities.pop(other.entity_id, None)
        self._aliases = {
            alias: (keep_id if entity_id == other.entity_id else entity_id)
            for alias, entity_id in self._aliases.items()
        }
        for alias in (other.name, other.normalized_name, *other.aliases):
            normalized = normalize_name(alias, company=keep.entity_type == "COMPANY")
            if normalized:
                self._aliases.setdefault(normalized, keep_id)
        self._by_key = {
            key: (keep_id if entity_id == other.entity_id else entity_id)
            for key, entity_id in self._by_key.items()
        }
        self._by_key[_normalized_key(merged)] = keep_id
        self._register_terminology_aliases(merged)

    def _register_terminology_aliases(self, entity: Entity) -> None:
        """Bind fixed company short names to the entity when they occur in its name."""

        if entity.entity_type != "COMPANY":
            return
        for sample, sample_type in TERMINOLOGY_SAMPLES:
            if sample_type != "COMPANY":
                continue
            if sample in entity.name or entity.name in sample:
                normalized = normalize_name(sample, company=True)
                if normalized:
                    self._aliases.setdefault(normalized, entity.entity_id)

    def set_context_alias(self, alias: str, entity_id: str) -> None:
        self._context_aliases[normalize_name(alias)] = entity_id
        self._context_aliases[normalize_name(alias, company=True)] = entity_id

    def resolve(self, mention: str, source_id: str = "", snippet: str = "") -> tuple[Entity | None, Mention | None]:
        """Resolve one mention; return ``(entity, pending_mention)``.

        Terminology samples win over aliases.  A mention whose canonical alias
        maps to several entity types is never silently resolved.
        """

        terminology_type = entity_type_for_mention(mention)
        if terminology_type is not None:
            candidates = [
                entity
                for entity in self.entities.values()
                if entity.entity_type == terminology_type
                and normalize_name(entity.name, company=False) == normalize_name(mention)
            ]
            if len(candidates) == 1:
                return candidates[0], None
            if len(candidates) > 1:
                return None, Mention(mention, source_id, "AMBIGUOUS_TERMINOLOGY", snippet)

        normalized = normalize_name(mention, company=True)
        for candidate_key in (normalized, normalize_name(mention, company=False)):
            entity_id = self._aliases.get(candidate_key)
            if entity_id is None:
                entity_id = self._by_key.get(candidate_key)
            if entity_id is not None:
                return self.entities[entity_id], None

        context_id = self._context_aliases.get(normalized) or self._context_aliases.get(
            normalize_name(mention, company=False)
        )
        if context_id is not None:
            return self.entities[context_id], None
        return None, Mention(mention, source_id, "UNRESOLVED", snippet)

    def ensure(
        self,
        mention: str,
        *,
        entity_type_hint: str | None = None,
        source_id: str = "",
        snippet: str = "",
    ) -> tuple[Entity | None, Mention | None]:
        """Resolve a mention, creating a new entity when it is unambiguous.

        Terminology determines the entity type when available; otherwise the
        caller's type hint is used, with COMPANY as the final fallback.  A
        mention that collides across entity types stays unresolved (PENDING).
        """

        resolved, pending = self.resolve(mention, source_id, snippet)
        if resolved is not None:
            return resolved, None
        if pending is not None and pending.reason != "UNRESOLVED":
            return None, pending
        entity_type = entity_type_for_mention(mention) or entity_type_hint or "COMPANY"
        normalized = normalize_name(mention, company=entity_type == "COMPANY")
        if not normalized:
            return None, Mention(mention, source_id, "UNRESOLVED", snippet)
        existing = self._by_key.get(normalized) or self._aliases.get(normalized)
        if existing is not None:
            existing_entity = self.entities[existing]
            if existing_entity.entity_type == entity_type:
                return existing_entity, None
            return None, Mention(mention, source_id, "CROSS_TYPE_COLLISION", snippet)
        entity_id = _entity_id(entity_type, normalized)
        entity = Entity(
            entity_id=entity_id,
            entity_type=entity_type,
            name=mention.strip(),
            normalized_name=normalized,
            aliases=(mention.strip(),),
        )
        self.add(entity)
        return entity, None


@dataclass(frozen=True)
class ExtractedRelationship:
    relationship_type: str
    source_entity_id: str
    target_entity_id: str
    confidence: float
    evidence_id: str


@dataclass(frozen=True)
class ExtractionOutcome:
    relationships: tuple[ExtractedRelationship, ...] = ()
    pending_mentions: tuple[Mention, ...] = ()


_SUPPLIES_CN = re.compile(
    r"(?P<a>[^，。；\n]+?)(?:向|给)(?P<b>[^，。；\n]+?)(?:供应|供货)(?P<item>[^，。；\n]*)"
)
_PURCHASES_CN = re.compile(
    r"(?P<a>[^，。；\n]+?)(?:从|向)(?P<b>[^，。；\n]+?)(?:采购|购买)(?P<item>[^，。；\n]*)"
)
_CUSTOMER_CN = re.compile(
    r"(?P<a>[^，。；\n]+?)(?:是|为)(?P<b>[^，。；\n]+?)(?:的)?(?:重要客户|核心客户|客户)"
)
_COMPETES_CN = re.compile(
    r"(?P<a>[^，。；\n]+?)(?:与|和)(?P<b>[^，。；\n]+?)(?:在[^，。；\n]*?)?(?:存在|构成)竞争关系"
)
_PRODUCES_CORE = re.compile(
    r"(?P<a>[^，。；\n]+?)(?:的)?核心产品(?:是|为)(?P<b>[^，。；\n]+)"
)
_INDUSTRY_OF = re.compile(
    r"(?P<a>[^，。；\n]+?)(?:所属行业|行业)(?:为|是)(?P<b>[^，。；\n]+)"
)
_PRODUCES_CN = re.compile(
    r"(?P<a>[^，。；\n]+?)(?:生产|制造)(?P<b>[^，。；\n]+)"
)
_USES_CN = re.compile(
    r"(?P<a>[^，。；\n]+?)(?:使用|采用)(?P<b>[^，。；\n]+)"
)
_MAY_SUPPLY_CN = re.compile(
    r"(?P<a>[^，。；\n]+?)可能(?:向|给)(?P<b>[^，。；\n]+?)(?:供应|供货)(?P<item>[^，。；\n]*)"
)
_ALIAS_BINDING = re.compile(r"(?P<pronoun>本公司|本公司集团|公司)（(?P<name>[^（）]+)）")

_SUPPLIES_EN = re.compile(r"(?P<a>\w+(?:\s+\w+)*?)\s+supplies\s+(?P<item>[^.]+?)\s+to\s+(?P<b>[^.]+)", re.IGNORECASE)
_PURCHASES_EN = re.compile(
    r"(?P<a>\w+(?:\s+\w+)*?)\s+purchases\s+(?P<item>[^.]+?)\s+from\s+(?P<b>[^.]+)", re.IGNORECASE
)
_PRODUCES_EN = re.compile(r"(?P<a>\w+(?:\s+\w+)*?)\s+produces\s+(?P<b>[^.]+)", re.IGNORECASE)
_COMPETES_EN = re.compile(r"(?P<a>\w+(?:\s+\w+)*?)\s+competes\s+with\s+(?P<b>[^.]+)", re.IGNORECASE)

#: (relationship type, pattern, confidence, target type hint)
_PATTERNS: tuple[tuple[str, re.Pattern[str], float, str], ...] = (
    ("SUPPLIES", _SUPPLIES_CN, 0.92, "COMPANY"),
    ("SUPPLIES", _SUPPLIES_EN, 0.92, "COMPANY"),
    ("PURCHASES", _PURCHASES_CN, 0.9, "COMPANY"),
    ("PURCHASES", _PURCHASES_EN, 0.9, "COMPANY"),
    ("CUSTOMER_OF", _CUSTOMER_CN, 0.85, "COMPANY"),
    ("COMPETES_WITH", _COMPETES_CN, 0.9, "COMPANY"),
    ("COMPETES_WITH", _COMPETES_EN, 0.9, "COMPANY"),
    ("PRODUCES", _PRODUCES_CORE, 0.95, "PRODUCT"),
    ("PART_OF", _INDUSTRY_OF, 0.9, "INDUSTRY"),
    ("PRODUCES", _PRODUCES_CN, 0.85, "PRODUCT"),
    ("PRODUCES", _PRODUCES_EN, 0.85, "PRODUCT"),
    ("USES", _USES_CN, 0.8, "PRODUCT"),
    ("SUPPLIES", _MAY_SUPPLY_CN, 0.6, "COMPANY"),
)


class RelationshipExtractor:
    """Deterministic rule-based extractor over imported evidence snippets."""

    def __init__(self, resolver: EntityResolver) -> None:
        self.resolver = resolver

    def extract(self, records: Iterable[ImportedRecord]) -> ExtractionOutcome:
        relationships: list[ExtractedRelationship] = []
        pending: list[Mention] = []
        for record in records:
            alias_match = _ALIAS_BINDING.search(record.snippet)
            if alias_match:
                pronoun = alias_match.group("pronoun")
                name = alias_match.group("name")
                entity, mention = self.resolver.ensure(
                    name,
                    entity_type_hint="COMPANY",
                    source_id=record.source_id,
                    snippet=record.snippet,
                )
                if entity is not None:
                    self.resolver.set_context_alias(pronoun, entity.entity_id)
                elif mention is not None:
                    pending.append(mention)
            subject: Entity | None = None
            for clause in _clauses(record.snippet):
                subject = self._extract_clause(clause, record, pending, subject, relationships)
        return ExtractionOutcome(tuple(relationships), tuple(pending))

    def _extract_clause(
        self,
        clause: str,
        record: ImportedRecord,
        pending: list[Mention],
        subject: Entity | None,
        relationships: list[ExtractedRelationship],
    ) -> Entity | None:
        for relationship_type, pattern, confidence, target_type_hint in _PATTERNS:
            for match in pattern.finditer(clause):
                groups = match.groupdict()
                source, subject = self._resolve_source(groups["a"], record, pending, subject)
                target_name = groups.get("b")
                target = (
                    self._resolve(target_name, record, pending, target_type_hint)
                    if target_name
                    else None
                )
                if source is None or target is None or source.entity_id == target.entity_id:
                    continue
                relationships.append(
                    ExtractedRelationship(
                        relationship_type=relationship_type,
                        source_entity_id=source.entity_id,
                        target_entity_id=target.entity_id,
                        confidence=confidence,
                        evidence_id=record.record_id,
                    )
                )
        return subject

    def _resolve_source(
        self,
        mention: str,
        record: ImportedRecord,
        pending: list[Mention],
        subject: Entity | None,
    ) -> tuple[Entity | None, Entity | None]:
        """Resolve a source mention, carrying the clause subject when needed."""

        cleaned = _strip_alias_binding(mention)
        if subject is not None and _looks_like_ellipsis_subject(cleaned):
            return subject, subject
        entity, unresolved = self.resolver.ensure(
            cleaned,
            entity_type_hint="COMPANY",
            source_id=record.source_id,
            snippet=record.snippet,
        )
        if unresolved is not None:
            pending.append(unresolved)
        if entity is not None and entity.entity_type == "COMPANY":
            return entity, entity
        return None, subject

    def _resolve(
        self,
        mention: str,
        record: ImportedRecord,
        pending: list[Mention],
        entity_type_hint: str,
    ) -> Entity | None:
        cleaned = _strip_alias_binding(mention)
        entity, unresolved = self.resolver.ensure(
            cleaned,
            entity_type_hint=entity_type_hint,
            source_id=record.source_id,
            snippet=record.snippet,
        )
        if unresolved is not None:
            pending.append(unresolved)
        return entity


@dataclass(frozen=True)
class PipelineResult:
    entities: tuple[Entity, ...]
    relationships: tuple[Relationship, ...]
    pending_mentions: tuple[Mention, ...]


class GraphPipeline:
    """End-to-end evidence -> entity/relationship pipeline with merge."""

    def __init__(self, now: str | None = None) -> None:
        self.resolver = EntityResolver()
        self.extractor = RelationshipExtractor(self.resolver)
        self._now = now or "2026-08-06T00:00:00+08:00"

    def run(
        self,
        records: Iterable[ImportedRecord],
        *,
        seed_entities: Iterable[Entity] = (),
    ) -> PipelineResult:
        self.resolver.seed(seed_entities)
        records = tuple(records)
        evidence_by_id = {
            record.record_id: Evidence(
                evidence_id=record.record_id,
                source_id=record.source_id,
                source_type=record.source_type,
                location=record.location,
                parsed_version=record.parsed_version,
                extracted_at=record.extracted_at,
                sha256=record.sha256,
            )
            for record in records
        }
        outcome = self.extractor.extract(records)
        entity_by_id: dict[str, Entity] = dict(self.resolver.entities)
        relationships: list[Relationship] = []
        for index, extracted in enumerate(outcome.relationships, start=1):
            status = "AUTO_ACCEPTED" if extracted.confidence >= AUTO_ACCEPT_THRESHOLD else "PENDING"
            relationships.append(
                Relationship(
                    relationship_id=f"rel.{index:04d}",
                    relationship_type=extracted.relationship_type,
                    source_entity_id=extracted.source_entity_id,
                    target_entity_id=extracted.target_entity_id,
                    direction="UNDIRECTED" if extracted.relationship_type == "COMPETES_WITH" else "DIRECTED",
                    confidence=extracted.confidence,
                    confirmation_status=status,
                    evidence_ids=(extracted.evidence_id,),
                    created_at=self._now,
                    updated_at=self._now,
                )
            )
        entities = tuple(sorted(entity_by_id.values(), key=lambda entity: entity.entity_id))
        validate_graph_snapshot(entities, evidence_by_id.values(), relationships)
        return PipelineResult(
            entities=entities,
            relationships=tuple(relationships),
            pending_mentions=outcome.pending_mentions,
        )


def build_entity(
    entity_id: str,
    entity_type: str,
    name: str,
    *,
    normalized_name: str | None = None,
    aliases: Iterable[str] = (),
    created_at: str = "",
) -> Entity:
    """Create an entity with a consistent canonical name."""

    normalized = normalized_name or normalize_name(name, company=entity_type == "COMPANY")
    return Entity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        normalized_name=normalized,
        aliases=tuple(aliases),
        created_at=created_at,
        updated_at=created_at,
    )


def relationship_key(relationship: Relationship | Mapping[str, str]) -> tuple[str, str, str]:
    """Canonical comparison key for one relationship (type, source, target)."""

    if isinstance(relationship, Relationship):
        return (
            relationship.relationship_type,
            relationship.source_entity_id,
            relationship.target_entity_id,
        )
    return (
        str(relationship["relationship_type"]),
        str(relationship["source_entity_id"]),
        str(relationship["target_entity_id"]),
    )


def _strip_alias_binding(mention: str) -> str:
    """Remove parenthetical bindings such as ``本公司（贵州茅台酒股份有限公司）``."""

    cleaned = re.sub(r"（[^（）]*）", "", mention)
    cleaned = re.sub(r"\([^()]*\)", "", cleaned)
    return cleaned.strip()


def _clauses(snippet: str) -> list[str]:
    """Split a snippet into sentence clauses while keeping clause order."""

    return [part.strip() for part in re.split(r"[。；\n]+", snippet) if part.strip()]


def _looks_like_ellipsis_subject(mention: str) -> bool:
    """True when a clause starts with a generic ellipsis connector."""

    return mention in {"所属", "所属行业", "其", "该", "此", "同时", "此外", "其中", "以及"}


def _entity_id(entity_type: str, normalized: str) -> str:
    digest = sha1(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{entity_type.lower()}.{digest}"
