"""Per-hand facts about the hero, computed from a HandRecord.

Each flag is 0/1 (or a small count) so the stats engine can aggregate them with
plain SQL sums. Definitions follow the usual tracker conventions:

- VPIP: hero voluntarily put chips in preflop (call / bet / raise; posts do not count).
- PFR: hero raised preflop.
- 3-bet: opportunity when hero acts preflop facing exactly one raise by someone else.
- Fold to 3-bet: hero made the first raise and faces a re-raise.
- C-bet flop: hero was the last preflop raiser, saw the flop and nobody bet before
  hero's first flop action. C-bet turn: hero c-bet the flop and nobody bet before
  hero's first turn action.
- Fold to c-bet (flop): the last preflop raiser (not hero) made the first flop bet
  and hero faces that single bet.
- WTSD: saw the flop and reached showdown. W$SD: won chips at showdown.
- Aggression (postflop): bets + raises, calls and folds.
- All-in EV adjusted: when chips go all-in before the river and every remaining
  hand is known, the net result is replaced by its expectation (equity x pot,
  layer by layer for side pots, with the same rake share as the real pot).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pokercore

from app.domain.hand import AGGRESSIVE, POSTS, VOLUNTARY, ActionType, HandRecord
from app.domain.scenario import Street
from app.recommend.preflop_equity import hand_class

STREET_ORDER = [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER]


@dataclass
class HeroFacts:
    position: str
    table_size: int
    stack_bb: float  # effective stack at the start of the hand, in bb
    hand_class: str | None
    net_chips: float
    net_bb: float
    allin_adj_bb: float  # equals net_bb when the hand had no all-in adjustment
    allin_adjusted: int
    showdown_bb: float  # net won at showdown (0 otherwise)
    non_showdown_bb: float  # net won without showdown (0 otherwise)
    vpip: int = 0
    pfr: int = 0
    threebet_opp: int = 0
    threebet: int = 0
    fold3b_opp: int = 0
    fold3b: int = 0
    cbet_flop_opp: int = 0
    cbet_flop: int = 0
    cbet_turn_opp: int = 0
    cbet_turn: int = 0
    fold_cbet_opp: int = 0
    fold_cbet: int = 0
    saw_flop: int = 0
    wtsd: int = 0
    wsd: int = 0
    agg_bets: int = 0
    agg_calls: int = 0
    agg_folds: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def _street_actions(record: HandRecord, street: Street):
    return [a for a in record.actions if a.street == street and a.type not in POSTS]


def _preflop(record: HandRecord, hero: str, f: HeroFacts) -> str | None:
    """Fills preflop flags and returns the last preflop raiser."""
    raises = 0
    first_raiser = None
    last_raiser = None
    threebet_seen = False
    fold3b_seen = False
    for a in _street_actions(record, Street.PREFLOP):
        if a.type == ActionType.RETURN:
            continue
        if a.player == hero:
            if a.type in VOLUNTARY:
                f.vpip = 1
            if a.type in AGGRESSIVE:
                f.pfr = 1
            if not threebet_seen and raises == 1 and last_raiser != hero:
                threebet_seen = True
                f.threebet_opp = 1
                f.threebet = int(a.type in AGGRESSIVE)
            if not fold3b_seen and first_raiser == hero and raises == 2 and last_raiser != hero:
                fold3b_seen = True
                f.fold3b_opp = 1
                f.fold3b = int(a.type == ActionType.FOLD)
        if a.type in AGGRESSIVE:
            raises += 1
            first_raiser = first_raiser or a.player
            last_raiser = a.player
    return last_raiser


def _first_action_unopened(record: HandRecord, street: Street, hero: str):
    """Hero's first action on a street and whether nobody bet before it."""
    bet_before = False
    for a in _street_actions(record, street):
        if a.player == hero and a.type != ActionType.RETURN:
            return a, not bet_before
        if a.type in AGGRESSIVE:
            bet_before = True
    return None, False


def _postflop(record: HandRecord, hero: str, aggressor: str | None, f: HeroFacts) -> None:
    folded_preflop = any(
        a.player == hero and a.type == ActionType.FOLD
        for a in _street_actions(record, Street.PREFLOP)
    )
    f.saw_flop = int(not folded_preflop and len(record.board) >= 6)
    if not f.saw_flop:
        return

    if aggressor == hero:
        first, unopened = _first_action_unopened(record, Street.FLOP, hero)
        if first is not None and unopened:
            f.cbet_flop_opp = 1
            f.cbet_flop = int(first.type in AGGRESSIVE)
        if f.cbet_flop and len(record.board) >= 8:
            first, unopened = _first_action_unopened(record, Street.TURN, hero)
            if first is not None and unopened:
                f.cbet_turn_opp = 1
                f.cbet_turn = int(first.type in AGGRESSIVE)
    elif aggressor is not None:
        bets = 0
        cbet = False
        for a in _street_actions(record, Street.FLOP):
            if a.type == ActionType.RETURN:
                continue
            if a.player == hero:
                if cbet and bets == 1:  # hero faces the aggressor's c-bet
                    f.fold_cbet_opp = 1
                    f.fold_cbet = int(a.type == ActionType.FOLD)
                    break
                if a.type in AGGRESSIVE:  # hero led the flop: no c-bet to face
                    break
                continue  # hero checked first
            if a.type in AGGRESSIVE:
                bets += 1
                cbet = bets == 1 and a.player == aggressor

    for a in record.actions:
        if a.player != hero or a.street == Street.PREFLOP:
            continue
        if a.type in AGGRESSIVE:
            f.agg_bets += 1
        elif a.type == ActionType.CALL:
            f.agg_calls += 1
        elif a.type == ActionType.FOLD:
            f.agg_folds += 1

    if hero in record.went_to_showdown():
        f.wtsd = 1
        f.wsd = int(record.collected.get(hero, 0.0) > 0)


def allin_adjusted_net(record: HandRecord, hero: str) -> float | None:
    """Expected net (chips) for an all-in before the river with every hand known."""
    voluntary = [a for a in record.actions if a.type not in POSTS and a.type != ActionType.RETURN]
    if not voluntary or len(record.board) != 10:
        return None
    street = voluntary[-1].street
    if street == Street.RIVER:
        return None
    alive = [s.name for s in record.dealt_seats if s.name not in record.folded()]
    if hero not in alive or len(alive) < 2:
        return None
    if not any(a.all_in for a in record.actions if a.player in alive):
        return None
    cards = {
        p: record.shown.get(p) or (record.hero_cards if p == record.hero else None) for p in alive
    }
    if any(not c for c in cards.values()):
        return None

    board = record.board_at(street)
    contrib = record.contributions()
    levels = sorted({contrib[p] for p in alive})
    expected = 0.0
    previous = 0.0
    for level in levels:
        amount = sum(min(c, level) - min(c, previous) for c in contrib.values())
        eligible = [p for p in alive if contrib[p] >= level]
        previous = level
        if amount <= 0 or hero not in eligible:
            continue
        if len(eligible) == 1:
            expected += amount
            continue
        players = [hero, *(p for p in eligible if p != hero)]
        result = pokercore.equity([cards[p] for p in players], board)
        expected += result.players[0].equity * amount

    total_in = sum(contrib.values())
    paid_out = sum(record.collected.values())
    rake_share = paid_out / total_in if total_in > 0 else 1.0
    return expected * rake_share - contrib[hero]


def hero_facts(record: HandRecord) -> HeroFacts | None:
    hero = record.hero
    if hero is None or hero not in record.positions():
        return None
    bb = record.bb
    hero_stack = record.stack_of(hero)
    others = [s.stack for s in record.dealt_seats if s.name != hero]
    effective = min(hero_stack, max(others)) if others else hero_stack
    net = record.net(hero)
    showdown = hero in record.went_to_showdown()
    adjusted = allin_adjusted_net(record, hero)

    f = HeroFacts(
        position=record.positions()[hero],
        table_size=record.table_size,
        stack_bb=effective / bb,
        hand_class=hand_class(record.hero_cards) if record.hero_cards else None,
        net_chips=net,
        net_bb=net / bb,
        allin_adj_bb=(adjusted if adjusted is not None else net) / bb,
        allin_adjusted=int(adjusted is not None),
        showdown_bb=net / bb if showdown else 0.0,
        non_showdown_bb=0.0 if showdown else net / bb,
    )
    aggressor = _preflop(record, hero, f)
    _postflop(record, hero, aggressor, f)
    return f
