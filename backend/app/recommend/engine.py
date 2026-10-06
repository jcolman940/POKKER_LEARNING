"""Recommendation engine: picks the source for a spot and builds the common output.

Preflop:
- tournaments at <= `pushfold_max_bb` effective, folded to hero or facing a shove:
  push/fold Nash (+ ICM when payouts are given), computed on the fly.
- otherwise: the closest stored chart (marked approximate when conditions differ).
Postflop sources (solver, multiway heuristics) arrive in later phases.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.positions import preflop_order
from app.domain.scenario import TOURNAMENT_FORMATS, Scenario, Situation, Street
from app.recommend.charts import (
    AGGRESSIVE,
    SOURCE_LABEL,
    ChartQuery,
    ChartSource,
    find_chart,
)
from app.recommend.preflop_equity import (
    class_index,
    combos_per_class,
    hand_class,
    preflop_equity,
)
from app.recommend.pushfold import PushFoldResult, PushFoldSpot, solve_push_fold
from app.recommend.schemas import ActionOut, RecommendationOut

ACTION_LABEL = {
    "fold": "fold",
    "call": "call",
    "raise": "raise",
    "limp": "limp",
    "3bet": "3-bet",
    "4bet": "4-bet",
    "5bet": "5-bet",
    "allin": "all-in",
}
INDIFFERENT_EV = 0.05  # bb (or 0.05% of the prize pool) where actions are close


def unavailable(message: str) -> RecommendationOut:
    return RecommendationOut(available=False, message=message)


@lru_cache(maxsize=64)
def _solve_cached(
    stacks: tuple[float, ...], ante: float, bb_ante: float, payouts: tuple[float, ...]
) -> PushFoldResult:
    return solve_push_fold(
        PushFoldSpot(stacks=list(stacks), ante=ante, bb_ante=bb_ante, payouts=list(payouts))
    )


def solve_spot(
    stacks: list[float], ante: float, bb_ante: float, payouts: list[float]
) -> PushFoldResult:
    return _solve_cached(tuple(stacks), ante, bb_ante, tuple(payouts))


def _strength_percentile(cls: int, action_range: np.ndarray) -> float:
    """Where the hand sits inside a range, by all-in equity vs a random hand (0 = top)."""
    pe = preflop_equity()
    vs_random = pe.vs_range(np.ones(169))
    weights = action_range * combos_per_class()
    total = weights.sum()
    if total <= 0:
        return 1.0
    stronger = weights[vs_random > vs_random[cls]].sum()
    return float(stronger / total)


def _blockers(hand: str) -> str | None:
    ranks = {hand[0], hand[2]}
    if "A" in ranks:
        return "Blockers: tu A reduce los combos de AA y AK del rival."
    if "K" in ranks:
        return "Blockers: tu K reduce los combos de KK y AK del rival."
    return None


def _explain_chart(hand: str, cls: int, actions: dict[str, list[float]]) -> list[str]:
    freqs = {a: g[cls] for a, g in actions.items() if g[cls] > 0}
    fold = max(0.0, 1.0 - sum(freqs.values()))
    out: list[str] = []
    if not freqs:
        return ["La mano está fuera del rango: fold."]
    if fold > 0 or len(freqs) > 1:
        out.append("Estrategia mixta: alterná las acciones según sus frecuencias.")
    for action in freqs:
        if action in AGGRESSIVE:
            top = _strength_percentile(cls, np.asarray(actions[action]))
            if top < 0.5:
                out.append(f"Valor: la mano está en la mitad fuerte de tu rango de {action}.")
            else:
                out.append(
                    f"Bluff/semi-bluff: parte baja de tu rango de {action}, "
                    "jugable por equity y fold equity."
                )
                if blocker := _blockers(hand):
                    out.append(blocker)
        elif action in ("call", "limp"):
            out.append(
                "Equity realization: la mano rinde más viendo flop que subiendo o foldeando."
            )
    return out


def _recommend_chart(scenario: Scenario, session: Session, hand: str) -> RecommendationOut:
    assert scenario.hero_position and scenario.situation
    vs_position = scenario.villains[0].position if scenario.situation != Situation.RFI else None
    query = ChartQuery(
        game_format=scenario.format,
        players=scenario.num_players,
        position=scenario.hero_position,
        situation=scenario.situation,
        stack_bb=scenario.effective_stack_bb,
        vs_position=vs_position,
        ante_bb=scenario.ante_bb,
    )
    match = find_chart(session, query)
    if match is None:
        return unavailable(
            f"No hay rangos cargados para {scenario.hero_position} en esta situación. "
            "Cargalos en la sección Rangos preflop."
        )
    chart = match.chart
    cls_name = hand_class(hand)
    cls = class_index()[cls_name]
    actions = [ActionOut(action=a, frequency=float(g[cls])) for a, g in chart.actions.items()]
    fold = max(0.0, 1.0 - sum(a.frequency for a in actions))
    actions = [a for a in actions if a.frequency > 0] + [ActionOut(action="fold", frequency=fold)]
    actions.sort(key=lambda a: -a.frequency)

    warnings = list(match.mismatches)
    if not match.exact:
        warnings.insert(0, "El escenario no coincide con las condiciones del rango: aproximado.")
    return RecommendationOut(
        available=True,
        source="chart",
        confidence="exact" if match.exact else "approximate",
        hand_class=cls_name,
        actions=[a for a in actions if a.frequency > 0],
        reference=f"{_upper_first(SOURCE_LABEL[ChartSource(chart.source)])} · {chart.name}",
        explanation=_explain_chart(hand, cls, chart.actions),
        warnings=warnings,
    )


def _recommend_pushfold(scenario: Scenario, hand: str) -> RecommendationOut:
    assert scenario.hero_position and scenario.situation
    order = preflop_order(scenario.num_players)
    stacks = [scenario.stacks_bb.get(p, scenario.effective_stack_bb) for p in order]
    result = solve_spot(stacks, scenario.ante_bb, scenario.bb_ante_bb, scenario.payouts)
    cls_name = hand_class(hand)
    cls = class_index()[cls_name]
    hero = scenario.hero_position

    if scenario.situation == Situation.RFI:
        if hero == "BB":
            return unavailable("En el BB no hay decisión de push/fold si todos foldean.")
        freq = float(result.push[hero][cls])
        ev_act, ev_fold = result.push_ev[hero]
        act = "allin"
        detail = f"Rango de push de {hero}: {_pct(result.push[hero])} de las manos."
    else:
        pusher = scenario.villains[0].position
        if not pusher:
            return unavailable("Indicá la posición del rival que fue all-in (Rival 1).")
        if order.index(pusher) >= order.index(hero):
            return unavailable("El rival que va all-in tiene que actuar antes que Hero.")
        key = (pusher, hero)
        freq = float(result.call[key][cls])
        ev_act, ev_fold = result.call_ev[key]
        act = "call"
        detail = (
            f"Rango de push de {pusher}: {_pct(result.push[pusher])}; "
            f"rango de call de {hero}: {_pct(result.call[key])}."
        )

    diff = float(ev_act[cls]) - ev_fold
    unit = result.unit
    explanation = [
        "Equilibrio de Nash push/fold"
        + (" con ICM (premios cargados)." if scenario.payouts else " en chip EV (sin premios)."),
        detail,
    ]
    scale = sum(scenario.payouts) / 100 if scenario.payouts else 1.0
    if abs(diff) < INDIFFERENT_EV * scale:
        explanation.append("La diferencia de EV es mínima: la mano está cerca de la indiferencia.")
    else:
        better = ACTION_LABEL[act] if diff > 0 else "fold"
        explanation.append(f"{_upper_first(better)} gana {abs(diff):.2f}{unit} frente a la otra.")

    warnings = ["Modelo push/fold: un solo caller (sin overcalls)."]
    if not result.converged:
        warnings.append(
            f"El cálculo no llegó a la tolerancia (explotabilidad {result.exploitability:.3f}"
            f"{unit}): aproximado."
        )
    if not scenario.stacks_bb:
        warnings.append("Sin stacks por posición: se asumió el stack efectivo para todos.")

    return RecommendationOut(
        available=True,
        source="nash",
        confidence="exact" if result.converged else "approximate",
        hand_class=cls_name,
        actions=[
            ActionOut(action=act, frequency=freq, ev=float(ev_act[cls])),
            ActionOut(action="fold", frequency=1 - freq, ev=ev_fold),
        ],
        ev_unit=unit,
        reference="Calculado por el sistema (push/fold Nash"
        + (" + ICM)" if scenario.payouts else ")"),
        explanation=explanation,
        warnings=warnings,
    )


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def _pct(grid: np.ndarray) -> str:
    share = float(combos_per_class() @ grid / 1326)
    return f"{share * 100:.1f}%"


def recommend(scenario: Scenario, session: Session) -> RecommendationOut:
    if scenario.street != Street.PREFLOP:
        return unavailable(
            "Postflop: el solver heads-up y las heurísticas multiway llegan en la fase 5."
        )
    if not scenario.hero_position:
        return unavailable("Indicá la posición de Hero para obtener una recomendación.")
    if not scenario.situation:
        return unavailable("Indicá la situación preflop (RFI, vs open, vs 3-bet…).")

    hand = scenario.hero_hand
    pushfold = (
        scenario.format in TOURNAMENT_FORMATS
        and scenario.effective_stack_bb <= get_settings().pushfold_max_bb
        and scenario.situation in (Situation.RFI, Situation.VS_ALLIN)
    )
    if pushfold:
        return _recommend_pushfold(scenario, hand)
    return _recommend_chart(scenario, session, hand)
