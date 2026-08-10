from __future__ import annotations

from pathlib import Path

from market_monitor.event_log import EventLog


def test_event_log_is_daily_jsonl_and_supports_bounded_read_only_filters(tmp_path: Path) -> None:
    events = EventLog(tmp_path)
    events.append({"category": "Operation", "status": "PASS", "operation": "ATLAS_BUILD"})
    events.append({"category": "Provider", "status": "FAILED", "detail": "timeout"})

    page = events.page(category="Operation", page_size=1)

    assert page["total"] == 1
    assert page["items"][0]["operation"] == "ATLAS_BUILD"
    assert list((tmp_path / "logs").glob("events-*.jsonl"))
