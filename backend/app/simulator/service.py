from __future__ import annotations

import random

import pokercore

from app.config import get_settings
from app.domain.cards import DECK, draw, ensure_disjoint, format_cards, parse_cards
from app.domain.metrics import pot_metrics
from app.domain.scenario import BOARD_SIZE, Scenario
from app.simulator.schemas import (
    AnalysisOut,
    DealOut,
    DealRequest,
    EquityOut,
    MetricsOut,
    OutsOut,
    PlayerEquityOut,
    RangeInfoOut,
)


def _equity(players: list[str], board: str) -> EquityOut:
    settings = get_settings()
    result = pokercore.equity(
        players,
        board,
        iterations=settings.equity_iterations,
        exact_limit=settings.equity_exact_limit,
    )
    out = [
        PlayerEquityOut(equity=p.equity, win=p.win, tie=p.tie, lose=p.lose, std_error=p.std_error)
        for p in result.players
    ]
    return EquityOut(hero=out[0], villains=out[1:], exact=result.exact, samples=result.samples)


def _share(strength: pokercore.HandStrength) -> float:
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
            result.append(_share(s))
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


def analyze(scenario: Scenario) -> AnalysisOut:
    ranges = [v.range for v in scenario.villains]
    dead = scenario.hero_hand + scenario.board
    range_info = [
        RangeInfoOut(text=r, combos=sum(w for _, w in pokercore.range_combos(r, dead)))
        for r in ranges
    ]
    for i, info in enumerate(range_info, start=1):
        if info.combos == 0:
            raise ValueError(f"El rango del rival {i} queda vacío con las cartas conocidas")

    # Main numbers: always against the villains' ranges.
    equity = _equity([scenario.hero_hand, *ranges], scenario.board)

    equity_vs_hands = None
    if any(v.hand for v in scenario.villains):
        players = [scenario.hero_hand, *(v.hand or v.range for v in scenario.villains)]
        equity_vs_hands = _equity(players, scenario.board)

    metrics = pot_metrics(scenario.pot_bb, scenario.to_call_bb, scenario.effective_stack_bb)
    return AnalysisOut(
        street=scenario.street,
        equity=equity,
        equity_vs_hands=equity_vs_hands,
        outs=compute_outs(scenario.hero_hand, ranges, scenario.board),
        metrics=MetricsOut(**metrics.__dict__),
        ranges=range_info,
    )


def deal(request: DealRequest) -> DealOut:
    """Fills in random cards around whatever the user fixed."""
    rng = random.Random(request.seed)
    hero = parse_cards(request.hero_hand)
    board = parse_cards(request.board)
    villains = [parse_cards(h) for h in request.villain_hands]

    target = BOARD_SIZE[request.street]
    if len(hero) not in (0, 2):
        raise ValueError("La mano de Hero debe tener 0 o 2 cartas")
    if any(len(v) not in (0, 2) for v in villains):
        raise ValueError("Cada mano de rival debe tener 0 o 2 cartas")
    if len(board) > target:
        raise ValueError("El board fijado tiene más cartas que la calle pedida")
    for i in request.deal_villains:
        if i < 0:
            raise ValueError("Índice de rival inválido")
        while len(villains) <= i:
            villains.append([])
    ensure_disjoint(
        {"la mano de Hero": hero, "el board": board}
        | {f"la mano del rival {i + 1}": v for i, v in enumerate(villains)}
    )

    used = hero + board + [c for v in villains for c in v]
    if not hero:
        hero = draw(2, used, rng)
        used += hero
    for i in request.deal_villains:
        if not villains[i]:
            villains[i] = draw(2, used, rng)
            used += villains[i]
    board += draw(target - len(board), used, rng)

    return DealOut(
        hero_hand=format_cards(hero),
        board=format_cards(board),
        villain_hands=[format_cards(v) or None for v in villains],
    )
