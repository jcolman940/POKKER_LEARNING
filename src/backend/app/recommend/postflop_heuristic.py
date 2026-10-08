"""Multiway postflop (3+ players): own equity-based heuristics, always approximate.

Inputs: hero's equity against every range at once and, per villain, the share of the
range hero beats right now. Thresholds come from settings (`heuristic_*`) and are cited
as "umbral heurístico" in the explanation: they are not solver output.
"""

from __future__ import annotations

import pokercore

from app.config import get_settings
from app.domain.metrics import pot_metrics
from app.domain.positions import postflop_order
from app.domain.scenario import Scenario
from app.recommend.schemas import ActionOut, RecommendationOut
from app.simulator.outs import compute_outs, showdown_share

THRESHOLD_NOTE = "umbral heurístico, no sale de un solver"


def _hero_is_last(scenario: Scenario) -> bool:
    positions = [scenario.hero_position, *(v.position for v in scenario.villains)]
    if not all(positions):
        return False
    order = postflop_order(scenario.num_players)
    return max(positions, key=order.index) == scenario.hero_position


def _pick(primary: str, secondary: str, near: bool) -> list[ActionOut]:
    if near:
        return [
            ActionOut(action=primary, frequency=0.5),
            ActionOut(action=secondary, frequency=0.5),
        ]
    return [ActionOut(action=primary, frequency=1.0), ActionOut(action=secondary, frequency=0.0)]


def recommend_heuristic(scenario: Scenario) -> RecommendationOut:
    s = get_settings()
    ranges = [v.range for v in scenario.villains]
    shares = [
        showdown_share(pokercore.hand_strength(scenario.hero_hand, r, scenario.board))
        for r in ranges
    ]
    min_share = min(shares)
    equity = (
        pokercore.equity(
            [scenario.hero_hand, *ranges],
            scenario.board,
            iterations=s.equity_iterations,
            exact_limit=s.equity_exact_limit,
        )
        .players[0]
        .equity
    )
    last = _hero_is_last(scenario)
    outs = compute_outs(scenario.hero_hand, ranges, scenario.board)
    explanation: list[str] = []
    warnings: list[str] = []

    if scenario.to_call_bb <= 0:
        near = abs(min_share - s.heuristic_value_share) < s.heuristic_margin
        if min_share >= s.heuristic_value_share or near:
            actions = _pick("bet", "check", near)
            explanation.append(
                f"Valor: le ganás a ≥ {s.heuristic_value_share:.0%} de cada rango "
                f"({THRESHOLD_NOTE})."
            )
        elif outs.available and outs.count >= s.heuristic_semibluff_outs and last:
            actions = _pick("bet", "check", False)
            explanation.append(f"Semi-bluff: {outs.count} outs y actuás último ({THRESHOLD_NOTE}).")
        else:
            actions = _pick("check", "bet", False)
            explanation.append("Check: sin valor claro contra todos los rangos ni draw fuerte.")
        if near:
            warnings.append("Spot cerca del umbral: mezclá las dos acciones.")
    else:
        metrics = pot_metrics(scenario.pot_bb, scenario.to_call_bb, scenario.effective_stack_bb)
        factor = s.heuristic_realization_last if last else s.heuristic_realization_oop
        need = (metrics.required_equity or 0.0) / factor
        near_raise = abs(min_share - s.heuristic_raise_share) < s.heuristic_margin
        if min_share >= s.heuristic_raise_share or near_raise:
            actions = [
                ActionOut(action="raise", frequency=0.5 if near_raise else 1.0),
                ActionOut(action="call", frequency=0.5 if near_raise else 0.0),
                ActionOut(action="fold", frequency=0.0),
            ]
            explanation.append(
                f"Valor: le ganás a ≥ {s.heuristic_raise_share:.0%} de cada rango "
                f"({THRESHOLD_NOTE})."
            )
            if near_raise:
                warnings.append("Spot cerca del umbral: mezclá raise y call.")
        else:
            near_call = abs(equity - need) < s.heuristic_margin
            if equity >= need or near_call:
                call = 0.5 if near_call else 1.0
                actions = [
                    ActionOut(action="call", frequency=call),
                    ActionOut(action="fold", frequency=1.0 - call),
                ]
            else:
                actions = [
                    ActionOut(action="call", frequency=0.0),
                    ActionOut(action="fold", frequency=1.0),
                ]
            explanation.append(
                f"Pot odds: necesitás {need:.0%} de equity (ajustada por realización ×{factor:g}, "
                f"{THRESHOLD_NOTE}); tenés {equity:.0%}."
            )
            if near_call:
                warnings.append("Spot cerca del umbral: mezclá call y fold.")

    if min_share >= 0.5 and len(scenario.board) < 10 and equity < min_share - 0.1:
        explanation.append("Protección: vas adelante pero los rangos rivales tienen muchos outs.")
    if any(a.action in ("bet", "raise") and a.frequency > 0 for a in actions) and min_share < 0.5:
        if "A" in {scenario.hero_hand[0], scenario.hero_hand[2]}:
            explanation.append("Blockers: tu A reduce los combos fuertes del rival.")

    return RecommendationOut(
        available=True,
        source="heuristic",
        confidence="approximate",
        actions=actions,
        reference=(
            f"Heurística multiway: equity {equity:.0%} contra todos; le ganás a "
            f"{min_share * 100:.1f}% de cada rango (mínimo)."
        ),
        explanation=explanation,
        warnings=warnings,
    )
