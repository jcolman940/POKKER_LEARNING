"""Pot geometry metrics shown by the simulator.

Conventions (all amounts in big blinds):
- `pot` is everything in the middle, including the bet the hero is facing.
- `to_call` is what the hero must put in to continue.
- MDF assumes the hero has not invested earlier in the street, so the bet faced
  equals `to_call` and the pot before the bet is `pot - to_call`.
- SPR is the effective stack behind divided by the pot.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PotMetrics:
    pot_odds: float | None  # x in "x : 1"
    required_equity: float | None
    mdf: float | None
    spr: float | None


def pot_metrics(pot: float, to_call: float, effective_stack: float) -> PotMetrics:
    if pot < 0 or to_call < 0 or effective_stack < 0:
        raise ValueError("Los montos no pueden ser negativos")
    facing_bet = to_call > 0
    if facing_bet and to_call > pot:
        raise ValueError("El monto a pagar no puede superar el pote (que incluye la apuesta rival)")
    return PotMetrics(
        pot_odds=pot / to_call if facing_bet else None,
        required_equity=to_call / (pot + to_call) if facing_bet else None,
        mdf=(pot - to_call) / pot if facing_bet else None,
        spr=effective_stack / pot if pot > 0 else None,
    )
