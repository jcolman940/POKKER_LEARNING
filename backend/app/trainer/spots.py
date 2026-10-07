"""Spot generators for the trainer: push/fold MTT spots and spots from the user's charts."""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import PreflopChart
from app.domain.positions import preflop_order
from app.domain.scenario import TOURNAMENT_FORMATS, GameFormat, Scenario, Situation, Villain
from app.leaks.finder import stack_bucket
from app.recommend.engine import solve_spot
from app.recommend.preflop_equity import class_names, combos_per_class, hand_class
from app.recommend.pushfold import PushFoldResult

PUSHFOLD_TABLES = (9, 6, 3, 2)
POOL_SIZE = 12
HERO_STACK = (3, 15)
OTHER_STACK = (5, 40)
DEFAULT_DIFFICULTY = 50
EPS = 1e-9
SUITS = "shdc"
RANKS = "AKQJT98765432"


@dataclass(frozen=True)
class TrainerSpot:
    source: Literal["pushfold", "chart"]
    scenario: Scenario
    offered: list[str]
    card_key: str
    chart_id: int | None = None


def pushfold_pool(table_size: int) -> list[list[float]]:
    """Fixed stack configurations for a table size (deterministic)."""
    rng = random.Random(table_size)
    pool: list[list[float]] = []
    for j in range(POOL_SIZE):
        stacks = [float(rng.randint(*OTHER_STACK)) for _ in range(table_size)]
        stacks[j % table_size] = float(rng.randint(*HERO_STACK))
        pool.append(stacks)
    return pool


# ---------------------------------------------------------------- hand choice


def _combo(rng: random.Random, cls: str) -> str:
    hi, lo = cls[0], cls[1]
    if len(cls) == 2:
        s1, s2 = rng.sample(SUITS, 2)
    elif cls[2] == "s":
        s1 = s2 = rng.choice(SUITS)
    else:
        s1, s2 = rng.sample(SUITS, 2)
    return f"{hi}{s1}{lo}{s2}"


def pick_hand(
    rng: random.Random, weights_by_class: np.ndarray, frontier: np.ndarray, difficulty: int
) -> str:
    """A concrete combo: from the frontier with probability difficulty/100, else any class.

    Both draws are weighted by `weights_by_class` (combos per class).
    """
    weights = np.asarray(weights_by_class, float)
    front = weights * np.asarray(frontier, bool)
    use_frontier = front.sum() > 0 and rng.random() < difficulty / 100
    w = front if use_frontier else weights
    idx = rng.choices(range(169), weights=w.tolist())[0]
    return _combo(rng, class_names()[idx])


def _grid_pos(name: str) -> tuple[int, int]:
    hi, lo = RANKS.index(name[0]), RANKS.index(name[1])
    if len(name) == 3 and name[2] == "o":
        return lo, hi
    return hi, lo


def chart_frontier(actions: dict[str, list[float]]) -> np.ndarray:
    """Classes with a mixed strategy, or on the edge of the range in the 13x13 grid."""
    total = np.zeros(169)
    top = np.zeros(169)
    for freqs in actions.values():
        arr = np.asarray(freqs, float)
        total += arr
        top = np.maximum(top, arr)
    inside = total > EPS
    mixed = inside & (top < 1 - EPS)
    names = class_names()
    cell = {_grid_pos(n): i for i, n in enumerate(names)}
    edge = np.zeros(169, bool)
    for i, name in enumerate(names):
        r, c = _grid_pos(name)
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            j = cell.get((r + dr, c + dc))
            if j is not None and inside[j] != inside[i]:
                edge[i] = True
                break
    return mixed | edge


def pushfold_frontier(ev_act: np.ndarray, ev_fold: float, scale: float) -> np.ndarray:
    return np.abs(np.asarray(ev_act, float) - ev_fold) < 1.0 * scale


# ----------------------------------------------------------------- card key


def card_key(spot: TrainerSpot) -> str:
    sc = spot.scenario
    cls = hand_class(sc.hero_hand)
    if spot.source == "chart":
        return f"chart|{spot.chart_id}|{cls}"
    assert sc.situation
    vs = sc.villains[0].position if sc.situation == Situation.VS_ALLIN else None
    bucket = stack_bucket(sc.effective_stack_bb, True)
    head = f"pushfold|{sc.format.value}|{sc.hero_position}|{sc.situation.value}"
    return f"{head}|{vs or '-'}|{bucket}|{cls}"


def _finish(spot: TrainerSpot) -> TrainerSpot:
    return replace(spot, card_key=card_key(spot))


# ------------------------------------------------------------------ push/fold


def _passes(filters: dict, key: str, value: str) -> bool:
    allowed = filters.get(key)
    return not allowed or value in allowed


def _pushfold_candidates(filters: dict, table: int) -> dict[Situation, list[tuple[int, int]]]:
    """(config index, hero index) by situation, honouring the filters."""
    order = preflop_order(table)
    out: dict[Situation, list[tuple[int, int]]] = {Situation.RFI: [], Situation.VS_ALLIN: []}
    for ci, stacks in enumerate(pushfold_pool(table)):
        for hi, pos in enumerate(order):
            if not HERO_STACK[0] <= stacks[hi] <= HERO_STACK[1]:
                continue
            if not _passes(filters, "positions", pos):
                continue
            if not _passes(filters, "stack_buckets", stack_bucket(stacks[hi], True)):
                continue
            if pos != "BB" and _passes(filters, "situations", Situation.RFI.value):
                out[Situation.RFI].append((ci, hi))
            if hi > 0 and _passes(filters, "situations", Situation.VS_ALLIN.value):
                out[Situation.VS_ALLIN].append((ci, hi))
    return out


def _pick_pusher(
    rng: random.Random, result: PushFoldResult, order: list[str], hero_idx: int
) -> str:
    earlier = order[:hero_idx]
    combos = combos_per_class()
    active = [p for p in earlier if float(combos @ result.push[p]) > 0]
    return rng.choice(active or earlier)


def generate_pushfold(
    session: Session,
    rng: random.Random,
    filters: dict,
    payouts: list[float],
    difficulty: int = DEFAULT_DIFFICULTY,
) -> TrainerSpot | None:
    if filters.get("formats") and GameFormat.MTT.value not in filters["formats"]:
        return None
    tables = [t for t in PUSHFOLD_TABLES if _passes(filters, "table_sizes", t)]
    rng.shuffle(tables)
    for table in tables:
        by_sit = {s: c for s, c in _pushfold_candidates(filters, table).items() if c}
        if not by_sit:
            continue
        situation = rng.choice(sorted(by_sit, key=lambda s: s.value))
        ci, hi = rng.choice(by_sit[situation])
        order = preflop_order(table)
        stacks = pushfold_pool(table)[ci]
        hero = order[hi]
        result = solve_spot(stacks, 0.0, 1.0, payouts)
        if situation == Situation.RFI:
            pusher = None
            ev_act, ev_fold = result.push_ev[hero]
            villain, offered = "BB", ["allin", "fold"]
        else:
            pusher = _pick_pusher(rng, result, order, hi)
            ev_act, ev_fold = result.call_ev[(pusher, hero)]
            villain, offered = pusher, ["call", "fold"]
        scale = sum(payouts) / 100 if payouts else 1.0
        hand = pick_hand(
            rng, combos_per_class(), pushfold_frontier(ev_act, ev_fold, scale), difficulty
        )
        scenario = Scenario(
            format=GameFormat.MTT,
            num_players=table,
            hero_position=hero,
            hero_hand=hand,
            villains=[Villain(position=pusher or villain)],
            situation=situation,
            effective_stack_bb=stacks[hi],
            bb_ante_bb=1.0,
            stacks_bb=dict(zip(order, stacks, strict=True)),
            payouts=list(payouts),
        )
        return _finish(TrainerSpot("pushfold", scenario, offered, "", None))
    return None


# --------------------------------------------------------------------- charts


def _chart_usable(chart: PreflopChart) -> Situation | None:
    """The chart's situation when it can become a valid Scenario, else None."""
    try:
        situation = Situation(chart.situation)
        GameFormat(chart.game_format)
        order = preflop_order(chart.players)
    except ValueError:
        return None
    if chart.position not in order:
        return None
    if chart.vs_position and (
        chart.vs_position not in order or chart.vs_position == chart.position
    ):
        return None
    if not any(any(f > 0 for f in freqs) for freqs in chart.actions.values()):
        return None
    return situation


def generate_chart(
    session: Session,
    rng: random.Random,
    filters: dict,
    difficulty: int = DEFAULT_DIFFICULTY,
) -> TrainerSpot | None:
    query = select(PreflopChart).order_by(PreflopChart.id)
    if filters.get("formats"):
        query = query.where(PreflopChart.game_format.in_(filters["formats"]))
    if filters.get("positions"):
        query = query.where(PreflopChart.position.in_(filters["positions"]))
    if filters.get("situations"):
        query = query.where(PreflopChart.situation.in_(filters["situations"]))
    pushfold_max = get_settings().pushfold_max_bb
    charts: list[tuple[PreflopChart, Situation]] = []
    for chart in session.scalars(query):
        situation = _chart_usable(chart)
        if situation is None:
            continue
        if filters.get("stack_buckets"):
            pf = GameFormat(chart.game_format) in TOURNAMENT_FORMATS and (
                chart.stack_bb <= pushfold_max
            )
            if stack_bucket(chart.stack_bb, pf) not in filters["stack_buckets"]:
                continue
        charts.append((chart, situation))
    if not charts:
        return None
    chart, situation = rng.choice(charts)
    order = preflop_order(chart.players)
    vs = chart.vs_position or next(p for p in reversed(order) if p != chart.position)
    hand = pick_hand(rng, combos_per_class(), chart_frontier(chart.actions), difficulty)
    scenario = Scenario(
        format=GameFormat(chart.game_format),
        num_players=chart.players,
        hero_position=chart.position,
        hero_hand=hand,
        villains=[Villain(position=vs)],
        situation=situation,
        effective_stack_bb=chart.stack_bb,
        ante_bb=chart.ante_bb,
    )
    present = [a for a, freqs in chart.actions.items() if a != "fold" and any(f > 0 for f in freqs)]
    return _finish(TrainerSpot("chart", scenario, ["fold", *present], "", chart.id))
