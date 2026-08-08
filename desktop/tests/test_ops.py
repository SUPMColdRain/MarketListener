import pytest

from market_monitor.ops import JobLockedError, JobStateStore, NightlyJob


def test_steps_run_in_order_and_job_passes(tmp_path) -> None:
    store = JobStateStore(tmp_path / "jobs.sqlite")
    order: list[str] = []
    job = NightlyJob(store, [("first", lambda: order.append("first")), ("second", lambda: order.append("second"))])

    status = job.run(job_id="job-1")

    assert status == "PASS"
    assert order == ["first", "second"]


def test_retries_are_bounded_and_job_fails_after_exhaustion(tmp_path) -> None:
    store = JobStateStore(tmp_path / "jobs.sqlite")
    calls = {"n": 0}

    def failing() -> None:
        calls["n"] += 1
        raise ConnectionError("network down")

    job = NightlyJob(store, [("collect", failing)], max_attempts=2)

    assert job.run(job_id="job-2") == "FAILED"
    assert calls["n"] == 2


def test_resume_continues_after_last_passed_step(tmp_path) -> None:
    store = JobStateStore(tmp_path / "jobs.sqlite")
    executed: list[str] = []

    def first() -> None:
        executed.append("first")

    def second() -> None:
        executed.append("second")

    job = NightlyJob(store, [("first", first), ("second", second)])
    assert job.run(job_id="job-3") == "PASS"

    executed.clear()
    resumed = NightlyJob(store, [("first", first), ("second", second)])
    assert resumed.run(job_id="job-3", resume=True) == "PASS"
    assert executed == ["second"]


def test_concurrent_same_job_id_is_rejected(tmp_path) -> None:
    store = JobStateStore(tmp_path / "jobs.sqlite")
    store.begin_job("job-4")
    with pytest.raises(JobLockedError):
        store.begin_job("job-4")


def test_stale_running_job_can_be_abandoned(tmp_path) -> None:
    store = JobStateStore(tmp_path / "jobs.sqlite")
    store.begin_job("job-5")
    assert not store.abandon_stale("job-5", older_than_seconds=3600)
    assert store.abandon_stale("job-5", older_than_seconds=0)
    store.begin_job("job-5")
