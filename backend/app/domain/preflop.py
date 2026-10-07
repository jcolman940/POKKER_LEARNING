"""Preflop situation of a player at a decision point (shared by replay and stats)."""

from __future__ import annotations

from app.domain.hand import AGGRESSIVE, Action, ActionType
from app.domain.scenario import Situation


def preflop_situation(
    positions: dict[str, str], hero: str, before: list[Action], folded: set[str]
) -> Situation:
    raises = [a for a in before if a.type in AGGRESSIVE]
    others = [a for a in raises if a.player != hero]
    hero_raised = any(a.player == hero for a in raises)
    pos = positions[hero]
    if raises and raises[-1].all_in and raises[-1].player != hero:
        return Situation.VS_ALLIN
    if not raises:
        active = [p for p in positions if p not in folded and p != hero]
        if pos in ("SB", "BB") and all(positions[p] in ("SB", "BB") for p in active):
            return Situation.BVB
        return Situation.RFI
    if len(raises) == 1:
        opener = raises[0]
        if pos == "BB" and positions.get(opener.player) == "SB":
            return Situation.BVB
        after = before[before.index(opener) + 1 :]
        if any(a.type == ActionType.CALL and a.player != hero for a in after):
            return Situation.SQUEEZE
        return Situation.VS_OPEN
    if len(raises) == 2 or (hero_raised and len(others) == 1):
        return Situation.VS_3BET
    return Situation.VS_4BET
