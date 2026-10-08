"""Persistent solve queue (SQLite) and the single background worker.

One solve runs at a time (the solver already uses every core). A simulator request
preempts a running batch/library job, which goes back to the queue.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import AppMeta, SolverJob, SolverResult
from app.solver.cache import store_result
from app.solver.config_gen import generate_config
from app.solver.output_parser import parse_output
from app.solver.runner import Progress, SolverError, SolverStopped, kill_tree, run_solver
from app.solver.spot import SolverSpot

log = logging.getLogger(__name__)

PAUSED_KEY = "solver_queue_paused"
KEEP_FAILED_DIRS = 5


class Origin(StrEnum):
    SIMULATOR = "simulator"
    BATCH = "batch"
    LIBRARY = "library"


PRIORITY = {Origin.SIMULATOR: 0, Origin.BATCH: 10, Origin.LIBRARY: 20}


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE = {JobStatus.QUEUED, JobStatus.RUNNING}


def _now() -> datetime:
    return datetime.now(UTC)


def enqueue(
    session: Session, spot: SolverSpot, origin: Origin, library_key: str | None = None
) -> SolverJob:
    spot_hash = spot.spot_hash()
    priority = PRIORITY[origin]
    active = session.scalars(
        select(SolverJob).where(SolverJob.spot_hash == spot_hash, SolverJob.status.in_(ACTIVE))
    ).first()
    if active is not None:
        if priority < active.priority:
            active.priority = priority
            session.commit()
        return active
    cached = session.get(SolverResult, spot_hash) is not None
    job = SolverJob(
        spot_hash=spot_hash,
        spot=spot.to_json(),
        label=spot.label(),
        origin=origin,
        priority=priority,
        status=JobStatus.DONE if cached else JobStatus.QUEUED,
        iteration=0,
        library_key=library_key,
        finished_at=_now() if cached else None,
    )
    session.add(job)
    session.commit()
    return job


def _queued(session: Session):
    return (
        select(SolverJob)
        .where(SolverJob.status == JobStatus.QUEUED)
        .order_by(SolverJob.priority, SolverJob.id)
    )


def next_job(session: Session) -> SolverJob | None:
    return session.scalars(_queued(session).limit(1)).first()


def queue_positions(session: Session) -> dict[int, int]:
    """Queue place (1 = next) of every queued job, in one query."""
    ids = session.scalars(_queued(session).with_only_columns(SolverJob.id))
    return {job_id: i for i, job_id in enumerate(ids, start=1)}


def queue_position(
    session: Session, job: SolverJob, positions: dict[int, int] | None = None
) -> int | None:
    if job.status != JobStatus.QUEUED:
        return None
    if positions is None:
        positions = queue_positions(session)
    return positions.get(job.id)


def _get(session: Session, job_id: int) -> SolverJob:
    job = session.get(SolverJob, job_id)
    if job is None:
        raise ValueError(f"No existe el trabajo {job_id}")
    return job


def cancel_job(session: Session, job_id: int) -> SolverJob:
    job = _get(session, job_id)
    # Conditional: the worker may finish the job between the read and the write.
    changed = session.execute(
        update(SolverJob)
        .where(SolverJob.id == job_id, SolverJob.status.in_(ACTIVE))
        .values(status=JobStatus.CANCELLED, finished_at=_now())  # a running worker sees this
    ).rowcount
    session.commit()
    session.refresh(job)
    if not changed:
        raise ValueError("Solo se puede cancelar un trabajo en cola o corriendo")
    return job


def retry_job(session: Session, job_id: int) -> SolverJob:
    job = _get(session, job_id)
    if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
        raise ValueError("Solo se puede reintentar un trabajo fallido o cancelado")
    job.status = JobStatus.QUEUED
    job.error = None
    job.iteration = 0
    job.exploitability = None
    job.finished_at = None
    session.commit()
    return job


def _is_solver_process(pid: int) -> bool:
    """True only if `pid` is alive AND is a TexasSolver process (PIDs get reused).

    Never use os.kill(pid, 0) for this on Windows: there it calls TerminateProcess.
    """
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.lower()
        except (OSError, subprocess.TimeoutExpired):
            return False
        return "console_solver" in out
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").lower()
    except OSError:
        return False
    return "console_solver" in cmdline


def recover_jobs(session: Session) -> int:
    """Startup: jobs left running by a previous backend go back to the queue."""
    jobs = session.scalars(select(SolverJob).where(SolverJob.status == JobStatus.RUNNING)).all()
    for job in jobs:
        if job.pid and _is_solver_process(job.pid):
            kill_tree(job.pid)
        job.status = JobStatus.QUEUED
        job.pid = None
        job.started_at = None
    session.commit()
    return len(jobs)


def is_paused(session: Session) -> bool:
    meta = session.get(AppMeta, PAUSED_KEY)
    return meta is not None and meta.value == "1"


def set_paused(session: Session, paused: bool) -> None:
    session.merge(AppMeta(key=PAUSED_KEY, value="1" if paused else "0"))
    session.commit()


class SolverWorker:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        solver_path: Path,
        data_dir: Path,
        *,
        threads: int,
        timeout_s: float,
        poll_s: float = 1.0,
        run_poll_s: float = 0.5,
    ):
        self._sessions = session_factory
        self._solver_path = solver_path
        self._jobs_dir = data_dir / "solver" / "jobs"
        self._threads = threads
        self._timeout_s = timeout_s
        self._poll_s = poll_s
        self._run_poll_s = run_poll_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        with self._sessions() as session:
            recover_jobs(session)
        self._thread = threading.Thread(target=self._loop, name="solver-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                worked = self.run_once()
            except Exception:  # keep the worker alive; the job itself records errors
                log.exception("solver worker iteration failed")
                worked = False
            if not worked:
                self._stop.wait(self._poll_s)

    def run_once(self) -> bool:
        with self._sessions() as session:
            if is_paused(session):
                return False
            job = next_job(session)
            if job is None:
                return False
            job_id = job.id
            # Conditional: a cancel may land between next_job() and this write.
            changed = session.execute(
                update(SolverJob)
                .where(SolverJob.id == job_id, SolverJob.status == JobStatus.QUEUED)
                .values(status=JobStatus.RUNNING, started_at=_now(), iteration=0)
            ).rowcount
            session.commit()
            if not changed:
                return True  # skip it; the loop picks the next job
        try:
            self._execute(job_id)
        except Exception as e:  # never leave a job RUNNING
            log.exception("solver job %s failed unexpectedly", job_id)
            try:
                self._finish(job_id, JobStatus.FAILED, error=f"Error interno: {e}")
                self._prune_failed()
            except Exception:
                log.exception("could not mark solver job %s as failed", job_id)
        return True

    def _execute(self, job_id: int) -> None:
        with self._sessions() as session:
            job = _get(session, job_id)
            spot = SolverSpot.from_json(job.spot)
            library_key = job.library_key

        workdir = self._jobs_dir / str(job_id)
        started = time.monotonic()
        try:
            raw, progress = run_solver(
                generate_config(spot, self._threads),
                workdir,
                self._solver_path,
                timeout_s=self._timeout_s,
                on_start=lambda pid: self._update(job_id, pid=pid),
                on_progress=lambda p: self._update(
                    job_id, iteration=p.iteration, exploitability=p.exploitability
                ),
                should_stop=lambda: self._should_stop(job_id),
                poll_s=self._run_poll_s,
            )
            tree = parse_output(raw, spot.stack_bb)
        except SolverStopped as stop:
            self._finish_stopped(job_id, stop.reason)
            shutil.rmtree(workdir, ignore_errors=True)
            return
        except (SolverError, ValueError) as e:
            self._finish(job_id, JobStatus.FAILED, error=str(e))
            self._prune_failed()
            return

        with self._sessions() as session:
            store_result(session, spot, tree, progress, time.monotonic() - started, library_key)
        # The result exists, so DONE wins even over a cancel that arrived meanwhile.
        self._finish(job_id, JobStatus.DONE, progress=progress)
        shutil.rmtree(workdir, ignore_errors=True)

    def _update(self, job_id: int, **fields) -> None:
        with self._sessions() as session:
            session.execute(update(SolverJob).where(SolverJob.id == job_id).values(**fields))
            session.commit()

    def _should_stop(self, job_id: int) -> str | None:
        with self._sessions() as session:
            job = session.get(SolverJob, job_id)
            if job is None or job.status == JobStatus.CANCELLED:
                return "cancelled"
            if self._stop.is_set():
                return "shutdown"
            # Only a queued simulator job (priority 0) preempts, and never a simulator job.
            # Uses the job's current priority (an enqueue may have bumped it).
            if job.priority > 0 and not is_paused(session):
                urgent = session.scalars(
                    _queued(session).where(SolverJob.priority == 0).limit(1)
                ).first()
                if urgent is not None:
                    return "preempted"
        return None

    def _finish_stopped(self, job_id: int, reason: str) -> None:
        if reason in ("preempted", "shutdown"):
            values = {"pid": None, "status": JobStatus.QUEUED, "started_at": None}
            allowed = [JobStatus.RUNNING]  # never requeue a cancelled job
        else:
            values = {"pid": None}
            allowed = [JobStatus.RUNNING, JobStatus.CANCELLED]
        with self._sessions() as session:
            session.execute(
                update(SolverJob)
                .where(SolverJob.id == job_id, SolverJob.status.in_(allowed))
                .values(**values)
            )
            session.commit()

    def _finish(
        self,
        job_id: int,
        status: JobStatus,
        *,
        error: str | None = None,
        progress: Progress | None = None,
    ) -> None:
        values: dict = {"status": status, "error": error, "pid": None, "finished_at": _now()}
        if progress:
            values["iteration"] = progress.iteration
            values["exploitability"] = progress.exploitability
        allowed = [JobStatus.RUNNING]
        if status == JobStatus.DONE:
            allowed.append(JobStatus.CANCELLED)
        with self._sessions() as session:
            session.execute(
                update(SolverJob)
                .where(SolverJob.id == job_id, SolverJob.status.in_(allowed))
                .values(**values)
            )
            session.commit()

    def _prune_failed(self) -> None:
        if not self._jobs_dir.exists():
            return
        dirs = sorted(
            (d for d in self._jobs_dir.iterdir() if d.is_dir()),
            key=lambda d: d.stat().st_mtime,
        )
        for d in dirs[:-KEEP_FAILED_DIRS]:
            shutil.rmtree(d, ignore_errors=True)
