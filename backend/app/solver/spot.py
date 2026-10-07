"""A postflop spot as the solver sees it, its canonical form and its cache key."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

import pokercore

from app.recommend.preflop_equity import hand_class
from app.solver.trees import TreePreset, get_preset

Side = Literal["oop", "ip"]

SOLVER_VERSION = "texassolver-0.2.0"
CHIP_SCALE = 100  # the solver rounds amounts to whole chips: 1bb = 100 chips
ACCURACY = 0.5  # target exploitability, % of the pot
MAX_ITERATION = 200
ALLIN_THRESHOLD = 0.67
RAISE_LIMIT = 3
STREET_BY_CARDS = {3: "flop", 4: "turn", 5: "river"}


@dataclass(frozen=True)
class SolverRange:
    text: str  # class-level notation the solver accepts ("AKs,KJo:0.5")
    approximated: bool  # True when combo-level weights had to be averaged per class


def _class_size(name: str) -> int:
    if len(name) == 2:
        return 6
    return 4 if name.endswith("s") else 12


def to_solver_range(text: str) -> SolverRange:
    """Our notation (classes, combos, weights) -> class-level notation for TexasSolver.

    TexasSolver rejects specific combos, so each class gets its average weight; when the
    combos of a class had different weights the result is flagged as approximated.
    """
    names = pokercore.hand_class_names()
    grid = pokercore.range_grid(text)
    parts = []
    for name, weight in zip(names, grid, strict=True):
        if weight < 0.0005:
            continue
        parts.append(name if weight >= 0.9995 else f"{name}:{round(weight, 3):g}")
    if not parts:
        raise ValueError("El rango está vacío")

    weights_by_class: dict[str, list[float]] = defaultdict(list)
    for combo, weight in pokercore.range_combos(text):
        weights_by_class[hand_class(combo)].append(weight)
    approximated = any(
        len(ws) != _class_size(cls) or max(ws) - min(ws) > 1e-6
        for cls, ws in weights_by_class.items()
    )
    return SolverRange(text=",".join(parts), approximated=approximated)


def facing_pct(to_call_bb: float, pot_before_bet_bb: float) -> float:
    """Bet size as a whole % of the pot before the bet (the solver works in whole %)."""
    return float(round(100 * to_call_bb / pot_before_bet_bb))


@dataclass(frozen=True)
class SolverSpot:
    board: tuple[str, ...]
    pot_bb: float  # pot at the start of the street
    stack_bb: float  # effective stack at the start of the street
    range_oop: str
    range_ip: str
    preset: TreePreset
    bettor: Side | None = None  # who bet the size hero faces (injected into the tree)
    facing_bet_pct: float | None = None

    @property
    def street(self) -> str:
        return STREET_BY_CARDS[len(self.board)]

    def canonical(self) -> dict:
        flop = sorted(self.board[:3])
        return {
            "solver": SOLVER_VERSION,
            "accuracy": ACCURACY,
            "max_iteration": MAX_ITERATION,
            "allin_threshold": ALLIN_THRESHOLD,
            "raise_limit": RAISE_LIMIT,
            "board": [*flop, *self.board[3:]],
            "pot": round(self.pot_bb, 2),
            "stack": round(self.stack_bb, 2),
            "range_oop": self.range_oop,
            "range_ip": self.range_ip,
            "preset": self.preset.canonical(),
            "bettor": self.bettor,
            "facing_bet_pct": self.facing_bet_pct,
        }

    def spot_hash(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    def to_json(self) -> dict:
        return {
            "board": list(self.board),
            "pot_bb": self.pot_bb,
            "stack_bb": self.stack_bb,
            "range_oop": self.range_oop,
            "range_ip": self.range_ip,
            "preset": self.preset.name,
            "bettor": self.bettor,
            "facing_bet_pct": self.facing_bet_pct,
        }

    @classmethod
    def from_json(cls, d: dict) -> SolverSpot:
        return cls(
            board=tuple(d["board"]),
            pot_bb=d["pot_bb"],
            stack_bb=d["stack_bb"],
            range_oop=d["range_oop"],
            range_ip=d["range_ip"],
            preset=get_preset(d["preset"]),
            bettor=d.get("bettor"),
            facing_bet_pct=d.get("facing_bet_pct"),
        )

    def label(self) -> str:
        board = " ".join(self.board)
        text = (
            f"{self.street.capitalize()} {board} · pote {self.pot_bb:g}bb · "
            f"stack {self.stack_bb:g}bb"
        )
        if self.bettor and self.facing_bet_pct:
            text += f" · {self.bettor.upper()} apuesta {self.facing_bet_pct:g}%"
        return text
