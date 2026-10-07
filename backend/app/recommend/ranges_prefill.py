"""Postflop starting ranges taken from the user's preflop charts.

SRP:    aggressor = RFI "raise"      caller = vs_open "call"
3-bet:  aggressor = vs_open "3bet"   caller = vs_3bet "call"
The small blind's charts may be stored as blind-vs-blind, so it is tried as a fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy.orm import Session

from app.domain.scenario import GameFormat, Situation
from app.recommend.charts import ChartQuery, find_chart
from app.recommend.preflop_equity import grid_to_text


class PotType(StrEnum):
    SRP = "srp"
    THREE_BET = "3bet"


@dataclass(frozen=True)
class PrefillQuery:
    game_format: GameFormat
    players: int
    aggressor: str
    caller: str
    pot_type: PotType
    stack_bb: float
    ante_bb: float = 0.0


@dataclass
class PrefillRange:
    text: str | None
    approximate: bool = False
    notes: list[str] = field(default_factory=list)
    missing: str | None = None


@dataclass
class PrefillResult:
    aggressor: PrefillRange
    caller: PrefillRange


def _lookup(
    session: Session,
    q: PrefillQuery,
    position: str,
    vs: str | None,
    situations: list[Situation],
    action: str,
    label: str,
) -> PrefillRange:
    for situation in situations:
        match = find_chart(
            session,
            ChartQuery(
                game_format=q.game_format,
                players=q.players,
                position=position,
                situation=situation,
                stack_bb=q.stack_bb,
                vs_position=vs,
                ante_bb=q.ante_bb,
            ),
        )
        if match is None:
            continue
        values = match.chart.actions.get(action)
        if not values or max(values) <= 0:
            continue
        return PrefillRange(
            text=grid_to_text(values), approximate=not match.exact, notes=match.mismatches
        )
    return PrefillRange(text=None, missing=label)


def prefill_ranges(session: Session, q: PrefillQuery) -> PrefillResult:
    a, c = q.aggressor, q.caller
    if q.pot_type == PotType.SRP:
        opener_sits = [Situation.RFI, Situation.BVB] if a == "SB" else [Situation.RFI]
        caller_sits = [Situation.VS_OPEN, Situation.BVB] if a == "SB" else [Situation.VS_OPEN]
        return PrefillResult(
            aggressor=_lookup(session, q, a, None, opener_sits, "raise", f"{a} RFI"),
            caller=_lookup(session, q, c, a, caller_sits, "call", f"{c} vs open de {a}"),
        )
    return PrefillResult(
        aggressor=_lookup(session, q, a, c, [Situation.VS_OPEN], "3bet", f"{a} 3-bet vs {c}"),
        caller=_lookup(session, q, c, a, [Situation.VS_3BET], "call", f"{c} vs 3-bet de {a}"),
    )
