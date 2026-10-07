"""The process-wide solver worker (started by the app lifespan when the solver exists)."""

from __future__ import annotations

from app.config import get_settings
from app.db.session import _session_factory
from app.solver.queue import SolverWorker

_worker: SolverWorker | None = None


def solver_available() -> bool:
    path = get_settings().solver_path
    return path is not None and path.is_file()


def start_worker() -> None:
    global _worker
    if _worker is not None or not solver_available():
        return
    s = get_settings()
    _worker = SolverWorker(
        _session_factory(),
        s.solver_path,
        s.data_dir,
        threads=s.solver_threads,
        timeout_s=s.solver_timeout_min * 60,
    )
    _worker.start()


def stop_worker() -> None:
    global _worker
    if _worker is not None:
        _worker.stop()
        _worker = None
