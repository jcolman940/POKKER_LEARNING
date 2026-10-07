import json
from pathlib import Path

from app.db.models import SolverJob
from app.db.session import _session_factory
from app.solver.cache import store_result
from app.solver.flops import representative_flops
from app.solver.output_parser import parse_output
from app.solver.queue import JobStatus, Origin, enqueue
from app.solver.runner import Progress
from app.solver.spot import SolverSpot, to_solver_range
from app.solver.trees import get_preset

FIXTURES = Path(__file__).parent / "fixtures" / "solver"


def river_spot():
    return SolverSpot(
        ("Qs", "Jh", "2h", "7c", "3d"),
        20.0,
        90.0,
        to_solver_range("AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5").text,
        to_solver_range("AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s").text,
        get_preset("simple"),
    )


def store(spot):
    tree = parse_output(json.loads((FIXTURES / "river_out.json").read_text()), 90.0)
    with _session_factory()() as s:
        store_result(s, spot, tree, Progress(200, 0.4, 1), 18.0)


def test_status_without_solver(client):
    body = client.get("/api/solver/status").json()
    assert body["configured"] is False
    assert {p["name"] for p in body["presets"]} == {"simple", "chico", "amplio"}
    assert body["cache_entries"] == 0


def test_pause_resume(client):
    assert client.post("/api/solver/queue/pause").json() == {"paused": True}
    assert client.get("/api/solver/status").json()["paused"] is True
    assert client.post("/api/solver/queue/resume").json() == {"paused": False}


def test_jobs_lifecycle(client):
    with _session_factory()() as s:
        job_id = enqueue(s, river_spot(), Origin.BATCH).id
    jobs = client.get("/api/solver/jobs").json()
    assert jobs[0]["id"] == job_id and jobs[0]["position"] == 1
    assert client.post(f"/api/solver/jobs/{job_id}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/solver/jobs/{job_id}/retry").json()["status"] == "queued"
    assert client.get("/api/solver/jobs/999").status_code == 404


def test_jobs_running_before_queued(client):
    other = SolverSpot(
        ("Qs", "Jh", "2h", "7c", "3d"),
        21.0,
        90.0,
        river_spot().range_oop,
        river_spot().range_ip,
        get_preset("simple"),
    )
    with _session_factory()() as s:
        first = enqueue(s, river_spot(), Origin.BATCH).id
        second = enqueue(s, other, Origin.BATCH).id
        # Make the later job outrank the earlier one, then mark the earlier one running.
        s.get(SolverJob, second).priority = 0
        s.get(SolverJob, first).status = JobStatus.RUNNING
        s.commit()
    jobs = client.get("/api/solver/jobs").json()
    assert [j["id"] for j in jobs[:2]] == [first, second]
    assert jobs[0]["status"] == "running"


def test_node_navigation(client):
    spot = river_spot()
    store(spot)
    root = client.get(f"/api/solver/results/{spot.spot_hash()}/node").json()
    assert root["player"] == "oop" and root["path"] == ""
    assert abs(sum(a["frequency"] for a in root["actions"]) - 1) < 1e-3
    check = next(a for a in root["actions"] if a["kind"] == "check")
    child = client.get(
        f"/api/solver/results/{spot.spot_hash()}/node", params={"path": str(check["index"])}
    ).json()
    assert child["player"] == "ip"
    assert len(child["layers"][0]["grid"]) == 169
    assert client.get(f"/api/solver/results/{spot.spot_hash()}/node?path=9.9").status_code == 404


def test_cache_delete(client):
    spot = river_spot()
    store(spot)
    assert client.get("/api/solver/status").json()["cache_entries"] == 1
    assert client.delete(f"/api/solver/cache/{spot.spot_hash()}").status_code == 204
    assert client.delete(f"/api/solver/cache/{spot.spot_hash()}").status_code == 404
    store(spot)
    assert client.delete("/api/solver/cache").json() == {"deleted": 1}


def test_library_reports_missing_charts(client):
    body = client.get("/api/solver/library").json()
    assert {f["id"] for f in body} == {"mtt", "cash"}
    line = body[1]["lines"][0]
    assert line["missing"] and line["entries"][0]["status"] == "missing_chart"
    r = client.post("/api/solver/library/enqueue", json={"family": "cash", "line": "btn_bb"}).json()
    assert r["enqueued"] == 0 and r["missing"]


def test_batch_validates_flops(client):
    body = {
        "game_format": "cash",
        "players": 6,
        "preset": "simple",
        "line": {
            "aggressor": "BTN",
            "caller": "BB",
            "pot_type": "srp",
            "stack_bb": 100,
            "open_size_bb": 2.5,
        },
        "flops": ["AhK"],
    }
    assert client.post("/api/solver/batch", json=body).status_code == 422
    body["flops"] = representative_flops()[:1]
    r = client.post("/api/solver/batch", json=body).json()
    assert r["enqueued"] == 0 and r["missing"]


def test_prefill_endpoint(client):
    r = client.post(
        "/api/solver/prefill-ranges",
        json={
            "game_format": "cash",
            "players": 6,
            "aggressor": "BTN",
            "caller": "BB",
            "pot_type": "srp",
            "stack_bb": 100,
        },
    ).json()
    assert r["aggressor"]["text"] is None and r["aggressor"]["missing"] == "BTN RFI"


def test_simulator_postflop_without_solver(client):
    r = client.post(
        "/api/simulator/analyze",
        json={
            "num_players": 6,
            "hero_position": "BB",
            "hero_hand": "QhQc",
            "hero_range": "AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5",
            "villains": [{"position": "BTN", "range": "AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s"}],
            "board": "QsJh2h7c3d",
            "pot_bb": 20,
            "to_call_bb": 0,
            "effective_stack_bb": 90,
        },
    ).json()
    assert r["recommendation"]["available"] is False
    assert "POKER_SOLVER_PATH" in r["recommendation"]["message"]
