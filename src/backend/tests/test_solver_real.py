import os
from pathlib import Path

import pytest

from app.domain.scenario import Scenario, Villain
from app.recommend.postflop_solver import build_solver_spot, recommend_solver
from app.solver.queue import JobStatus, Origin, SolverWorker, enqueue

SOLVER = os.environ.get("POKER_SOLVER_PATH")
pytestmark = [
    pytest.mark.solver,
    pytest.mark.skipif(
        not SOLVER or not Path(SOLVER).is_file(),
        reason="POKER_SOLVER_PATH no definido o no apunta a un archivo",
    ),
]


def test_real_river_solve_end_to_end(db_session, tmp_path):
    from app.db.session import _session_factory

    scenario = Scenario(
        num_players=6,
        hero_position="BTN",
        hero_hand="AhKc",
        hero_range="AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s",
        villains=[Villain(position="BB", range="AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5")],
        board="QsJh2h7c3d",
        pot_bb=30.0,
        to_call_bb=10.0,
        effective_stack_bb=90.0,
    )
    built = build_solver_spot(scenario)
    job = enqueue(db_session, built.spot, Origin.SIMULATOR)
    worker = SolverWorker(
        _session_factory(), Path(SOLVER), tmp_path, threads=os.cpu_count() or 2, timeout_s=600
    )
    assert worker.run_once()
    db_session.refresh(job)
    assert job.status == JobStatus.DONE, job.error
    assert job.exploitability is not None and job.exploitability < 2.0

    rec = recommend_solver(scenario, db_session)
    assert rec.available and rec.source == "solver"
    assert {a.action for a in rec.actions} >= {"call", "fold"}
    assert sum(a.frequency for a in rec.actions) == pytest.approx(1.0, abs=1e-3)
