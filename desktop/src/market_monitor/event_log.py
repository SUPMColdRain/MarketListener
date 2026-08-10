"""Append-only structured event log for the local research terminal."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Mapping


class EventLog:
    """Daily JSONL event files; deliberately not a business-data store."""

    def __init__(self, data_root: Path) -> None:
        self.directory = Path(data_root) / "logs"
        self._lock = Lock()

    def append(self, event: Mapping[str, Any]) -> None:
        timestamp = datetime.now(timezone.utc)
        document = {"timestamp": timestamp.isoformat(timespec="seconds"), **dict(event)}
        target = self.directory / f"events-{timestamp.date().isoformat()}.jsonl"
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n")

    def page(self, *, category: str | None = None, status: str | None = None, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        if page < 1 or not 1 <= page_size <= 500:
            raise ValueError("page must be at least 1 and page_size must be between 1 and 500")
        rows: list[dict[str, Any]] = []
        for path in sorted(self.directory.glob("events-*.jsonl"), reverse=True):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in reversed(lines):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if category and row.get("category") != category:
                    continue
                if status and row.get("status") != status:
                    continue
                rows.append(row)
        start = (page - 1) * page_size
        return {"items": rows[start : start + page_size], "total": len(rows), "page": page, "pageSize": page_size}


__all__ = ("EventLog",)
