"""Builds a step-by-step replay of a stored hand.

Hero's equity at each point is computed against the ranges assigned to the
opponents still in the hand (default: any two cards), never against the cards
they showed. Hero decision points carry a ready-made simulator Scenario for the
"Analizar este spot" button.
"""

from __future__ import annotations

from functools import lru_cache

import pokercore
from pydantic import BaseModel

from app.domain.hand import AGGRESSIVE, POSTS, Action, ActionType, HandRecord
from app.domain.preflop import preflop_situation
from app.domain.scenario import TOURNAMENT_FORMATS, Street

STREET_LABEL = {
    Street.PREFLOP: "Preflop",
    Street.FLOP: "Flop",
    Street.TURN: "Turn",
    Street.RIVER: "River",
}
BOARD_SIZE = {Street.PREFLOP: 0, Street.FLOP: 3, Street.TURN: 4, Street.RIVER: 5}
STREETS = [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER]
REPLAY_ITERATIONS = 30_000


class ReplayPlayer(BaseModel):
    name: str
    seat: int
    position: str
    stack_bb: float
    is_hero: bool
    cards: str | None  # hero's cards, or cards shown at showdown


class HeroEquity(BaseModel):
    equity: float
    std_error: float
    exact: bool


class ReplayStep(BaseModel):
    index: int
    street: Street
    description: str
    actor: str | None = None
    board: str
    pot_bb: float
    stacks_bb: dict[str, float]
    bets_bb: dict[str, float]
    folded: list[str]
    hero_equity: HeroEquity | None = None
    # Present when the next action is the hero's: the spot as a simulator scenario.
    scenario: dict | None = None


class Replay(BaseModel):
    site: str
    hand_id: str
    game_type: str
    bb: float
    players: list[ReplayPlayer]
    ranges: dict[str, str]
    steps: list[ReplayStep]
    result: dict[str, float]  # net bb per player


@lru_cache(maxsize=2048)
def _equity(hero_cards: str, ranges: tuple[str, ...], board: str) -> HeroEquity:
    r = pokercore.equity(
        [hero_cards, *ranges], board, iterations=REPLAY_ITERATIONS, exact_limit=3e6, seed=1
    )
    p = r.players[0]
    return HeroEquity(equity=p.equity, std_error=p.std_error, exact=r.exact)


class _State:
    def __init__(self, record: HandRecord):
        self.r = record
        self.bb = record.bb
        self.pos = record.positions()
        self.stacks = {s.name: s.stack for s in record.dealt_seats}
        self.bets = {name: 0.0 for name in self.stacks}
        self.pot = 0.0
        self.folded: list[str] = []
        self.street = Street.PREFLOP
        self.board = ""
        self.applied: list[Action] = []

    def apply(self, a: Action) -> None:
        self.applied.append(a)
        if a.type == ActionType.RETURN:
            self.stacks[a.player] += a.amount
            self.bets[a.player] -= a.amount
            self.pot -= a.amount
            return
        self.stacks[a.player] -= a.amount
        self.pot += a.amount
        if a.type != ActionType.POST_ANTE:
            self.bets[a.player] += a.amount
        if a.type == ActionType.FOLD:
            self.folded.append(a.player)

    def new_street(self, street: Street) -> None:
        self.street = street
        self.board = self.r.board[: BOARD_SIZE[street] * 2]
        self.bets = {name: 0.0 for name in self.bets}

    def label(self, player: str) -> str:
        return f"{self.pos.get(player, '?')} ({player})"

    def describe(self, a: Action) -> str:
        who = self.label(a.player)
        amount = a.amount / self.bb
        total = self.bets[a.player] / self.bb
        tail = " (all-in)" if a.all_in else ""
        text = {
            ActionType.FOLD: f"{who} foldea",
            ActionType.CHECK: f"{who} pasa",
            ActionType.CALL: f"{who} paga {amount:g}bb{tail}",
            ActionType.BET: f"{who} apuesta {amount:g}bb{tail}",
            ActionType.RAISE: f"{who} sube a {total:g}bb{tail}",
            ActionType.RETURN: f"Se devuelven {amount:g}bb a {who}",
        }
        return text.get(a.type, f"{who} {a.type.value}")

    def snapshot(self, index: int, description: str, actor: str | None) -> ReplayStep:
        bb = self.bb
        return ReplayStep(
            index=index,
            street=self.street,
            description=description,
            actor=actor,
            board=self.board,
            pot_bb=round(self.pot / bb, 4),
            stacks_bb={p: round(s / bb, 4) for p, s in self.stacks.items()},
            bets_bb={p: round(b / bb, 4) for p, b in self.bets.items()},
            folded=list(self.folded),
        )


def _scenario(
    state: _State, hero: str, ranges: dict[str, str], preflop: list[Action], log: list[str]
) -> dict:
    r = state.r
    bb = state.bb
    active = [p for p in state.stacks if p not in state.folded and p != hero]
    # Rival 1 = last aggressor still in the hand (opener / raiser / shover).
    aggressor = next(
        (a.player for a in reversed(state.applied) if a.type in AGGRESSIVE and a.player in active),
        None,
    )
    seat_order = list(state.pos)
    ordered = sorted(active, key=lambda p: (p != aggressor, seat_order.index(p)))
    to_call = max(state.bets.values()) - state.bets[hero]
    effective = min(state.stacks[hero], max(state.stacks[p] for p in active)) if active else 0.0
    scenario = {
        "format": r.game_type.value,
        "num_players": r.table_size,
        "hero_position": state.pos[hero],
        "hero_hand": r.hero_cards,
        "villains": [
            {
                "position": state.pos[p],
                "range": ranges.get(p, "random"),
                "hand": r.shown.get(p),
            }
            for p in ordered
        ],
        "board": state.board,
        "pot_bb": round(state.pot / bb, 4),
        "to_call_bb": round(min(to_call, state.stacks[hero]) / bb, 4),
        "effective_stack_bb": round(effective / bb, 4),
        "previous_action": "; ".join(log[-12:]),
        "ante_bb": round(r.ante / bb, 4),
    }
    if state.street == Street.PREFLOP:
        scenario["situation"] = preflop_situation(state.pos, hero, preflop, set(state.folded)).value
        if r.game_type in TOURNAMENT_FORMATS:
            scenario["stacks_bb"] = {
                state.pos[s.name]: round(s.stack / bb, 4) for s in r.dealt_seats
            }
    return scenario


def build_replay(record: HandRecord, ranges: dict[str, str] | None = None) -> Replay:
    ranges = dict(ranges or {})
    hero = record.hero
    state = _State(record)
    steps: list[ReplayStep] = []
    log: list[str] = []
    preflop: list[Action] = []

    def hero_equity() -> HeroEquity | None:
        if not hero or not record.hero_cards or hero in state.folded:
            return None
        opponents = [p for p in state.stacks if p != hero and p not in state.folded]
        if not opponents:
            return None
        return _equity(
            record.hero_cards, tuple(ranges.get(p, "random") for p in opponents), state.board
        )

    def push(description: str, actor: str | None) -> None:
        step = state.snapshot(len(steps), description, actor)
        step.hero_equity = hero_equity()
        steps.append(step)

    actions = record.actions
    posts = [a for a in actions if a.type in POSTS]
    for a in posts:
        state.apply(a)
    push("Ciegas" + (" y antes" if record.ante else ""), None)

    rest = [a for a in actions if a.type not in POSTS]
    for a in rest:
        if a.street != state.street:
            for street in STREETS[STREETS.index(state.street) + 1 : STREETS.index(a.street) + 1]:
                state.new_street(street)
                push(f"{STREET_LABEL[street]}: {_spaced(state.board)}", None)
        if (
            a.player == hero
            and a.type != ActionType.RETURN
            and steps
            and steps[-1].scenario is None
        ):
            steps[-1].scenario = _scenario(state, hero, ranges, preflop, log)
        state.apply(a)
        if a.street == Street.PREFLOP:
            preflop.append(a)
        text = state.describe(a)
        log.append(text)
        push(text, a.player)

    # Runout after an all-in: reveal the remaining board.
    final_street = {0: Street.PREFLOP, 3: Street.FLOP, 4: Street.TURN, 5: Street.RIVER}[
        len(record.board) // 2
    ]
    for street in STREETS[STREETS.index(state.street) + 1 : STREETS.index(final_street) + 1]:
        state.new_street(street)
        push(f"{STREET_LABEL[street]}: {_spaced(state.board)}", None)

    winners = [
        f"{state.label(p)} gana {amount / record.bb:g}bb" for p, amount in record.collected.items()
    ]
    push(" · ".join(winners) or "Fin de la mano", None)

    bb = record.bb
    players = [
        ReplayPlayer(
            name=s.name,
            seat=s.seat,
            position=state.pos[s.name],
            stack_bb=round(s.stack / bb, 4),
            is_hero=s.name == hero,
            cards=record.hero_cards if s.name == hero else record.shown.get(s.name),
        )
        for s in record.dealt_seats
    ]
    return Replay(
        site=record.site,
        hand_id=record.hand_id,
        game_type=record.game_type.value,
        bb=bb,
        players=players,
        ranges={p.name: ranges.get(p.name, "random") for p in players if not p.is_hero},
        steps=steps,
        result={s.name: round(record.net(s.name) / bb, 4) for s in record.dealt_seats},
    )


def _spaced(board: str) -> str:
    return " ".join(board[i : i + 2] for i in range(0, len(board), 2))
