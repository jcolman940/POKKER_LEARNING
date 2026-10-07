"""TexasSolver JSON output -> compact strategy tree for the current street.

Facts about the raw format (verified against v0.2.0):
- `player` 1 is OOP and 0 is IP.
- Action strings: CHECK, CALL, FOLD, "BET <chips>", "RAISE <chips>" (RAISE is the
  street total, not the increment); amounts are whole chips (x CHIP_SCALE).
- Chance nodes (next street / showdown) are dropped: we only keep the street solved.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pokercore

from app.recommend.preflop_equity import hand_class
from app.solver.spot import CHIP_SCALE, Side

RANKS = "23456789TJQKA"
SUITS = "cdhs"
PLAYER: dict[int, Side] = {1: "oop", 0: "ip"}


def _card_key(card: str) -> tuple[int, int]:
    return (RANKS.index(card[0]), SUITS.index(card[1]))


def canonical_combo(combo: str) -> str:
    a, b = combo[:2], combo[2:]
    hi, lo = sorted((a, b), key=_card_key, reverse=True)
    return hi + lo


@dataclass(frozen=True)
class SolverAction:
    kind: str  # check / bet / call / raise / fold / allin
    amount_bb: float | None = None

    def label(self, pot_bb: float) -> str:
        if self.amount_bb is None:
            return self.kind.capitalize()
        if self.kind == "allin":
            return f"All-in ({self.amount_bb:g}bb)"
        if self.kind == "bet" and pot_bb > 0:
            return f"Bet {round(100 * self.amount_bb / pot_bb)}% ({self.amount_bb:g}bb)"
        return f"{self.kind.capitalize()} a {self.amount_bb:g}bb"


@dataclass
class StrategyNode:
    player: Side
    actions: list[SolverAction]
    strategy: dict[str, list[float]]
    children: dict[int, StrategyNode] = field(default_factory=dict)

    def child(self, kind: str, amount_bb: float | None = None) -> StrategyNode | None:
        for i, action in enumerate(self.actions):
            if action.kind == kind and (amount_bb is None or action.amount_bb == amount_bb):
                return self.children.get(i)
        return None

    def range_mix(self, weights: dict[str, float]) -> list[float]:
        totals = [0.0] * len(self.actions)
        mass = 0.0
        for combo, freqs in self.strategy.items():
            w = weights.get(combo, 0.0)
            if w <= 0:
                continue
            mass += w
            for i, f in enumerate(freqs):
                totals[i] += w * f
        return [t / mass for t in totals] if mass > 0 else totals

    def class_layers(self, weights: dict[str, float]) -> list[list[float]]:
        """Per action, the 169-class grid of (range weight x frequency), averaged per class."""
        index = {n: i for i, n in enumerate(pokercore.hand_class_names())}
        sums = [[0.0] * 169 for _ in self.actions]
        counts = [0] * 169
        for combo, freqs in self.strategy.items():
            w = weights.get(combo, 0.0)
            cls = index[hand_class(combo)]
            counts[cls] += 1
            for i, f in enumerate(freqs):
                sums[i][cls] += w * f
        return [[s / counts[c] if counts[c] else 0.0 for c, s in enumerate(row)] for row in sums]

    def to_dict(self) -> dict:
        return {
            "p": self.player,
            "a": [[a.kind, a.amount_bb] for a in self.actions],
            "s": self.strategy,
            "c": {str(i): n.to_dict() for i, n in self.children.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> StrategyNode:
        return cls(
            player=d["p"],
            actions=[SolverAction(k, a) for k, a in d["a"]],
            strategy=d["s"],
            children={int(i): cls.from_dict(n) for i, n in d["c"].items()},
        )


def _action(text: str, stack_chips: int) -> SolverAction:
    head, _, amount = text.partition(" ")
    kind = head.lower()
    if not amount:
        return SolverAction(kind)
    chips = round(float(amount))
    if chips >= stack_chips:
        kind = "allin"
    return SolverAction(kind, chips / CHIP_SCALE)


def _parse_node(raw: dict, stack_chips: int) -> StrategyNode | None:
    if raw.get("node_type") != "action_node":
        return None
    actions = [_action(a, stack_chips) for a in raw["actions"]]
    strategy = {
        canonical_combo(c): [float(x) for x in freqs]
        for c, freqs in raw["strategy"]["strategy"].items()
    }
    children = {}
    for i, text in enumerate(raw["actions"]):
        sub = raw.get("childrens", {}).get(text)
        node = _parse_node(sub, stack_chips) if sub else None
        if node is not None:
            children[i] = node
    return StrategyNode(PLAYER[raw["player"]], actions, strategy, children)


def parse_output(raw: dict, stack_bb: float) -> StrategyNode:
    try:
        node = _parse_node(raw, round(stack_bb * CHIP_SCALE))
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"Salida del solver con formato inesperado: {e}") from e
    if node is None:
        raise ValueError("La salida del solver no empieza en un nodo de acción")
    return node


@dataclass
class HeroNode:
    node: StrategyNode
    warnings: list[str]


def _facing(node: StrategyNode, facing_bet_bb: float) -> tuple[StrategyNode, list[str]]:
    bets = [(i, a) for i, a in enumerate(node.actions) if a.kind in ("bet", "allin")]
    if not bets:
        raise ValueError("El árbol no tiene apuestas en este nodo")
    i, best = min(bets, key=lambda x: abs((x[1].amount_bb or 0) - facing_bet_bb))
    child = node.children.get(i)
    if child is None:
        raise ValueError("El árbol no tiene el nodo de respuesta a la apuesta")
    warnings = []
    if abs((best.amount_bb or 0) - facing_bet_bb) > 0.01:
        warnings.append(
            f"Apuesta ajustada de {facing_bet_bb:g}bb a {best.amount_bb:g}bb (tamaño del árbol)."
        )
    return child, warnings


def find_hero_node(root: StrategyNode, hero: Side, facing_bet_bb: float) -> HeroNode:
    if hero == "oop" and facing_bet_bb <= 0:
        return HeroNode(root, [])
    after_check = root.child("check")
    if hero == "ip" and facing_bet_bb <= 0:
        if after_check is None:
            raise ValueError("El árbol no tiene el nodo después del check")
        return HeroNode(after_check, [])
    if hero == "ip":
        return HeroNode(*_facing(root, facing_bet_bb))
    if after_check is None:
        raise ValueError("El árbol no tiene el nodo después del check")
    return HeroNode(*_facing(after_check, facing_bet_bb))
