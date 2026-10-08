from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.filters import stats_filter
from app.db import get_session
from app.db.models import Hand, ImportBatch
from app.domain.hand import HandRecord
from app.parsers import registered_parsers
from app.parsers.importer import import_files
from app.replay.service import Replay, build_replay
from app.stats.engine import StatsFilter

router = APIRouter(tags=["hands"])
SessionDep = Annotated[Session, Depends(get_session)]
FilterDep = Annotated[StatsFilter, Depends(stats_filter)]
MAX_UPLOAD_BYTES = 200 * 1024 * 1024


class ParserOut(BaseModel):
    site: str
    label: str


@router.get("/parsers", response_model=list[ParserOut])
def parsers() -> list[ParserOut]:
    return [ParserOut(site=p.site, label=p.label) for p in registered_parsers()]


class ImportOut(BaseModel):
    id: int
    created_at: datetime
    report: dict


@router.post("/imports", response_model=ImportOut)
async def upload(files: list[UploadFile], session: SessionDep) -> ImportOut:
    if not files:
        raise HTTPException(status_code=422, detail="No se recibieron archivos")
    payload = []
    total = 0
    for f in files:
        data = await f.read()
        total += len(data)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Los archivos superan los 200 MB")
        payload.append((f.filename or "archivo", data))
    batch, _ = import_files(session, payload)
    return ImportOut(id=batch.id, created_at=batch.created_at, report=batch.report)


@router.get("/imports", response_model=list[ImportOut])
def imports(session: SessionDep) -> list[ImportOut]:
    batches = session.scalars(select(ImportBatch).order_by(ImportBatch.id.desc()).limit(50))
    return [ImportOut(id=b.id, created_at=b.created_at, report=b.report) for b in batches]


class HandSummary(BaseModel):
    id: int
    site: str
    hand_id: str
    played_at: datetime
    game_type: str
    table_size: int
    position: str | None
    hero_cards: str | None
    stack_bb: float
    net_bb: float
    allin_adj_bb: float
    showdown: bool


class HandPage(BaseModel):
    total: int
    items: list[HandSummary]


@router.get("/hands", response_model=HandPage)
def list_hands(
    session: SessionDep, filters: FilterDep, limit: int = 50, offset: int = 0
) -> HandPage:
    limit = max(1, min(limit, 500))
    base = filters.apply(select(Hand))
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.scalars(
        base.order_by(Hand.played_at.desc(), Hand.id.desc()).limit(limit).offset(offset)
    )
    return HandPage(
        total=total,
        items=[
            HandSummary(
                id=h.id,
                site=h.site,
                hand_id=h.hand_id,
                played_at=h.played_at,
                game_type=h.game_type,
                table_size=h.table_size,
                position=h.position,
                hero_cards=h.hero_cards,
                stack_bb=h.stack_bb,
                net_bb=h.net_bb,
                allin_adj_bb=h.allin_adj_bb,
                showdown=bool(h.wtsd) or bool(h.allin_adjusted),
            )
            for h in rows
        ],
    )


def _get_hand(session: Session, hand_id: int) -> Hand:
    hand = session.get(Hand, hand_id)
    if hand is None:
        raise HTTPException(status_code=404, detail="Mano no encontrada")
    return hand


class HandDetail(BaseModel):
    id: int
    record: dict
    raw_text: str


@router.get("/hands/{hand_id}", response_model=HandDetail)
def get_hand(hand_id: int, session: SessionDep) -> HandDetail:
    hand = _get_hand(session, hand_id)
    return HandDetail(id=hand.id, record=hand.record, raw_text=hand.raw_text)


class ReplayIn(BaseModel):
    ranges: dict[str, str] = {}


@router.post("/hands/{hand_id}/replay", response_model=Replay)
def replay(hand_id: int, body: ReplayIn, session: SessionDep) -> Replay:
    hand = _get_hand(session, hand_id)
    return build_replay(HandRecord.model_validate(hand.record), body.ranges)
