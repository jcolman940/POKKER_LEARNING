from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.scenario import Street
from app.recommend.schemas import RecommendationOut


class PlayerEquityOut(BaseModel):
    equity: float
    win: float
    tie: float
    lose: float
    std_error: float


class EquityOut(BaseModel):
    hero: PlayerEquityOut
    villains: list[PlayerEquityOut]
    exact: bool
    samples: int


class OutsOut(BaseModel):
    available: bool
    currently_ahead: bool | None = None
    hero_share: float | None = None  # current showdown share vs the ranges (win + tie/2)
    cards: list[str] = []
    count: int = 0
    unseen: int = 0  # cards that can still come


class MetricsOut(BaseModel):
    pot_odds: float | None
    required_equity: float | None
    mdf: float | None
    spr: float | None


class RangeInfoOut(BaseModel):
    text: str
    combos: float  # weighted live combos after removing hero and board cards


class AnalysisOut(BaseModel):
    street: Street
    equity: EquityOut
    # Informative only: equity against the exact hands the user fixed for villains.
    equity_vs_hands: EquityOut | None = None
    outs: OutsOut
    metrics: MetricsOut
    ranges: list[RangeInfoOut]
    recommendation: RecommendationOut


class DealRequest(BaseModel):
    street: Street = Street.FLOP
    hero_hand: str = ""
    board: str = ""
    villain_hands: list[str | None] = []
    # Indexes of villains that should get a random exact hand.
    deal_villains: list[int] = []
    seed: int | None = Field(default=None, description="For reproducible deals")


class DealOut(BaseModel):
    hero_hand: str
    board: str
    villain_hands: list[str | None]
