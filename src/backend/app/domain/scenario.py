"""Scenario: what the simulator receives (spec section 5)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

import pokercore
from pydantic import BaseModel, Field, model_validator

from app.domain.cards import parse_cards
from app.domain.positions import MAX_PLAYERS, MIN_PLAYERS, position_names


class GameFormat(StrEnum):
    CASH = "cash"
    MTT = "mtt"
    SNG = "sng"
    SPIN = "spin"


TOURNAMENT_FORMATS = {GameFormat.MTT, GameFormat.SNG, GameFormat.SPIN}


class Situation(StrEnum):
    RFI = "rfi"  # folded to hero
    VS_OPEN = "vs_open"
    VS_3BET = "vs_3bet"
    VS_4BET = "vs_4bet"
    SQUEEZE = "squeeze"
    BVB = "bvb"  # blind vs blind
    VS_ALLIN = "vs_allin"


class Street(StrEnum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


BOARD_SIZE = {Street.PREFLOP: 0, Street.FLOP: 3, Street.TURN: 4, Street.RIVER: 5}
STREET_BY_BOARD_SIZE = {size: street for street, size in BOARD_SIZE.items()}

Amount = Annotated[float, Field(ge=0)]


class Villain(BaseModel):
    position: str | None = None
    # Range in standard notation. The recommendation and the main equity always use it.
    range: str = "random"
    # Optional exact hand: only used for the separate, informative equity.
    hand: str | None = None


class Scenario(BaseModel):
    format: GameFormat = GameFormat.CASH
    num_players: int = Field(default=6, ge=MIN_PLAYERS, le=MAX_PLAYERS)
    hero_position: str | None = None
    hero_hand: str
    villains: list[Villain] = Field(min_length=1)
    # Postflop solver inputs. Hero's range is required for a heads-up solve; the UI can
    # prefill it (and the villain's) from the preflop charts, flagging approximations.
    hero_range: str | None = None
    ranges_approximate: bool = False
    solver_preset: str = "chico"
    board: str = ""
    pot_bb: Amount = 0.0
    to_call_bb: Amount = 0.0
    effective_stack_bb: Amount = 100.0
    previous_action: str = ""
    # Preflop context for the recommendation engine. Villain 1 is the player who
    # opened / raised / shoved when the situation involves a rival.
    situation: Situation | None = None
    ante_bb: Amount = 0.0  # per player
    bb_ante_bb: Amount = 0.0  # big blind ante (paid by the BB)
    # Tournaments: stacks by position (defaults to the effective stack) and the
    # remaining payouts for ICM (empty = chip EV).
    stacks_bb: dict[str, float] = Field(default_factory=dict)
    payouts: list[Annotated[float, Field(ge=0)]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> Scenario:
        if len(self.villains) > self.num_players - 1:
            raise ValueError("Hay más rivales que asientos en la mesa")

        hero = parse_cards(self.hero_hand)
        if len(hero) != 2:
            raise ValueError("La mano de Hero debe tener 2 cartas")
        board = parse_cards(self.board)
        if len(board) not in STREET_BY_BOARD_SIZE:
            raise ValueError("El board debe tener 0, 3, 4 o 5 cartas")
        self.hero_hand = "".join(hero)
        self.board = "".join(board)

        used = {c: "la mano de Hero" for c in hero}
        for c in board:
            if c in used:
                raise ValueError(f"La carta {c} está en {used[c]} y en el board")
            used[c] = "el board"
        for i, v in enumerate(self.villains, start=1):
            if v.hand:
                cards = parse_cards(v.hand)
                if len(cards) != 2:
                    raise ValueError(f"La mano del rival {i} debe tener 2 cartas")
                for c in cards:
                    if c in used:
                        raise ValueError(
                            f"La carta {c} está en {used[c]} y en la mano del rival {i}"
                        )
                    used[c] = f"la mano del rival {i}"
                v.hand = "".join(cards)
            else:
                v.hand = None
            if not v.range.strip():
                v.range = "random"
            try:
                pokercore.range_combos(v.range)
            except ValueError as e:
                raise ValueError(f"Rango inválido del rival {i}: {e}") from e

        if self.hero_range is not None:
            if not self.hero_range.strip():
                self.hero_range = None
            else:
                try:
                    pokercore.range_combos(self.hero_range)
                except ValueError as e:
                    raise ValueError(f"Rango inválido de Hero: {e}") from e

        valid_positions = set(position_names(self.num_players))
        given = [p for p in [self.hero_position, *(v.position for v in self.villains)] if p]
        for p in given:
            if p not in valid_positions:
                raise ValueError(f"Posición {p} no existe en una mesa de {self.num_players}")
        if len(given) != len(set(given)):
            raise ValueError("Dos jugadores no pueden ocupar la misma posición")

        for pos, stack in self.stacks_bb.items():
            if pos not in valid_positions:
                raise ValueError(f"Posición {pos} no existe en una mesa de {self.num_players}")
            if stack <= 0:
                raise ValueError("Los stacks deben ser positivos")

        if self.to_call_bb > self.pot_bb:
            raise ValueError(
                "El monto a pagar no puede superar el pote (que incluye la apuesta rival)"
            )
        return self

    @property
    def street(self) -> Street:
        return STREET_BY_BOARD_SIZE[len(self.board) // 2]
