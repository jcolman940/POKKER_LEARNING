from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ActionOut(BaseModel):
    action: str  # fold / call / raise / 3bet / allin ...
    frequency: float
    ev: float | None = None
    label: str | None = None  # e.g. "Bet 75% (6bb)" when an action has several sizes
    amount_bb: float | None = None


class PendingJobOut(BaseModel):
    id: int
    status: str
    iteration: int
    exploitability: float | None
    position: int | None  # place in the queue (1 = next), None when running


class StrategyLayerOut(BaseModel):
    action: str
    label: str
    grid: list[float]  # 169 classes, range weight x frequency


class RecommendationOut(BaseModel):
    """Common output of every recommendation source (spec 6.4)."""

    available: bool = False
    message: str | None = None
    source: Literal["chart", "nash", "solver", "heuristic"] | None = None
    confidence: Literal["exact", "approximate"] | None = None
    hand_class: str | None = None
    actions: list[ActionOut] = []
    ev_unit: str | None = None  # "bb" or "$"
    reference: str | None = None  # where the numbers come from
    explanation: list[str] = []
    warnings: list[str] = []
    pending_job: PendingJobOut | None = None
    strategy_grid: list[StrategyLayerOut] = []
