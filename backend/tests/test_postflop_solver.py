import json
from pathlib import Path

import pytest

from app.domain.scenario import Scenario, Villain
from app.recommend.postflop_solver import build_solver_spot, hero_side, recommend_solver
from app.solver.cache import store_result
from app.solver.output_parser import parse_output
from app.solver.runner import Progress

FIXTURES = Path(__file__).parent / "fixtures" / "solver"
OOP = "AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5"
IP = "AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s"


def scenario(**kw):
    base = dict(
        num_players=6,
        hero_position="BB",
        hero_hand="QhQc",
        hero_range=OOP,
        villains=[Villain(position="BTN", range=IP)],
        board="QsJh2h7c3d",
        pot_bb=20.0,
        to_call_bb=0.0,
        effective_stack_bb=90.0,
    )
    base.update(kw)
    return Scenario(**base)


def cache_river(session):
    built = build_solver_spot(scenario())
    tree = parse_output(json.loads((FIXTURES / "river_out.json").read_text()), 90.0)
    store_result(session, built.spot, tree, Progress(200, 0.42, 1), 18.0)
    return built


def test_hero_side():
    assert hero_side(scenario()) == "oop"
    assert (
        hero_side(scenario(hero_position="BTN", villains=[Villain(position="BB", range=OOP)]))
        == "ip"
    )


def test_spot_puts_ranges_on_the_right_side():
    built = build_solver_spot(
        scenario(hero_position="BTN", hero_range=IP, villains=[Villain(position="BB", range=OOP)])
    )
    assert built.hero == "ip"
    assert built.spot.range_oop.startswith("AQs")
    assert built.spot.range_ip.startswith("AA")


def test_facing_bet_injects_size_and_uses_pot_before_bet():
    built = build_solver_spot(scenario(pot_bb=30.0, to_call_bb=10.0))
    assert built.spot.pot_bb == 20.0
    assert built.spot.bettor == "ip"
    assert built.spot.facing_bet_pct == 50.0
    assert built.facing_bet_bb == 10.0


def test_missing_hero_range(db_session):
    rec = recommend_solver(scenario(hero_range=None), db_session)
    assert not rec.available and "rango de Hero" in rec.message


def test_missing_positions(db_session):
    rec = recommend_solver(scenario(hero_position=None), db_session)
    assert not rec.available and "posiciones" in rec.message


def test_uncached_without_solver_explains_configuration(db_session, monkeypatch):
    monkeypatch.setattr("app.recommend.postflop_solver.solver_available", lambda: False)
    rec = recommend_solver(scenario(), db_session)
    assert not rec.available and "POKER_SOLVER_PATH" in rec.message


def test_uncached_enqueues_a_simulator_job(db_session, monkeypatch):
    monkeypatch.setattr("app.recommend.postflop_solver.solver_available", lambda: True)
    rec = recommend_solver(scenario(), db_session)
    assert not rec.available
    assert rec.source == "solver"
    assert rec.pending_job.status == "queued" and rec.pending_job.position == 1


def test_cached_spot_returns_hero_combo_strategy(db_session):
    cache_river(db_session)
    rec = recommend_solver(scenario(), db_session)
    assert rec.available and rec.source == "solver" and rec.confidence == "exact"
    assert sum(a.frequency for a in rec.actions) == pytest.approx(1.0, abs=1e-3)
    assert {a.action for a in rec.actions} <= {"check", "bet", "allin"}
    assert len(rec.strategy_grid) == len(rec.actions)
    assert all(len(layer.grid) == 169 for layer in rec.strategy_grid)
    assert "explotabilidad" in rec.reference
    assert any("primera decisión" in w for w in rec.warnings)


def test_hand_outside_range_shows_range_strategy(db_session):
    cache_river(db_session)
    rec = recommend_solver(scenario(hero_hand="8s6s"), db_session)
    assert rec.available
    assert any("no está en tu rango" in w for w in rec.warnings)


def test_approximate_when_ranges_flagged(db_session):
    cache_river(db_session)
    rec = recommend_solver(scenario(ranges_approximate=True), db_session)
    assert rec.confidence == "approximate"
