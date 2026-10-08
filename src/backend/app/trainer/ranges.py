"""'Pintá tu rango' drill: pick a chart/action and score a painted range against it."""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PreflopChart
from app.recommend.preflop_equity import class_names, combos_per_class
from app.trainer.srs import Verdict

SITUATION_LABELS = {
    "rfi": "RFI",
    "vs_open": "vs open",
    "vs_3bet": "vs 3-bet",
    "vs_4bet": "vs 4-bet",
    "squeeze": "squeeze",
    "bvb": "ciega vs ciega",
    "vs_allin": "vs all-in",
}
CORRECT_AT = 0.9
ACCEPTABLE_AT = 0.75
TOP_CLASSES = 10


@dataclass(frozen=True)
class RangeDrill:
    chart_id: int
    action: str
    title: str
    card_key: str


@dataclass(frozen=True)
class RangeScore:
    precision: float
    error: float
    verdict: Verdict
    diff_grid: list[float]
    top_classes: list[dict]


def generate_range_drill(session: Session, rng: random.Random, filters: dict) -> RangeDrill | None:
    query = select(PreflopChart).order_by(PreflopChart.id)
    if filters.get("formats"):
        query = query.where(PreflopChart.game_format.in_(filters["formats"]))
    if filters.get("positions"):
        query = query.where(PreflopChart.position.in_(filters["positions"]))
    if filters.get("situations"):
        query = query.where(PreflopChart.situation.in_(filters["situations"]))
    charts = [
        (c, [a for a, freqs in c.actions.items() if any(f > 0 for f in freqs)])
        for c in session.scalars(query)
    ]
    charts = [(c, actions) for c, actions in charts if actions]
    if not charts:
        return None
    chart, actions = rng.choice(charts)
    action = rng.choice(sorted(actions))
    situation = SITUATION_LABELS.get(chart.situation, chart.situation)
    title = (
        f"Pintá el rango de {action}: {chart.position} {situation} · "
        f"{chart.game_format} {chart.players} jugadores · {chart.stack_bb:g}bb"
    )
    return RangeDrill(chart.id, action, title, f"range|{chart.id}|{action}")


def score_range(target: list[float], painted: list[float]) -> RangeScore:
    if len(painted) != 169 or any(not 0 <= v <= 1 for v in painted):
        raise ValueError("El rango pintado debe tener 169 valores entre 0 y 1")
    t = np.asarray(target, float)
    p = np.asarray(painted, float)
    combos = combos_per_class()
    diff = p - t
    denom = float((combos * np.maximum(t, p)).sum())
    error = float((combos * np.abs(diff)).sum()) / denom if denom > 0 else 0.0
    precision = 1.0 - error
    verdict: Verdict = (
        "correct"
        if precision >= CORRECT_AT
        else "acceptable"
        if precision >= ACCEPTABLE_AT
        else "error"
    )
    weights = combos * np.abs(diff)
    names = class_names()
    order = sorted(range(169), key=lambda i: (-weights[i], i))[:TOP_CLASSES]
    top = [
        {
            "hand_class": names[i],
            "target": float(t[i]),
            "painted": float(p[i]),
            "weight": float(weights[i]),
        }
        for i in order
        if weights[i] > 0
    ]
    return RangeScore(precision, error, verdict, [float(d) for d in diff], top)
