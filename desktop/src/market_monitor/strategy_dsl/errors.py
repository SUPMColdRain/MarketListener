"""Structured error taxonomy for Strategy DSL v1."""

from __future__ import annotations

from enum import Enum


class DslErrorKind(str, Enum):
    SCHEMA = "SCHEMA"
    UNKNOWN_NODE = "UNKNOWN_NODE"
    CYCLE = "CYCLE"
    LIMIT = "LIMIT"
    NO_DATA = "NO_DATA"
    PARAMETER = "PARAMETER"
    TYPE = "TYPE"
    NUMERIC = "NUMERIC"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class StrategyDslError(Exception):
    """Carries a stable machine-readable kind so runners never mix categories."""

    def __init__(self, kind: DslErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind.value, "message": str(self)}
