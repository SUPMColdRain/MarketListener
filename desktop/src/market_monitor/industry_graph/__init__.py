"""Industry chain graph domain model, importers, pipeline and review.

The package implements the FULL-700..FULL-704 industry-graph series on the
desktop producer side: public contracts, fixed terminology samples, evidence
importers, normalization/disambiguation/extraction/merge, human review with
an audit chain, and evaluation against a gold standard.
"""

from __future__ import annotations

from .models import (
    AUTO_ACCEPT_THRESHOLD,
    CONFIRMATION_STATUSES,
    ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    Entity,
    Evidence,
    EvidenceLocation,
    Relationship,
)

__all__ = [
    "AUTO_ACCEPT_THRESHOLD",
    "CONFIRMATION_STATUSES",
    "ENTITY_TYPES",
    "RELATIONSHIP_TYPES",
    "Entity",
    "Evidence",
    "EvidenceLocation",
    "Relationship",
]

__version__ = "1.0.0"
