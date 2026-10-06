"""Preflop all-in equity between the 169 hand classes, with card removal.

E[a, b]: heads-up equity of class a vs class b (precomputed, data/precomputed).
N[a, b]: number of compatible combo pairs between a and b (card removal).
Ranges are 169-vectors of class weights in [0, 1] (13x13 grid order).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pokercore

from app.config import REPO_ROOT

MATRIX_PATH = REPO_ROOT / "data" / "precomputed" / "preflop_equity_169.npy"
RANKS = "23456789TJQKA"


@lru_cache
def class_names() -> tuple[str, ...]:
    return tuple(pokercore.hand_class_names())


@lru_cache
def class_index() -> dict[str, int]:
    return {name: i for i, name in enumerate(class_names())}


def combos_per_class() -> np.ndarray:
    return np.array([6 if len(n) == 2 else 4 if n[2] == "s" else 12 for n in class_names()], float)


def hand_class(hand: str) -> str:
    """Class name of a two-card hand, e.g. "AhKh" -> "AKs", "7c7d" -> "77"."""
    hand = "".join(hand.split())
    r1, s1, r2, s2 = hand[0].upper(), hand[1].lower(), hand[2].upper(), hand[3].lower()
    hi, lo = sorted((r1, r2), key=RANKS.index, reverse=True)
    if hi == lo:
        return hi + lo
    return hi + lo + ("s" if s1 == s2 else "o")


@dataclass(frozen=True)
class PreflopEquity:
    equity: np.ndarray  # (169, 169)
    compat: np.ndarray  # (169, 169) compatible combo pairs
    weighted: np.ndarray  # equity * compat

    def vs_range(self, villain: np.ndarray) -> np.ndarray:
        """Equity of each hero class against a weighted villain range (nan if no combos)."""
        den = self.compat @ villain
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(den > 0, (self.weighted @ villain) / den, np.nan)

    def play_probability(self, villain: np.ndarray) -> np.ndarray:
        """P(villain holds a hand of the range | hero class), with card removal."""
        return (self.compat @ villain) / self.compat.sum(axis=1)

    def range_vs_range(self, hero: np.ndarray, villain: np.ndarray) -> float:
        den = float(hero @ self.compat @ villain)
        return float(hero @ self.weighted @ villain) / den if den > 0 else 0.5

    def range_play_probability(self, hero: np.ndarray, villain: np.ndarray) -> float:
        """P(villain holds a hand of its range | hero holds a hand of its range)."""
        den = float(hero @ self.compat.sum(axis=1))
        return float(hero @ self.compat @ villain) / den if den > 0 else 0.0


def _compatibility() -> np.ndarray:
    names = class_index()
    cards: list[tuple[int, int]] = []
    owner: list[int] = []
    deck = [r + s for r in RANKS for s in "cdhs"]
    for i, a in enumerate(deck):
        for b in deck[i + 1 :]:
            cards.append((i, deck.index(b)))
            owner.append(names[hand_class(a + b)])
    c = np.array(cards)
    # Two combos conflict when they share a card.
    share = (
        (c[:, None, 0] == c[None, :, 0])
        | (c[:, None, 0] == c[None, :, 1])
        | (c[:, None, 1] == c[None, :, 0])
        | (c[:, None, 1] == c[None, :, 1])
    )
    member = np.zeros((len(cards), 169))
    member[np.arange(len(cards)), owner] = 1.0
    return member.T @ (~share).astype(float) @ member


@lru_cache
def preflop_equity() -> PreflopEquity:
    equity = np.load(MATRIX_PATH).astype(float)
    compat = _compatibility()
    return PreflopEquity(equity=equity, compat=compat, weighted=equity * compat)


def range_vector(text: str) -> np.ndarray:
    return np.asarray(pokercore.range_grid(text), dtype=float)


def grid_to_text(grid: list[float] | np.ndarray, digits: int = 3) -> str:
    """169 class weights -> notation ("AA,AKs:0.5,...") compatible with PioViewer imports."""
    parts = []
    for name, w in zip(class_names(), grid, strict=True):
        w = round(float(w), digits)
        if w >= 1.0:
            parts.append(name)
        elif w > 0.0:
            parts.append(f"{name}:{w:g}")
    return ",".join(parts)
