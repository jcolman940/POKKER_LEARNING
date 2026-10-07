import random
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import PayoutStructure
from app.recommend.schemas import RecommendationOut
from app.trainer import service
from app.trainer.selection import NoSpots

router = APIRouter(prefix="/trainer", tags=["trainer"])
SessionDep = Annotated[Session, Depends(get_session)]


def get_rng() -> random.Random:
    """Unseeded in production; tests override this dependency with a seeded generator."""
    return random.Random()


RngDep = Annotated[random.Random, Depends(get_rng)]


class SourceOut(BaseModel):
    available: bool
    reason: str | None = None


class SourcesOut(BaseModel):
    pushfold: SourceOut
    chart: SourceOut
    range: SourceOut


class PayoutIn(BaseModel):
    name: str
    payouts: list[float]


class PayoutOut(BaseModel):
    id: int
    name: str
    payouts: list[float]
    builtin: bool


class SessionIn(BaseModel):
    sources: list[Literal["pushfold", "chart", "range"]]
    formats: list[str] = []
    positions: list[str] = []
    situations: list[str] = []
    stack_buckets: list[str] = []
    table_sizes: list[int] = []
    mode: Literal["normal", "review", "frequent"] = "normal"
    difficulty: int = Field(default=50, ge=0, le=100)
    payout_id: int | None = None
    card_ids: list[int] | None = None


class SessionOut(BaseModel):
    id: int
    filters: dict


class SpotOut(BaseModel):
    spot_id: str
    kind: Literal["hand", "range"]
    source: str
    scenario: dict | None
    offered: list[str]
    title: str
    card_id: int | None
    review: bool


class AnswerIn(BaseModel):
    action: str | None = None
    painted: list[float] | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "AnswerIn":
        if (self.action is None) == (self.painted is None):
            raise ValueError("Respondé con una acción o con un rango pintado")
        return self


class LayerOut(BaseModel):
    action: str
    grid: list[float]


class RangeFeedbackOut(BaseModel):
    target: list[float]
    diff_grid: list[float]
    top_classes: list[dict]
    precision: float


class CardOut(BaseModel):
    interval_days: int
    due_at: str | None
    ease: float


class FeedbackOut(BaseModel):
    verdict: str
    loss: float
    loss_unit: str
    approximate: bool
    chosen: str | None
    best: str | None
    recommendation: RecommendationOut | None = None
    reference_layers: list[LayerOut] = []
    hand_index: int | None = None
    range: RangeFeedbackOut | None = None
    card: CardOut


class SummaryOut(BaseModel):
    spots: int
    correct: int
    acceptable: int
    error: int
    ev_loss_bb: float
    avg_freq_error: float | None
    avg_precision: float | None


class FrequentErrorOut(BaseModel):
    card_id: int
    key: str
    source: str
    label: str
    lapses: int
    reps: int


@router.get("/sources", response_model=SourcesOut)
def sources(session: SessionDep) -> dict:
    return service.source_status(session)


@router.get("/payouts", response_model=list[PayoutOut])
def payouts(session: SessionDep) -> list[PayoutStructure]:
    return list(session.scalars(select(PayoutStructure).order_by(PayoutStructure.id)))


@router.post("/payouts", response_model=PayoutOut, status_code=201)
def add_payout(body: PayoutIn, session: SessionDep) -> PayoutStructure:
    return service.create_payout(session, body.name, body.payouts)


@router.delete("/payouts/{payout_id}", status_code=204)
def remove_payout(payout_id: int, session: SessionDep) -> None:
    if not service.delete_payout(session, payout_id):
        raise HTTPException(status_code=404, detail="La estructura no existe")


@router.post("/sessions", response_model=SessionOut, status_code=201)
def new_session(body: SessionIn, session: SessionDep) -> SessionOut:
    ts = service.create_session(session, body.model_dump())
    return SessionOut(id=ts.id, filters=ts.filters)


@router.post("/sessions/{session_id}/next", response_model=SpotOut)
def next_spot(session_id: int, session: SessionDep, rng: RngDep) -> SpotOut:
    try:
        attempt, served = service.next_spot(session, session_id, rng)
    except service.SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoSpots as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SpotOut(
        spot_id=attempt.spot_id,
        kind=served.kind,  # type: ignore[arg-type]
        source=served.source,
        scenario=served.scenario.model_dump(mode="json") if served.scenario else None,
        offered=served.offered,
        title=served.title,
        card_id=attempt.card_id,
        review=served.review,
    )


@router.post("/spots/{spot_id}/answer", response_model=FeedbackOut)
def answer(spot_id: str, body: AnswerIn, session: SessionDep, rng: RngDep) -> dict:
    try:
        return service.answer_spot(session, spot_id, body.model_dump(exclude_none=True), rng)
    except service.SpotNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}", response_model=SummaryOut)
def summary(session_id: int, session: SessionDep) -> dict:
    try:
        return service.session_summary(session, session_id)
    except service.SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/frequent-errors", response_model=list[FrequentErrorOut])
def frequent_errors(session: SessionDep, limit: int = 10) -> list[dict]:
    return service.frequent_errors(session, max(1, min(limit, 100)))
