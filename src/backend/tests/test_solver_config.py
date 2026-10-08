from pathlib import Path

from app.solver.config_gen import chips, generate_config
from app.solver.spot import SolverSpot, to_solver_range
from app.solver.trees import get_preset

FIXTURES = Path(__file__).parent / "fixtures" / "solver"
OOP = to_solver_range("AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5").text
IP = to_solver_range("AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s").text


def test_river_matches_fixture():
    spot = SolverSpot(("Qs", "Jh", "2h", "7c", "3d"), 20.0, 90.0, OOP, IP, get_preset("simple"))
    assert generate_config(spot, threads=6) == (FIXTURES / "river_spot.txt").read_text()


def test_turn_injects_the_faced_size_and_covers_river():
    spot = SolverSpot(
        ("Qs", "Jh", "2h", "7c"),
        20.0,
        90.0,
        OOP,
        IP,
        get_preset("chico"),
        bettor="oop",
        facing_bet_pct=50.0,
    )
    assert generate_config(spot, threads=6) == (FIXTURES / "turn_spot.txt").read_text()


def test_injected_size_already_in_preset_is_not_duplicated():
    spot = SolverSpot(
        ("Qs", "Jh", "2h", "7c", "3d"),
        20.0,
        90.0,
        OOP,
        IP,
        get_preset("simple"),
        bettor="ip",
        facing_bet_pct=50.0,
    )
    text = generate_config(spot, threads=2)
    assert "set_bet_sizes ip,river,bet,50,100\n" in text


def test_chips_scale():
    assert chips(20.0) == 2000
    assert chips(0.125) == 12
