"""HandRecord: a played hand, normalized and independent of the poker room.

Every room parser produces this model; stats, the replayer and the trainer only
read it. Amounts are in chips (tournaments) or money units (cash), exactly as the
room reports them; `bb` lets every consumer normalize to big blinds.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.domain.cards import parse_cards
from app.domain.positions import position_of_seat
from app.domain.scenario import GameFormat, Street


class ActionType(StrEnum):
    POST_SB = "post_sb"
    POST_BB = "post_bb"
    POST_ANTE = "post_ante"
    POST_DEAD = "post_dead"  # dead blind / straddle-like posts that are not voluntary
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    RETURN = "return"  # uncalled bet returned to the player


POSTS = {ActionType.POST_SB, ActionType.POST_BB, ActionType.POST_ANTE, ActionType.POST_DEAD}
VOLUNTARY = {ActionType.CALL, ActionType.BET, ActionType.RAISE}
AGGRESSIVE = {ActionType.BET, ActionType.RAISE}


class Action(BaseModel):
    street: Street
    player: str
    type: ActionType
    # Chips this action moves into the pot (for RETURN: chips given back).
    amount: float = Field(default=0.0, ge=0)
    # For raises: the total the player's bet reaches on this street.
    to_amount: float | None = None
    all_in: bool = False


class Seat(BaseModel):
    seat: int
    name: str
    stack: float = Field(gt=0)
    sitting_out: bool = False


class TournamentInfo(BaseModel):
    tournament_id: str
    buy_in: float | None = None  # prize pool contribution
    fee: float | None = None
    currency: str | None = None
    level: str | None = None
    # Filled when the history reveals it (e.g. the hero's last hand).
    finish: int | None = None
    prize: float | None = None


class HandRecord(BaseModel):
    site: str
    hand_id: str
    played_at: datetime
    game_type: GameFormat
    table_name: str = ""
    max_seats: int = Field(ge=2, le=10)
    currency: str | None = None
    sb: float = Field(gt=0)
    bb: float = Field(gt=0)
    ante: float = Field(default=0.0, ge=0)
    tournament: TournamentInfo | None = None
    button_seat: int
    seats: list[Seat]
    hero: str | None = None
    hero_cards: str | None = None
    actions: list[Action]
    board: str = ""
    shown: dict[str, str] = Field(default_factory=dict)  # player -> hole cards at showdown
    collected: dict[str, float] = Field(default_factory=dict)  # player -> chips won
    rake: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def _validate(self) -> HandRecord:
        names = [s.name for s in self.seats]
        if len(set(names)) != len(names):
            raise ValueError("duplicate player names")
        if len({s.seat for s in self.seats}) != len(self.seats):
            raise ValueError("duplicate seat numbers")
        known = set(names)
        for a in self.actions:
            if a.player not in known:
                raise ValueError(f"action by unknown player {a.player!r}")
        for who in [*self.shown, *self.collected, *([self.hero] if self.hero else [])]:
            if who not in known:
                raise ValueError(f"unknown player {who!r}")
        if self.button_seat not in {s.seat for s in self.seats}:
            raise ValueError("button seat is not occupied")
        board = parse_cards(self.board)
        if len(board) > 5:
            raise ValueError("board has more than 5 cards")
        self.board = "".join(board)
        if self.hero_cards:
            self.hero_cards = "".join(parse_cards(self.hero_cards))
        self.shown = {p: "".join(parse_cards(c)) for p, c in self.shown.items()}
        return self

    # ---- Derived views ---------------------------------------------------------

    @property
    def dealt_seats(self) -> list[Seat]:
        """Players dealt into the hand (sitting-out players do not count)."""
        return [s for s in self.seats if not s.sitting_out]

    @property
    def table_size(self) -> int:
        return len(self.dealt_seats)

    def positions(self) -> dict[str, str]:
        """Position of every dealt player, relative to the button."""
        dealt = self.dealt_seats
        occupied = [s.seat for s in dealt]
        button = self.button_seat
        if button not in occupied:
            # Button on a sitting-out seat: use the closest dealt seat before it.
            before = [s for s in occupied if s < button]
            button = max(before) if before else max(occupied)
        return {s.name: position_of_seat(s.seat, button, occupied) for s in dealt}

    def stack_of(self, player: str) -> float:
        return next(s.stack for s in self.seats if s.name == player)

    def contributions(self) -> dict[str, float]:
        """Chips each player put in the pot (posts included, uncalled returns removed)."""
        out = {s.name: 0.0 for s in self.seats}
        for a in self.actions:
            if a.type == ActionType.RETURN:
                out[a.player] -= a.amount
            else:
                out[a.player] += a.amount
        return out

    def net(self, player: str) -> float:
        return self.collected.get(player, 0.0) - self.contributions()[player]

    def folded(self) -> set[str]:
        return {a.player for a in self.actions if a.type == ActionType.FOLD}

    def went_to_showdown(self) -> set[str]:
        """Players who reached showdown: more than one player left after the river
        action (or an all-in runout) and did not fold."""
        alive = [s.name for s in self.dealt_seats if s.name not in self.folded()]
        return set(alive) if len(alive) > 1 else set()

    def board_at(self, street: Street) -> str:
        size = {Street.PREFLOP: 0, Street.FLOP: 3, Street.TURN: 4, Street.RIVER: 5}[street]
        return self.board[: size * 2]
