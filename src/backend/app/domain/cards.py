"""Card text helpers with user-facing (Spanish) validation messages.

Cards are two-character strings: rank (23456789TJQKA) + suit (c d h s), e.g. "Ah".
"""

from __future__ import annotations

import random
from collections.abc import Iterable

RANKS = "23456789TJQKA"
SUITS = "cdhs"
DECK: tuple[str, ...] = tuple(r + s for r in RANKS for s in SUITS)


class CardError(ValueError):
    """Invalid card input. The message is meant to be shown to the user."""


def parse_cards(text: str | None) -> list[str]:
    """Parses "AhKd", "Ah Kd" or "ah,kd" into normalized cards ["Ah", "Kd"]."""
    if not text:
        return []
    compact = "".join(ch for ch in text if not ch.isspace() and ch != ",")
    if len(compact) % 2:
        raise CardError(f"Cartas inválidas: '{text}'")
    cards = []
    for i in range(0, len(compact), 2):
        rank, suit = compact[i].upper(), compact[i + 1].lower()
        if rank not in RANKS or suit not in SUITS:
            raise CardError(f"Carta inválida: '{compact[i : i + 2]}'")
        cards.append(rank + suit)
    duplicates = {c for c in cards if cards.count(c) > 1}
    if duplicates:
        raise CardError(f"Carta repetida: {', '.join(sorted(duplicates))}")
    return cards


def format_cards(cards: Iterable[str]) -> str:
    return "".join(cards)


def ensure_disjoint(groups: dict[str, list[str]]) -> None:
    """Raises CardError when the same card appears in two places (e.g. hero and board)."""
    seen: dict[str, str] = {}
    for label, cards in groups.items():
        for card in cards:
            if card in seen:
                raise CardError(f"La carta {card} está en {seen[card]} y en {label}")
            seen[card] = label


def draw(n: int, used: Iterable[str], rng: random.Random) -> list[str]:
    """Draws `n` distinct cards not in `used`."""
    available = [c for c in DECK if c not in set(used)]
    if n > len(available):
        raise CardError("No quedan cartas suficientes en el mazo")
    return rng.sample(available, n)
