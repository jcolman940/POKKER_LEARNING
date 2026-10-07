"""Outs against villain ranges."""

from __future__ import annotations

import pokercore

from app.domain.cards import DECK, parse_cards
from app.simulator.schemas import OutsOut


def showdown_share(strength: pokercore.HandStrength) -> float:
    return strength.win + strength.tie / 2


def compute_outs(hero: str, villain_ranges: list[str], board: str) -> OutsOut:
    """Outs against the villains' ranges (never their exact hands).

    The hero is "ahead" when its showdown share on the current board (win + tie/2)
    is at least 50% against every villain range. An out is an unseen card that
    takes a hero who is behind to ahead.
    """
    board_cards = parse_cards(board)
    if len(board_cards) not in (3, 4):
        return OutsOut(available=False)

    def shares(b: str) -> list[float] | None:
        result = []
        for r in villain_ranges:
            s = pokercore.hand_strength(hero, r, b)
            if s.combos == 0:
                return None
            result.append(showdown_share(s))
        return result

    current = shares(board)
    if current is None:
        return OutsOut(available=False)
    used = set(parse_cards(hero)) | set(board_cards)
    unseen = [c for c in DECK if c not in used]
    ahead = min(current) >= 0.5
    outs: list[str] = []
    if not ahead:
        for card in unseen:
            after = shares(board + card)
            if after is not None and min(after) >= 0.5:
                outs.append(card)
    return OutsOut(
        available=True,
        currently_ahead=ahead,
        hero_share=min(current),
        cards=outs,
        count=len(outs),
        unseen=len(unseen),
    )
