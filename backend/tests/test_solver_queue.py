import threading
import time
from pathlib import Path

import pytest

from app.db.models import SolverJob
from app.solver.cache import get_result
from app.solver.queue import (
    JobStatus,
    Origin,
    SolverWorker,
    cancel_job,
    enqueue,
    is_paused,
    next_job,
    queue_position,
    recover_jobs,
    retry_job,
    set_paused,
)
from app.solver.spot import SolverSpot, to_solver_range
from app.solver.trees import get_preset

FIXTURES = Path(__file__).parent / "fixtures" / "solver"
FAKE = Path(__file__).parent / "fake_solver.py"


def spot(pot=20.0):
    return SolverSpot(
        ("Qs", "Jh", "2h", "7c", "3d"),
        pot,
        90.0,
        to_solver_range("AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5").text,
        to_solver_range("AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s").text,
        get_preset("simple"),
    )


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("FAKE_SOLVER_FIXTURE", str(FIXTURES / "river_out.json"))
    monkeypatch.setenv("FAKE_SOLVER_DELAY", "0.01")
    monkeypatch.setenv("FAKE_SOLVER_MODE", "ok")
    return lambda mode: monkeypatch.setenv("FAKE_SOLVER_MODE", mode)


@pytest.fixture
def worker(db_session, tmp_path):
    from app.db.session import _session_factory

    return SolverWorker(
        _session_factory(), FAKE, tmp_path, threads=2, timeout_s=30, poll_s=0.05, run_poll_s=0.02
    )


def test_enqueue_dedupes_and_bumps_priority(db_session):
    a = enqueue(db_session, spot(), Origin.LIBRARY)
    b = enqueue(db_session, spot(), Origin.SIMULATOR)
    assert a.id == b.id
    assert b.priority == 0
    assert db_session.query(SolverJob).count() == 1


def test_order_by_priority_then_age(db_session):
    lib = enqueue(db_session, spot(20), Origin.LIBRARY)
    batch = enqueue(db_session, spot(21), Origin.BATCH)
    sim = enqueue(db_session, spot(22), Origin.SIMULATOR)
    assert next_job(db_session).id == sim.id
    assert queue_position(db_session, sim) == 1
    assert queue_position(db_session, batch) == 2
    assert queue_position(db_session, lib) == 3


def test_worker_solves_and_caches(db_session, worker, fake):
    job = enqueue(db_session, spot(), Origin.SIMULATOR)
    assert worker.run_once() is True
    db_session.refresh(job)
    assert job.status == JobStatus.DONE
    assert job.iteration == 30
    assert get_result(db_session, spot().spot_hash()) is not None
    assert worker.run_once() is False  # nothing left


def test_enqueue_of_cached_spot_returns_done_job(db_session, worker, fake):
    enqueue(db_session, spot(), Origin.SIMULATOR)
    worker.run_once()
    again = enqueue(db_session, spot(), Origin.SIMULATOR)
    assert again.status == JobStatus.DONE


def test_failure_is_recorded_and_retryable(db_session, worker, fake):
    fake("fail")
    job = enqueue(db_session, spot(), Origin.BATCH)
    worker.run_once()
    db_session.refresh(job)
    assert job.status == JobStatus.FAILED
    assert "len not valid" in job.error
    fake("ok")
    retry_job(db_session, job.id)
    worker.run_once()
    db_session.refresh(job)
    assert job.status == JobStatus.DONE


def test_cancel_queued_job(db_session):
    job = enqueue(db_session, spot(), Origin.BATCH)
    assert cancel_job(db_session, job.id).status == JobStatus.CANCELLED
    assert next_job(db_session) is None


def test_cancel_running_job_stops_the_solver(db_session, worker, fake):
    fake("hang")
    job = enqueue(db_session, spot(), Origin.BATCH)
    t = threading.Thread(target=worker.run_once)
    t.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        db_session.refresh(job)
        if job.status == JobStatus.RUNNING and job.iteration > 0:
            break
        time.sleep(0.02)
    cancel_job(db_session, job.id)
    t.join(10)
    assert not t.is_alive()
    db_session.refresh(job)
    assert job.status == JobStatus.CANCELLED


def test_simulator_job_preempts_running_batch(db_session, worker, fake):
    fake("hang")
    batch = enqueue(db_session, spot(20), Origin.BATCH)
    t = threading.Thread(target=worker.run_once)
    t.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        db_session.refresh(batch)
        if batch.status == JobStatus.RUNNING and batch.iteration > 0:
            break
        time.sleep(0.02)
    sim = enqueue(db_session, spot(21), Origin.SIMULATOR)
    t.join(10)
    assert not t.is_alive()
    db_session.refresh(batch)
    assert batch.status == JobStatus.QUEUED
    assert batch.priority == 10
    assert next_job(db_session).id == sim.id


def test_pause_blocks_the_worker(db_session, worker, fake):
    enqueue(db_session, spot(), Origin.BATCH)
    set_paused(db_session, True)
    assert is_paused(db_session)
    assert worker.run_once() is False
    set_paused(db_session, False)
    assert worker.run_once() is True


def test_recover_requeues_running_jobs(db_session):
    job = enqueue(db_session, spot(), Origin.BATCH)
    job.status = JobStatus.RUNNING
    job.pid = 999999  # not alive
    db_session.commit()
    assert recover_jobs(db_session) == 1
    db_session.refresh(job)
    assert job.status == JobStatus.QUEUED and job.pid is None


def test_failed_workdirs_are_capped(db_session, worker, fake, tmp_path):
    fake("fail")
    for pot in range(20, 27):
        enqueue(db_session, spot(pot), Origin.BATCH)
        worker.run_once()
    jobs_dir = tmp_path / "solver" / "jobs"
    assert len(list(jobs_dir.iterdir())) == 5


def _start_running(db_session, worker, job):
    t = threading.Thread(target=worker.run_once)
    t.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        db_session.refresh(job)
        if job.status == JobStatus.RUNNING and job.iteration > 0:
            break
        time.sleep(0.02)
    return t


def _join(t):
    t.join(10)
    assert not t.is_alive()


def test_unexpected_exception_marks_job_failed(db_session, worker, fake, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaput")

    monkeypatch.setattr("app.solver.queue.parse_output", boom)
    job = enqueue(db_session, spot(), Origin.BATCH)
    assert worker.run_once() is True
    db_session.refresh(job)
    assert job.status == JobStatus.FAILED
    assert "Error interno: kaput" in job.error


def test_shutdown_does_not_requeue_a_cancelled_job(db_session, worker, fake):
    fake("hang")
    job = enqueue(db_session, spot(), Origin.BATCH)
    t = _start_running(db_session, worker, job)
    cancel_job(db_session, job.id)
    worker._stop.set()
    _join(t)
    db_session.refresh(job)
    assert job.status == JobStatus.CANCELLED


def test_finish_stopped_never_requeues_cancelled(db_session, worker):
    job = enqueue(db_session, spot(), Origin.BATCH)
    cancel_job(db_session, job.id)
    worker._finish_stopped(job.id, "preempted")
    db_session.refresh(job)
    assert job.status == JobStatus.CANCELLED


def test_cancel_finished_job_raises(db_session, worker, fake):
    job = enqueue(db_session, spot(), Origin.BATCH)
    worker.run_once()
    with pytest.raises(ValueError):
        cancel_job(db_session, job.id)


def test_bumped_priority_is_not_preempted(db_session, worker, fake):
    fake("hang")
    job = enqueue(db_session, spot(20), Origin.LIBRARY)
    t = _start_running(db_session, worker, job)
    enqueue(db_session, spot(20), Origin.SIMULATOR)  # same spot: bumps priority to 0
    enqueue(db_session, spot(21), Origin.SIMULATOR)
    time.sleep(0.3)  # several poll cycles (run_poll_s=0.02)
    db_session.refresh(job)
    assert job.priority == 0
    assert job.status == JobStatus.RUNNING
    cancel_job(db_session, job.id)
    _join(t)


def test_batch_does_not_preempt_library(db_session, worker, fake):
    fake("hang")
    job = enqueue(db_session, spot(20), Origin.LIBRARY)
    t = _start_running(db_session, worker, job)
    enqueue(db_session, spot(21), Origin.BATCH)
    time.sleep(0.3)
    db_session.refresh(job)
    assert job.status == JobStatus.RUNNING
    cancel_job(db_session, job.id)
    _join(t)


def test_no_preemption_while_paused(db_session, worker, fake):
    fake("hang")
    job = enqueue(db_session, spot(20), Origin.BATCH)
    t = _start_running(db_session, worker, job)
    set_paused(db_session, True)
    enqueue(db_session, spot(21), Origin.SIMULATOR)
    time.sleep(0.3)
    db_session.refresh(job)
    assert job.status == JobStatus.RUNNING
    cancel_job(db_session, job.id)
    _join(t)


def test_queue_position_none_when_missing(db_session):
    job = enqueue(db_session, spot(), Origin.BATCH)
    db_session.expunge(job)
    job.id = 12345  # stale id not present in the queue
    assert queue_position(db_session, job) is None
