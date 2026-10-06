from fastapi import APIRouter

from app.domain.positions import position_names
from app.domain.scenario import Scenario
from app.simulator import service
from app.simulator.schemas import AnalysisOut, DealOut, DealRequest

router = APIRouter(prefix="/simulator", tags=["simulator"])


@router.post("/analyze", response_model=AnalysisOut)
def analyze(scenario: Scenario) -> AnalysisOut:
    return service.analyze(scenario)


@router.post("/deal", response_model=DealOut)
def deal(request: DealRequest) -> DealOut:
    return service.deal(request)


@router.get("/positions/{num_players}", response_model=list[str])
def positions(num_players: int) -> list[str]:
    return position_names(num_players)
