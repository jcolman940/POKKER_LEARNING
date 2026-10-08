from typing import Annotated

import pokercore
from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from app.domain.positions import MAX_PLAYERS, MIN_PLAYERS, preflop_order
from app.recommend.engine import solve_spot
from app.recommend.preflop_equity import combos_per_class

router = APIRouter(prefix="/pushfold", tags=["pushfold"])


class PushFoldIn(BaseModel):
    # Stacks in bb, in preflop order (UTG ... SB, BB). Table size = len(stacks).
    stacks_bb: list[Annotated[float, Field(gt=0)]] = Field(
        min_length=MIN_PLAYERS, max_length=MAX_PLAYERS
    )
    ante_bb: float = Field(default=0.0, ge=0)
    bb_ante_bb: float = Field(default=0.0, ge=0)
    payouts: list[Annotated[float, Field(ge=0)]] = []

    @model_validator(mode="after")
    def _payouts(self):
        if len(self.payouts) > len(self.stacks_bb):
            raise ValueError("Hay más premios que jugadores en la mesa")
        return self


class RangeOut(BaseModel):
    position: str
    vs_position: str | None = None
    share: float  # fraction of all hands
    grid: list[float]
    ev_diff: list[float]  # EV(action) - EV(fold) per class


class PushFoldOut(BaseModel):
    positions: list[str]
    unit: str
    push: list[RangeOut]
    call: list[RangeOut]
    icm_equity: list[float] | None
    iterations: int
    exploitability: float
    converged: bool


@router.post("/solve", response_model=PushFoldOut)
def solve(body: PushFoldIn) -> PushFoldOut:
    result = solve_spot(body.stacks_bb, body.ante_bb, body.bb_ante_bb, body.payouts)
    combos = combos_per_class()

    def out(position, vs, grid, ev):
        ev_act, ev_fold = ev
        return RangeOut(
            position=position,
            vs_position=vs,
            share=float(combos @ grid / 1326),
            grid=grid.tolist(),
            ev_diff=(ev_act - ev_fold).tolist(),
        )

    names = preflop_order(len(body.stacks_bb))
    return PushFoldOut(
        positions=names,
        unit=result.unit,
        push=[out(p, None, result.push[p], result.push_ev[p]) for p in names[:-1]],
        call=[
            out(caller, pusher, grid, result.call_ev[(pusher, caller)])
            for (pusher, caller), grid in result.call.items()
        ],
        icm_equity=pokercore.icm_equity(body.stacks_bb, body.payouts) if body.payouts else None,
        iterations=result.iterations,
        exploitability=result.exploitability,
        converged=result.converged,
    )
