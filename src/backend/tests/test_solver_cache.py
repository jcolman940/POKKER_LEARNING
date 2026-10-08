import json
from pathlib import Path

from app.solver.cache import cache_stats, clear_cache, delete_result, get_result, store_result
from app.solver.output_parser import parse_output
from app.solver.runner import Progress
from app.solver.spot import SolverSpot, to_solver_range
from app.solver.trees import get_preset

FIXTURES = Path(__file__).parent / "fixtures" / "solver"


def spot():
    return SolverSpot(
        ("Qs", "Jh", "2h", "7c", "3d"),
        20.0,
        90.0,
        to_solver_range("AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5").text,
        to_solver_range("AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s").text,
        get_preset("simple"),
    )


def tree():
    return parse_output(json.loads((FIXTURES / "river_out.json").read_text()), 90.0)


def test_store_and_get(db_session):
    s, t = spot(), tree()
    assert get_result(db_session, s.spot_hash()) is None
    store_result(db_session, s, t, Progress(200, 0.4, 1500), solve_seconds=18.2)
    cached = get_result(db_session, s.spot_hash())
    assert cached.tree == t
    assert cached.spot == s
    assert cached.exploitability == 0.4
    assert cached.iterations == 200
    entries, size = cache_stats(db_session)
    assert entries == 1 and size > 0


def test_store_is_idempotent(db_session):
    s, t = spot(), tree()
    store_result(db_session, s, t, Progress(200, 0.4, 1), 1.0)
    store_result(db_session, s, t, Progress(200, 0.3, 1), 1.0)
    assert cache_stats(db_session)[0] == 1
    assert get_result(db_session, s.spot_hash()).exploitability == 0.3


def test_delete_and_clear(db_session):
    s, t = spot(), tree()
    store_result(db_session, s, t, Progress(), 1.0)
    assert delete_result(db_session, s.spot_hash()) is True
    assert delete_result(db_session, s.spot_hash()) is False
    store_result(db_session, s, t, Progress(), 1.0)
    assert clear_cache(db_session) == 1
    assert cache_stats(db_session) == (0, 0)
