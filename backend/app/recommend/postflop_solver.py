"""Heads-up postflop recommendation from TexasSolver (cached) or a pending solve."""

from __future__ import annotations

from dataclasses import dataclass

import pokercore
from sqlalchemy.orm import Session

from app.domain.cards import parse_cards
from app.domain.positions import postflop_order
from app.domain.scenario import Scenario
from app.recommend.schemas import ActionOut, PendingJobOut, RecommendationOut, StrategyLayerOut
from app.simulator.outs import showdown_share
from app.solver.cache import CachedResult, get_result
from app.solver.output_parser import StrategyNode, canonical_combo, find_hero_node
from app.solver.queue import Origin, enqueue, queue_position
from app.solver.spot import Side, SolverSpot, facing_pct, to_solver_range
from app.solver.trees import get_preset
from app.solver.worker_registry import solver_available

AGGRESSIVE = {"bet", "raise", "allin"}
FIRST_DECISION = "Solo primera decisión de la calle: raises y re-raises previos no se modelan."


@dataclass
class BuiltSpot:
    spot: SolverSpot
    hero: Side
    facing_bet_bb: float
    approximated: list[str]


def hero_side(scenario: Scenario) -> Side:
    order = postflop_order(scenario.num_players)
    villain = scenario.villains[0].position
    if not scenario.hero_position or not villain:
        raise ValueError("Indicá las posiciones de Hero y del rival para usar el solver.")
    return "oop" if order.index(scenario.hero_position) < order.index(villain) else "ip"


def build_solver_spot(scenario: Scenario) -> BuiltSpot:
    hero = hero_side(scenario)
    if not scenario.hero_range:
        raise ValueError(
            "Cargá el rango de Hero (o prellenalo desde las tablas) para usar el solver."
        )
    hero_r = to_solver_range(scenario.hero_range)
    villain_r = to_solver_range(scenario.villains[0].range)
    approximated = []
    if hero_r.approximated:
        approximated.append(
            "Rango de Hero promediado por clase (el solver no acepta combos sueltos)."
        )
    if villain_r.approximated:
        approximated.append(
            "Rango rival promediado por clase (el solver no acepta combos sueltos)."
        )

    to_call = scenario.to_call_bb
    pot_before = scenario.pot_bb - to_call
    if pot_before <= 0:
        raise ValueError("El pote antes de la apuesta debe ser mayor que 0.")
    villain_side: Side = "ip" if hero == "oop" else "oop"
    facing = to_call > 0 and to_call < scenario.effective_stack_bb
    spot = SolverSpot(
        board=tuple(parse_cards(scenario.board)),
        pot_bb=round(pot_before, 2),
        stack_bb=round(scenario.effective_stack_bb, 2),
        range_oop=hero_r.text if hero == "oop" else villain_r.text,
        range_ip=villain_r.text if hero == "oop" else hero_r.text,
        preset=get_preset(scenario.solver_preset),
        bettor=villain_side if facing else None,
        facing_bet_pct=facing_pct(to_call, pot_before) if facing else None,
    )
    return BuiltSpot(spot, hero, to_call, approximated)


def _unavailable(message: str) -> RecommendationOut:
    return RecommendationOut(available=False, message=message, source="solver")


def _range_weights(range_text: str, dead: str) -> dict[str, float]:
    return {canonical_combo(c): w for c, w in pokercore.range_combos(range_text, dead)}


def _explain(scenario: Scenario, node: StrategyNode, freqs: list[float]) -> list[str]:
    out = []
    main = max(range(len(freqs)), key=freqs.__getitem__)
    if sorted(freqs)[-1] < 0.85:
        out.append("Estrategia mixta: alterná las acciones según sus frecuencias.")
    strength = pokercore.hand_strength(
        scenario.hero_hand, scenario.villains[0].range, scenario.board
    )
    share = showdown_share(strength) if strength.combos > 0 else None
    kind = node.actions[main].kind
    if kind in AGGRESSIVE:
        if share is None:
            pass
        elif share >= 0.6:
            out.append("Valor: tu mano le gana a la mayor parte del rango rival que paga.")
        else:
            out.append("Bluff/semi-bluff: poca equity al showdown, apuesta por fold equity.")
    elif kind == "call":
        out.append("Bluff-catcher / realización de equity: pagar rinde más que subir o foldear.")
    elif kind == "check":
        out.append("Check: la mano rinde más controlando el pote que apostando.")
    return out


def _from_cache(scenario: Scenario, built: BuiltSpot, cached: CachedResult) -> RecommendationOut:
    hero_node = find_hero_node(cached.tree, built.hero, built.facing_bet_bb)
    node = hero_node.node
    warnings = [FIRST_DECISION, *hero_node.warnings, *built.approximated]
    hero_range_text = built.spot.range_oop if node.player == "oop" else built.spot.range_ip
    weights = _range_weights(hero_range_text, scenario.board)
    combo = canonical_combo(scenario.hero_hand)
    pot = built.spot.pot_bb
    if combo in node.strategy:
        freqs = node.strategy[combo]
    else:
        freqs = node.range_mix(weights)
        warnings.append(
            "Tu mano no está en tu rango: se muestra la estrategia del rango. "
            "Agregala al rango para ver la suya."
        )
    layers = node.class_layers(weights)
    exact = not built.approximated and not scenario.ranges_approximate
    expl = cached.exploitability
    return RecommendationOut(
        available=True,
        source="solver",
        confidence="exact" if exact else "approximate",
        actions=[
            ActionOut(action=a.kind, frequency=f, label=a.label(pot), amount_bb=a.amount_bb)
            for a, f in zip(node.actions, freqs, strict=True)
        ],
        reference=(
            f"TexasSolver · preset {built.spot.preset.label} · explotabilidad {expl:.2f}% del pote"
            if expl is not None
            else "TexasSolver"
        ),
        explanation=_explain(scenario, node, freqs),
        warnings=warnings,
        strategy_grid=[
            StrategyLayerOut(action=a.kind, label=a.label(pot), grid=g)
            for a, g in zip(node.actions, layers, strict=True)
        ],
    )


def recommend_solver(scenario: Scenario, session: Session) -> RecommendationOut:
    try:
        built = build_solver_spot(scenario)
    except ValueError as e:
        return _unavailable(str(e))
    cached = get_result(session, built.spot.spot_hash())
    if cached is not None:
        try:
            return _from_cache(scenario, built, cached)
        except ValueError as e:
            return _unavailable(str(e))
    if not solver_available():
        return _unavailable(
            "El solver no está configurado: definí POKER_SOLVER_PATH con la ruta de "
            "console_solver.exe de TexasSolver."
        )
    job = enqueue(session, built.spot, Origin.SIMULATOR)
    return RecommendationOut(
        available=False,
        source="solver",
        message="Resolviendo el spot con el solver…",
        pending_job=PendingJobOut(
            id=job.id,
            status=job.status,
            iteration=job.iteration,
            exploitability=job.exploitability,
            position=queue_position(session, job),
        ),
    )
