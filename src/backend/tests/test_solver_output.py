import json
from pathlib import Path

import pytest

from app.solver.output_parser import (
    SolverAction,
    StrategyNode,
    canonical_combo,
    find_hero_node,
    parse_output,
)

FIXTURES = Path(__file__).parent / "fixtures" / "solver"


@pytest.fixture(scope="module")
def river():
    return parse_output(json.loads((FIXTURES / "river_out.json").read_text()), stack_bb=90.0)


@pytest.fixture(scope="module")
def turn():
    return parse_output(json.loads((FIXTURES / "turn_out.json").read_text()), stack_bb=90.0)


def test_canonical_combo():
    assert canonical_combo("2c2d") == "2d2c"
    assert canonical_combo("KhAh") == "AhKh"
    assert canonical_combo("AhKh") == "AhKh"


def test_root_is_oop_and_amounts_are_unscaled(river):
    assert river.player == "oop"
    assert river.actions == [
        SolverAction("check", None),
        SolverAction("bet", 10.0),
        SolverAction("bet", 20.0),
        SolverAction("allin", 90.0),
    ]


def test_strategies_are_distributions(river):
    for freqs in river.strategy.values():
        assert len(freqs) == len(river.actions)
        assert sum(freqs) == pytest.approx(1.0, abs=1e-3)
    assert all(canonical_combo(c) == c for c in river.strategy)


def test_children_alternate_players_and_stop_at_street_end(river):
    after_check = river.child("check")
    assert after_check is not None and after_check.player == "ip"
    vs_bet = river.child("bet", 10.0)
    assert vs_bet.player == "ip"
    assert {a.kind for a in vs_bet.actions} >= {"call", "fold"}
    assert vs_bet.child("call") is None  # showdown / next street: not kept


def test_turn_faced_size_was_injected(turn):
    assert SolverAction("bet", 10.0) in turn.actions  # 50% of 20bb


@pytest.mark.parametrize(
    ("hero", "facing", "expected"),
    [
        ("oop", 0.0, lambda root: root),
        ("ip", 0.0, lambda root: root.child("check")),
        ("ip", 10.0, lambda root: root.child("bet", 10.0)),
    ],
)
def test_find_hero_node(river, hero, facing, expected):
    found = find_hero_node(river, hero, facing)
    assert found.node is expected(river)
    assert found.node.player == hero
    assert found.warnings == []


def test_find_hero_node_oop_facing_bet_after_check(river):
    found = find_hero_node(river, "oop", 10.0)
    assert found.node.player == "oop"
    assert {a.kind for a in found.node.actions} >= {"call", "fold"}


def test_find_hero_node_warns_when_size_is_adjusted(river):
    found = find_hero_node(river, "ip", 11.0)
    assert found.node.player == "ip"
    assert found.warnings and "10" in found.warnings[0]


def test_dict_roundtrip(river):
    assert StrategyNode.from_dict(river.to_dict()) == river


def test_range_mix_weights_combos(river):
    combos = list(river.strategy)[:2]
    mix = river.range_mix({combos[0]: 1.0, combos[1]: 0.0})
    assert mix == pytest.approx(river.strategy[combos[0]])
