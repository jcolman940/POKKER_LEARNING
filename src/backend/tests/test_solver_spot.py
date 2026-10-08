import pytest

from app.solver.spot import SolverSpot, facing_pct, to_solver_range
from app.solver.trees import get_preset

OOP = "AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5"
IP = "AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s"


def make(**kw):
    base = dict(
        board=("Qs", "Jh", "2h", "7c", "3d"),
        pot_bb=20.0,
        stack_bb=90.0,
        range_oop=to_solver_range(OOP).text,
        range_ip=to_solver_range(IP).text,
        preset=get_preset("simple"),
    )
    base.update(kw)
    return SolverSpot(**base)


def test_to_solver_range_orders_by_grid_and_keeps_weights():
    r = to_solver_range(OOP)
    assert r.text == "AQs,A5s,KQs,QJs,KJo:0.5,JTs,T9s,99,88,77,22"
    assert r.approximated is False


def test_to_solver_range_flags_combo_specific_ranges():
    r = to_solver_range("AhKh")
    assert r.text == "AKs:0.25"
    assert r.approximated is True


def test_to_solver_range_rejects_empty():
    with pytest.raises(ValueError):
        to_solver_range("AA:0")


def test_street_from_board():
    assert make().street == "river"
    assert make(board=("Qs", "Jh", "2h")).street == "flop"


def test_hash_is_stable_and_sensitive():
    assert make().spot_hash() == make().spot_hash()
    assert len(make().spot_hash()) == 64
    assert make().spot_hash() != make(pot_bb=21.0).spot_hash()
    assert make().spot_hash() != make(preset=get_preset("chico")).spot_hash()
    assert make().spot_hash() != make(bettor="oop", facing_bet_pct=50.0).spot_hash()


def test_board_order_does_not_change_the_flop_hash():
    a = make(board=("Qs", "Jh", "2h"))
    b = make(board=("2h", "Qs", "Jh"))
    assert a.spot_hash() == b.spot_hash()


def test_board_order_matters_for_turn_card():
    a = make(board=("Qs", "Jh", "2h", "7c"))
    b = make(board=("Qs", "Jh", "7c", "2h"))
    assert a.spot_hash() != b.spot_hash()


def test_json_roundtrip():
    spot = make(bettor="ip", facing_bet_pct=75.0)
    assert SolverSpot.from_json(spot.to_json()) == spot


def test_facing_pct_rounds_to_integer_percent():
    assert facing_pct(6.6, 20.0) == 33.0
    assert facing_pct(10.0, 20.0) == 50.0
