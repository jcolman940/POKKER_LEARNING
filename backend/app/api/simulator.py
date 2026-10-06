from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.positions import position_names
from app.domain.scenario import Scenario
from app.simulator import service
from app.simulator.schemas import AnalysisOut, DealOut, DealRequest

router = APIRouter(prefix="/simulator", tags=["simulator"])


@router.post("/analyze", response_model=AnalysisOut)
def analyze(scenario: Scenario, session: Annotated[Session, Depends(get_session)]) -> AnalysisOut:
    return service.analyze(scenario, session)


@router.post("/deal", response_model=DealOut)
def deal(request: DealRequest) -> DealOut:
    return service.deal(request)


@router.get("/positions/{num_players}", response_model=list[str])
def positions(num_players: int) -> list[str]:
    return position_names(num_players)
