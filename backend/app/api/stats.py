from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.filters import stats_filter
from app.config import get_settings
from app.db import get_session
from app.stats.engine import (
    GraphPoint,
    GroupBy,
    StatsFilter,
    StatsGroup,
    TournamentStats,
    compute_stats,
    tournament_stats,
    winnings_graph,
)

router = APIRouter(prefix="/stats", tags=["stats"])
SessionDep = Annotated[Session, Depends(get_session)]
FilterDep = Annotated[StatsFilter, Depends(stats_filter)]


class StatsOut(BaseModel):
    min_sample: int
    groups: list[StatsGroup]


@router.get("", response_model=StatsOut)
def stats(session: SessionDep, filters: FilterDep, group_by: GroupBy = GroupBy.NONE) -> StatsOut:
    return StatsOut(
        min_sample=get_settings().stats_min_sample,
        groups=compute_stats(session, filters, group_by),
    )


@router.get("/graph", response_model=list[GraphPoint])
def graph(session: SessionDep, filters: FilterDep) -> list[GraphPoint]:
    return winnings_graph(session, filters)


@router.get("/tournaments", response_model=TournamentStats | None)
def tournaments(session: SessionDep, filters: FilterDep) -> TournamentStats | None:
    return tournament_stats(session, filters)
