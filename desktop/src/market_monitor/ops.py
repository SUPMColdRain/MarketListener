"""Nightly job state machine with locking, bounded retries and crash recovery."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from uuid import uuid4


class JobLockedError(RuntimeError):
    """Raised when another process already owns the nightly job."""


@dataclass(frozen=True)
class StepResult:
    step: str
    status: str
    attempts: int
    detail: str | None = None


class JobStateStore:
    """Persistent job/steps state so a crashed run resumes after the last PASS."""

    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path, timeout=10)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS job_runs (
                job_id TEXT PRIMARY KEY, status TEXT NOT NULL, started_at TEXT NOT NULL,
                completed_at TEXT, detail TEXT
            )"""
        )
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS job_steps (
                job_id TEXT NOT NULL, step_name TEXT NOT NULL, status TEXT NOT NULL,
                attempt INTEGER NOT NULL, started_at TEXT NOT NULL, completed_at TEXT,
                detail TEXT, PRIMARY KEY (job_id, step_name, attempt)
            )"""
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def begin_job(self, job_id: str) -> None:
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            running = self.connection.execute(
                "SELECT 1 FROM job_runs WHERE job_id=? AND status='RUNNING'", (job_id,)
            ).fetchone()
            if running:
                self.connection.rollback()
                raise JobLockedError(f"job already running: {job_id}")
            self.connection.execute(
                """INSERT INTO job_runs (job_id, status, started_at, completed_at, detail)
                VALUES (?, 'RUNNING', ?, NULL, NULL)
                ON CONFLICT(job_id) DO UPDATE SET status='RUNNING', started_at=excluded.started_at,
                    completed_at=NULL, detail=NULL""",
                (job_id, _now()),
            )
            self.connection.commit()
        except sqlite3.OperationalError as error:
            self.connection.rollback()
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                raise JobLockedError(str(error)) from error
            raise

    def last_completed_step(self, job_id: str) -> str | None:
        row = self.connection.execute(
            """SELECT step_name FROM job_steps
            WHERE job_id=? AND status='PASS'
            ORDER BY started_at DESC, attempt DESC LIMIT 1""",
            (job_id,),
        ).fetchone()
        return str(row[0]) if row else None

    def record_step(self, job_id: str, step: str, status: str, attempt: int, detail: str | None = None) -> None:
        self.connection.execute(
            """INSERT INTO job_steps (job_id, step_name, status, attempt, started_at, completed_at, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, step_name, attempt) DO UPDATE SET
                status=excluded.status, completed_at=excluded.completed_at, detail=excluded.detail""",
            (job_id, step, status, attempt, _now(), _now(), detail),
        )
        self.connection.commit()

    def finish_job(self, job_id: str, status: str, detail: str | None = None) -> None:
        self.connection.execute(
            "UPDATE job_runs SET status=?, completed_at=?, detail=? WHERE job_id=?",
            (status, _now(), detail, job_id),
        )
        self.connection.commit()

    def abandon_stale(self, job_id: str, older_than_seconds: float) -> bool:
        """Mark an old RUNNING job FAILED so a new run can take over."""

        stale = self.connection.execute(
            "SELECT started_at FROM job_runs WHERE job_id=? AND status='RUNNING'", (job_id,)
        ).fetchone()
        if not stale:
            return False
        started = datetime.fromisoformat(str(stale[0]))
        now = datetime.now(timezone.utc)
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if (now - started).total_seconds() <= older_than_seconds:
            return False
        self.connection.execute(
            "UPDATE job_runs SET status='FAILED', completed_at=?, detail='abandoned stale run' WHERE job_id=?",
            (_now(), job_id),
        )
        self.connection.commit()
        return True


class NightlyJob:
    """Run named steps in order with bounded retries and resume support."""

    def __init__(
        self,
        store: JobStateStore,
        steps: Sequence[tuple[str, Callable[[], None]]],
        *,
        max_attempts: int = 3,
        backoff_seconds: float = 0.0,
        notify: Callable[[str, str], None] | None = None,
    ) -> None:
        self.store = store
        self.steps = list(steps)
        self.max_attempts = max(1, max_attempts)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self.notify = notify or (lambda level, message: None)

    def run(self, *, job_id: str | None = None, resume: bool = False) -> str:
        job_id = job_id or f"nightly-{uuid4().hex}"
        start_index = 0
        if resume:
            last_completed = self.store.last_completed_step(job_id)
            if last_completed is not None:
                names = [name for name, _ in self.steps]
                start_index = names.index(last_completed) + 1 if last_completed in names else 0
            else:
                start_index = 0
        else:
            self.store.begin_job(job_id)
        try:
            for index in range(start_index, len(self.steps)):
                name, step = self.steps[index]
                attempt = 0
                while True:
                    attempt += 1
                    try:
                        step()
                        self.store.record_step(job_id, name, "PASS", attempt)
                        break
                    except Exception as error:  # noqa: BLE001 - step failures are orchestrated
                        self.store.record_step(job_id, name, "FAILED", attempt, str(error))
                        if attempt >= self.max_attempts:
                            self.store.finish_job(job_id, "FAILED", f"step {name} exhausted attempts")
                            self.notify("error", f"nightly job {job_id} failed at step {name}: {error}")
                            return "FAILED"
                        if self.backoff_seconds:
                            sleep(self.backoff_seconds)
            self.store.finish_job(job_id, "PASS")
            self.notify("info", f"nightly job {job_id} passed")
            return "PASS"
        except JobLockedError:
            raise
        finally:
            self.store.connection.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
