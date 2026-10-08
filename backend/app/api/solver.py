from dataclasses import asdict
from datetime import datetime
from typing import Annotated

import pokercore
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.db.models import SolverJob
from app.domain.cards import parse_cards
from app.domain.scenario import GameFormat
from app.recommend.ranges_prefill import PotType, PrefillQuery, prefill_ranges
from app.recommend.schemas import StrategyLayerOut
from app.solver import queue as q
from app.solver.cache import cache_stats, clear_cache, delete_result, get_result
from app.solver.flops import representative_flops
from app.solver.install import Installer, detected_solver_path
from app.solver.library import (
    Family,
    LineSpec,
    build_line_spots,
    enqueue_line,
    library_status,
    load_library,
)
from app.solver.output_parser import canonical_combo
from app.solver.spot import SOLVER_VERSION
from app.solver.trees import load_presets
from app.solver.worker_registry import solver_available

router = APIRouter(prefix="/solver", tags=["solver"])
DbSession = Annotated[Session, Depends(get_session)]
NO_SOLVER_DETAIL = "Descargá TexasSolver en Solver → Configuración para resolver spots."


def _require_solver() -> None:
    if not solver_available():
        raise HTTPException(409, NO_SOLVER_DETAIL)


class JobOut(BaseModel):
    id: int
    label: str
    origin: str
    priority: int
    status: str
    iteration: int
    exploitability: float | None
    error: str | None
    position: int | None
    paused: bool
    spot_hash: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def _job_out(
    session: Session,
    job: SolverJob,
    positions: dict[int, int] | None = None,
    paused: bool | None = None,
) -> JobOut:
    return JobOut(
        id=job.id,
        label=job.label,
        origin=job.origin,
        priority=job.priority,
        status=job.status,
        iteration=job.iteration,
        exploitability=job.exploitability,
        error=job.error,
        position=q.queue_position(session, job, positions),
        paused=q.is_paused(session) if paused is None else paused,
        spot_hash=job.spot_hash,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _job(session: Session, job_id: int) -> SolverJob:
    job = session.get(SolverJob, job_id)
    if job is None:
        raise HTTPException(404, f"No existe el trabajo {job_id}")
    return job


@router.get("/status")
def status(session: DbSession) -> dict:
    s = get_settings()
    entries, size = cache_stats(session)
    detected = detected_solver_path(s)
    return {
        "configured": solver_available(),
        "version": SOLVER_VERSION,
        "path": str(detected) if detected else None,
        "threads": s.solver_threads,
        "paused": q.is_paused(session),
        "cache_entries": entries,
        "cache_bytes": size,
        "presets": [{"name": p.name, "label": p.label} for p in load_presets().values()],
    }


@router.post("/install", status_code=202)
def install_start() -> dict:
    return asdict(Installer.get().start())


@router.get("/install")
def install_status() -> dict:
    return asdict(Installer.get().status())


@router.get("/jobs", response_model=list[JobOut])
def jobs(session: DbSession, status: str | None = None) -> list[JobOut]:
    active_query = select(SolverJob).where(SolverJob.status.in_(q.ACTIVE))
    done_query = select(SolverJob).where(SolverJob.status.not_in(q.ACTIVE))
    if status is not None:
        active_query = active_query.where(SolverJob.status == status)
        done_query = done_query.where(SolverJob.status == status)
    # "running" sorts after "queued" alphabetically, so descending puts running first.
    active = session.scalars(
        active_query.order_by(SolverJob.status.desc(), SolverJob.priority, SolverJob.id)
    ).all()
    done = session.scalars(done_query.order_by(SolverJob.id.desc()).limit(50)).all()
    positions = q.queue_positions(session)
    paused = q.is_paused(session)
    return [_job_out(session, j, positions, paused) for j in [*active, *done]]


@router.get("/jobs/{job_id}", response_model=JobOut)
def job(job_id: int, session: DbSession) -> JobOut:
    return _job_out(session, _job(session, job_id))


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel(job_id: int, session: DbSession) -> JobOut:
    _job(session, job_id)
    return _job_out(session, q.cancel_job(session, job_id))


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
def retry(job_id: int, session: DbSession) -> JobOut:
    _job(session, job_id)
    return _job_out(session, q.retry_job(session, job_id))


@router.post("/queue/pause")
def pause(session: DbSession) -> dict:
    q.set_paused(session, True)
    return {"paused": True}


@router.post("/queue/resume")
def resume(session: DbSession) -> dict:
    q.set_paused(session, False)
    return {"paused": False}


@router.delete("/cache")
def delete_cache(session: DbSession) -> dict:
    return {"deleted": clear_cache(session)}


@router.delete("/cache/{spot_hash}", status_code=204)
def delete_cached(spot_hash: str, session: DbSession) -> Response:
    if not delete_result(session, spot_hash):
        raise HTTPException(404, "Ese resultado no está en la caché")
    return Response(status_code=204)


class PrefillIn(BaseModel):
    game_format: GameFormat
    players: int = Field(ge=2, le=10)
    aggressor: str
    caller: str
    pot_type: PotType
    stack_bb: float = Field(gt=0)
    ante_bb: float = Field(default=0.0, ge=0)


@router.post("/prefill-ranges")
def prefill(body: PrefillIn, session: DbSession) -> dict:
    result = prefill_ranges(session, PrefillQuery(**body.model_dump()))
    return {"aggressor": result.aggressor.__dict__, "caller": result.caller.__dict__}


class BatchLine(BaseModel):
    aggressor: str
    caller: str
    pot_type: PotType
    stack_bb: float = Field(gt=0)
    open_size_bb: float = Field(gt=0)
    threebet_size_bb: float | None = Field(default=None, gt=0)


class BatchIn(BaseModel):
    game_format: GameFormat
    players: int = Field(ge=2, le=10)
    ante_total_bb: float = Field(default=0.0, ge=0)
    preset: str = "chico"
    line: BatchLine
    flops: list[str] | None = None


@router.post("/batch")
def batch(body: BatchIn, session: DbSession) -> dict:
    line = LineSpec(id="batch", label="Lote", **body.line.model_dump())
    family = Family(
        id="batch",
        label="Lote",
        game_format=body.game_format,
        players=body.players,
        ante_total_bb=body.ante_total_bb,
        preset=body.preset,
        lines=[line],
    )
    flops = [f.replace(" ", "") for f in body.flops] if body.flops else None
    for f in flops or []:
        try:
            cards = parse_cards(f)
        except ValueError:
            cards = []
        if len(cards) != 3 or len(set(cards)) != 3:
            raise HTTPException(422, f"Flop inválido: {f} (3 cartas distintas, p. ej. AhKd2c)")
    _require_solver()
    missing = build_line_spots(session, family, line, flops or ["AhKd2c"]).missing
    enqueued = 0 if missing else enqueue_line(session, family, line, flops, q.Origin.BATCH)
    return {"enqueued": enqueued, "missing": missing}


@router.get("/library")
def library(session: DbSession) -> list[dict]:
    return library_status(session, load_library())


class LibraryEnqueueIn(BaseModel):
    family: str
    line: str | None = None


@router.post("/library/enqueue")
def library_enqueue(body: LibraryEnqueueIn, session: DbSession) -> dict:
    family = next((f for f in load_library() if f.id == body.family), None)
    if family is None:
        raise HTTPException(404, f"No existe la familia {body.family}")
    lines = [ln for ln in family.lines if body.line in (None, ln.id)]
    if not lines:
        raise HTTPException(404, f"No existe la línea {body.line}")
    _require_solver()
    enqueued, missing = 0, []
    for line in lines:
        built = build_line_spots(session, family, line, representative_flops()[:1])
        if built.missing:
            missing += [f"{line.label}: {m}" for m in built.missing]
            continue
        enqueued += enqueue_line(session, family, line)
    return {"enqueued": enqueued, "missing": missing}


class NodeActionOut(BaseModel):
    index: int
    kind: str
    label: str
    amount_bb: float | None
    frequency: float
    has_child: bool


class NodeOut(BaseModel):
    player: str
    path: str
    actions: list[NodeActionOut]
    layers: list[StrategyLayerOut]


@router.get("/results/{spot_hash}/node", response_model=NodeOut)
def node(spot_hash: str, session: DbSession, path: str = "") -> NodeOut:
    cached = get_result(session, spot_hash)
    if cached is None:
        raise HTTPException(404, "Ese resultado no está en la caché")
    current = cached.tree
    for step in filter(None, path.split(".")):
        child = current.children.get(int(step)) if step.isdigit() else None
        if child is None:
            raise HTTPException(404, "Ese nodo no existe en el árbol")
        current = child
    spot = cached.spot
    rng = spot.range_oop if current.player == "oop" else spot.range_ip
    weights = {canonical_combo(c): w for c, w in pokercore.range_combos(rng, "".join(spot.board))}
    mix = current.range_mix(weights)
    layers = current.class_layers(weights)
    return NodeOut(
        player=current.player,
        path=path,
        actions=[
            NodeActionOut(
                index=i,
                kind=a.kind,
                label=a.label(spot.pot_bb),
                amount_bb=a.amount_bb,
                frequency=mix[i],
                has_child=i in current.children,
            )
            for i, a in enumerate(current.actions)
        ],
        layers=[
            StrategyLayerOut(action=a.kind, label=a.label(spot.pot_bb), grid=g)
            for a, g in zip(current.actions, layers, strict=True)
        ],
    )
