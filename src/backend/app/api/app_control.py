"""Packaged-app control endpoints (launcher heartbeat, shutdown, status)."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.db.models import SolverJob
from app.packaged import request_shutdown
from app.solver import worker_registry
from app.solver.queue import is_paused

router = APIRouter(prefix="/app", tags=["app"])


class AppStatus(BaseModel):
    packaged: bool
    heartbeat_age_s: float | None
    solver_busy: bool
    solver_pending: int


def solver_activity(session: Session) -> tuple[bool, int]:
    """(a job is running, queued jobs waiting while the queue is not paused).

    Without a running worker (no solver installed) nothing can ever run: report no work, so
    the watchdog does not keep the server alive for jobs that will never start.
    """
    if not worker_registry.worker_running():
        return False, 0
    running = session.scalar(
        select(func.count()).select_from(SolverJob).where(SolverJob.status == "running")
    )
    pending = 0
    if not is_paused(session):
        pending = session.scalar(
            select(func.count()).select_from(SolverJob).where(SolverJob.status == "queued")
        )
    return bool(running), int(pending or 0)


@router.post("/ping", status_code=204)
def ping(request: Request) -> Response:
    request.app.state.heartbeat.beat()
    return Response(status_code=204)


@router.post("/shutdown", status_code=202)
def shutdown(
    settings: Annotated[Settings, Depends(get_settings)],
    x_pokker_token: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    expected = settings.launch_token or ""
    if not x_pokker_token or not secrets.compare_digest(x_pokker_token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Token inválido")
    request_shutdown()
    return {"accepted": True}


@router.get("/status", response_model=AppStatus)
def status(request: Request, session: Annotated[Session, Depends(get_session)]) -> AppStatus:
    busy, pending = solver_activity(session)
    return AppStatus(
        packaged=True,
        heartbeat_age_s=request.app.state.heartbeat.age(),
        solver_busy=busy,
        solver_pending=pending,
    )
