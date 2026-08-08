"""FULL-702 gold-standard evaluation for the industry-graph pipeline.

The evaluator compares pipeline entities/relationships against the fixed gold
standard in ``tests/fixtures/graph/gold-standard.json`` and reports precision,
recall and F1 for entities and relationships.  COMPETES_WITH is treated as
undirected, so either direction matches the gold standard.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from .importers import GraphImporter
from .models import Entity, Relationship
from .pipeline import GraphPipeline

PRECISION_THRESHOLD = 0.8
RECALL_THRESHOLD = 0.7


@dataclass(frozen=True)
class Metrics:
    entity_precision: float
    entity_recall: float
    entity_f1: float
    relationship_precision: float
    relationship_recall: float
    relationship_f1: float
    entity_matched: int
    entity_actual: int
    entity_expected: int
    relationship_matched: int
    relationship_actual: int
    relationship_expected: int

    def passes(self) -> bool:
        return (
            self.entity_precision >= PRECISION_THRESHOLD
            and self.entity_recall >= RECALL_THRESHOLD
            and self.relationship_precision >= PRECISION_THRESHOLD
            and self.relationship_recall >= RECALL_THRESHOLD
        )

    def as_mapping(self) -> dict[str, object]:
        return {
            "entity_precision": self.entity_precision,
            "entity_recall": self.entity_recall,
            "entity_f1": self.entity_f1,
            "relationship_precision": self.relationship_precision,
            "relationship_recall": self.relationship_recall,
            "relationship_f1": self.relationship_f1,
            "entity_matched": self.entity_matched,
            "entity_actual": self.entity_actual,
            "entity_expected": self.entity_expected,
            "relationship_matched": self.relationship_matched,
            "relationship_actual": self.relationship_actual,
            "relationship_expected": self.relationship_expected,
            "thresholds": {"precision": PRECISION_THRESHOLD, "recall": RECALL_THRESHOLD},
        }


def evaluate_gold_standard(
    entities: Iterable[Entity],
    relationships: Iterable[Relationship],
    gold_standard: Mapping[str, object],
) -> Metrics:
    """Compare pipeline output with the fixed gold standard."""

    expected_entities = {
        _entity_key(str(item["entity_type"]), str(item["normalized_name"]))
        for item in gold_standard["entities"]  # type: ignore[index]
    }
    expected_relationships = {
        _canonical_signature(str(item["relationship_type"]), str(item["source"]), str(item["target"]))
        for item in gold_standard["relationships"]  # type: ignore[index]
    }

    actual_entities = {_entity_key(entity.entity_type, entity.normalized_name) for entity in entities}
    entity_matched = len(actual_entities & expected_entities)
    entity_precision = _ratio(entity_matched, len(actual_entities))
    entity_recall = _ratio(entity_matched, len(expected_entities))

    actual_relationships: set[tuple[str, str, str]] = set()
    for relationship in relationships:
        source = _normalized_for(relationship.source_entity_id, entities)
        target = _normalized_for(relationship.target_entity_id, entities)
        actual_relationships.add(_canonical_signature(relationship.relationship_type, source, target))

    relationship_matched = len(actual_relationships & expected_relationships)
    relationship_precision = _ratio(relationship_matched, len(actual_relationships))
    relationship_recall = _ratio(relationship_matched, len(expected_relationships))
    return Metrics(
        entity_precision=entity_precision,
        entity_recall=entity_recall,
        entity_f1=_f1(entity_precision, entity_recall),
        relationship_precision=relationship_precision,
        relationship_recall=relationship_recall,
        relationship_f1=_f1(relationship_precision, relationship_recall),
        entity_matched=entity_matched,
        entity_actual=len(actual_entities),
        entity_expected=len(expected_entities),
        relationship_matched=relationship_matched,
        relationship_actual=len(actual_relationships),
        relationship_expected=len(expected_relationships),
    )


def evaluate_fixtures() -> tuple[list[Path], Metrics, Mapping[str, object]]:
    """Run the pipeline over the checked-in graph fixtures."""

    repo_root = Path(__file__).resolve().parents[4]
    fixture_dir = repo_root / "tests" / "fixtures" / "graph"
    sources = [
        fixture_dir / "html" / "supply-chain.html",
        fixture_dir / "excel" / "supply-chain.xlsx",
        fixture_dir / "pdf" / "supply-chain.pdf",
        fixture_dir / "announcement" / "2026-08-01-moutai.txt",
    ]
    gold_standard = json.loads((fixture_dir / "gold-standard.json").read_text(encoding="utf-8"))
    now = datetime(2026, 8, 6, 1, 0, 0, tzinfo=timezone.utc)
    importer = GraphImporter(now=now)
    records = []
    for path in sources:
        result = importer.import_file(path)
        records.extend(result.records)
    result = GraphPipeline(now="2026-08-06T01:00:00+00:00").run(records)
    metrics = evaluate_gold_standard(result.entities, result.relationships, gold_standard)
    return sources, metrics, gold_standard


def main(argv: list[str] | None = None) -> int:
    sources, metrics, gold_standard = evaluate_fixtures()
    payload = {
        "fixtures": [str(path.relative_to(Path(__file__).resolve().parents[4])) for path in sources],
        "gold_standard_relationships": len(gold_standard["relationships"]),  # type: ignore[index]
        "metrics": metrics.as_mapping(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if metrics.passes() else 1


def _entity_key(entity_type: str, normalized_name: str) -> tuple[str, str]:
    return (entity_type, normalized_name)


def _normalized_for(entity_id: str, entities: Iterable[Entity]) -> str:
    for entity in entities:
        if entity.entity_id == entity_id:
            return entity.normalized_name
    return entity_id


def _ratio(matched: int, total: int) -> float:
    return matched / total if total else 0.0


def _canonical_signature(relationship_type: str, source: str, target: str) -> tuple[str, str, str]:
    if relationship_type == "COMPETES_WITH":
        left, right = sorted((source, target))
        return (relationship_type, left, right)
    return (relationship_type, source, target)


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


if __name__ == "__main__":
    sys.exit(main())
