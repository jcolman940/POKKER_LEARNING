"""A reproducible subset of flops covering the main textures.

All 22,100 flops are reduced to suit-isomorphic classes (weighted by how many real
flops they stand for), grouped by texture, and picked round-robin from the most
frequent textures so the subset reflects how often each texture comes up.

Texture = (high-card bucket A/K/Q/J/T/9-7/6-, suit pattern, shape). Inside a group the
members are sorted by rank tuple and picked spread out from the middle: the median
first, then the ~25% and ~75% members, then ~12.5%, ~62.5%, ... (a deterministic
bisection), so boards do not cluster on the lowest cards. Monotone groups get a x3 weight
boost when ordering groups, otherwise their rarity would leave them out of 25 picks.
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
    high = "AKQJT"[12 - hi] if hi >= 8 else "9-7" if hi >= 5 else "6-"
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


def _spread_indices(m: int) -> list[int]:
    """All indices 0..m-1, median first, then bisection fractions 1/4, 3/4, 1/8, 5/8, ..."""
    order: list[int] = []
    seen: set[int] = set()
    fractions = [0.5]
    denom = 4
    while len(fractions) < 2 * m + 2:
        fractions += [k / denom for k in range(1, denom, 2) if k / denom != 0.5]
        denom *= 2
    for f in fractions:
        i = min(int(f * m), m - 1)
        if i not in seen:
            seen.add(i)
            order.append(i)
    order += [i for i in range(m) if i not in seen]
    return order


def representative_flops(n: int = 25) -> list[str]:
    groups: dict[tuple[str, str, str], list[tuple[int, str]]] = defaultdict(list)
    for flop, weight in _classes().items():
        groups[_texture(flop)].append((weight, flop))
    spread: dict[tuple[str, str, str], list[str]] = {}
    for key, members in groups.items():
        by_rank = sorted(
            (f for _, f in members),
            key=lambda f: ([RANKS.index(f[i]) for i in (0, 2, 4)], f),
        )
        spread[key] = [by_rank[i] for i in _spread_indices(len(by_rank))]
    # Monotone boards are rare (~5%) but study-relevant: boost them so they make the cut.
    boost = {"mono": 3}
    order = sorted(groups, key=lambda k: (-sum(w for w, _ in groups[k]) * boost.get(k[1], 1), k))
    picked: list[str] = []
    used: dict[str, int] = {}
    depth = 0
    while len(picked) < n:
        added = False
        for key in order:
            if depth < len(spread[key]) and len(picked) < n:
                added = True
                flop = spread[key][depth]
                low = flop[2] + flop[4]  # two lowest ranks
                mid = "mid" + flop[2]
                # keep boards from clustering on the same low cards / middle rank
                if used.get(low, 0) < 3 and used.get(mid, 0) < 3:
                    used[low] = used.get(low, 0) + 1
                    used[mid] = used.get(mid, 0) + 1
                    picked.append(flop)
        if not added:
            break
        depth += 1
    return picked
