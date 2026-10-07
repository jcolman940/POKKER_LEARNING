"""A reproducible subset of flops covering the main textures.

All 22,100 flops are reduced to suit-isomorphic classes (weighted by how many real
flops they stand for), grouped by texture, and picked round-robin from the most
frequent textures so the subset reflects how often each texture comes up.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from itertools import combinations

RANKS = "23456789TJQKA"
SUITS = "shdc"  # canonical suit names in order of first appearance
DECK = [r + s for r in RANKS for s in "cdhs"]


def _canonical(cards: tuple[str, ...]) -> str:
    ordered = sorted(cards, key=lambda c: (RANKS.index(c[0]), "cdhs".index(c[1])), reverse=True)
    mapping: dict[str, str] = {}
    out = []
    for c in ordered:
        mapping.setdefault(c[1], SUITS[len(mapping)])
        out.append(c[0] + mapping[c[1]])
    return "".join(out)


def _texture(flop: str) -> tuple[str, str, str]:
    ranks = [flop[0], flop[2], flop[4]]
    suits = {flop[1], flop[3], flop[5]}
    hi = RANKS.index(ranks[0])
    high = "A" if hi == 12 else "K-Q" if hi >= 10 else "J-T" if hi >= 8 else "9-"
    suit = {1: "mono", 2: "two-tone", 3: "rainbow"}[len(suits)]
    idx = sorted({RANKS.index(r) for r in ranks})
    if len(idx) < 3:
        shape = "paired"
    elif idx[-1] - idx[0] <= 4:
        shape = "connected"
    else:
        shape = "disconnected"
    return high, suit, shape


@lru_cache
def _classes() -> dict[str, int]:
    weights: dict[str, int] = defaultdict(int)
    for cards in combinations(DECK, 3):
        weights[_canonical(cards)] += 1
    return dict(weights)


def representative_flops(n: int = 25) -> list[str]:
    groups: dict[tuple[str, str, str], list[tuple[int, str]]] = defaultdict(list)
    for flop, weight in _classes().items():
        groups[_texture(flop)].append((weight, flop))
    for members in groups.values():
        members.sort(key=lambda x: (-x[0], x[1]))
    order = sorted(groups, key=lambda k: (-sum(w for w, _ in groups[k]), k))
    picked: list[str] = []
    depth = 0
    while len(picked) < n:
        added = False
        for key in order:
            if depth < len(groups[key]) and len(picked) < n:
                picked.append(groups[key][depth][1])
                added = True
        if not added:
            break
        depth += 1
    return picked
