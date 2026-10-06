from datetime import UTC, datetime

import pytest

from app.stats.engine import mean_ci, wilson
from tests.fake_parser import fake_file
from tests.hands import act, make_hand


def test_wilson_and_mean_intervals():
    p, lo, hi = wilson(30, 100)
    assert (
        p == 0.3 and lo == pytest.approx(0.2189, abs=1e-3) and hi == pytest.approx(0.3958, abs=1e-3)
    )
    assert wilson(0, 0) == (None, None, None)
    mean, lo, hi = mean_ci(total=10, total_sq=110, n=10)  # values: ten draws averaging 1
    assert mean == 1 and lo < 1 < hi


def open_fold(i: int, position_button: str = "Hero"):
    """Hero opens and takes the blinds."""
    return make_hand(
        {"Hero": 100, "SB_p": 100, "BB_p": 100},
        [
            act("p", "Hero", "raise", 2.5),
            act("p", "SB_p", "fold"),
            act("p", "BB_p", "fold"),
            act("p", "Hero", "return", 1.5),
        ],
        button=position_button,
        hand_id=str(i),
        site="fake",
        collected={"Hero": 2.5},
        played_at=datetime(2026, 1 + i % 2, 1, tzinfo=UTC),
    )


def fold_bb(i: int):
    return make_hand(
        {"V": 100, "SB_p": 100, "Hero": 100},
        [act("p", "V", "raise", 2.5), act("p", "SB_p", "fold"), act("p", "Hero", "fold")],
        button="V",
        hand_id=f"b{i}",
        site="fake",
        collected={"V": 4.0},
        game_type="mtt",
    )


@pytest.fixture
def loaded(client, fake_room):
    hands = [open_fold(i) for i in range(30)] + [fold_bb(i) for i in range(10)]
    resp = client.post(
        "/api/imports", files=[("files", ("a.txt", fake_file(*hands), "text/plain"))]
    )
    assert resp.json()["report"]["totals"]["imported"] == 40
    return client


def metric(group, key):
    return next(m for m in group["metrics"] if m["key"] == key)


def test_stats_totals_with_sample_and_ci(loaded):
    data = loaded.get("/api/stats").json()
    assert data["min_sample"] == 100
    total = data["groups"][0]
    assert total["group"] == "Total" and total["hands"] == 40
    vpip = metric(total, "vpip")
    assert vpip["value"] == pytest.approx(75.0) and vpip["n"] == 40
    assert vpip["ci_low"] < 75 < vpip["ci_high"]
    assert vpip["insufficient"] is True  # 40 < 100
    winrate = metric(total, "winrate")
    assert winrate["value"] == pytest.approx((30 * 1.5 - 10 * 1) / 40 * 100)
    assert winrate["unit"] == "bb/100"


def test_stats_group_by_and_filters(loaded):
    by_pos = loaded.get("/api/stats", params={"group_by": "position"}).json()["groups"]
    assert {g["group"]: g["hands"] for g in by_pos} == {"BTN": 30, "BB": 10}
    pfr_bb = metric(next(g for g in by_pos if g["group"] == "BB"), "pfr")
    assert pfr_bb["value"] == 0

    mtt = loaded.get("/api/stats", params={"game_types": ["mtt"]}).json()["groups"][0]
    assert mtt["hands"] == 10

    by_month = loaded.get("/api/stats", params={"group_by": "month"}).json()["groups"]
    assert {g["group"] for g in by_month} == {"2026-01", "2026-02"}

    by_stack = loaded.get("/api/stats", params={"group_by": "stack"}).json()["groups"]
    assert [g["group"] for g in by_stack] == [">=100bb"]

    none = loaded.get("/api/stats", params={"positions": ["CO"]}).json()["groups"]
    assert none == []


def test_winnings_graph(loaded):
    points = loaded.get("/api/stats/graph").json()
    assert points[0]["hand"] == 0
    assert points[-1]["hand"] == 40
    assert points[-1]["net"] == pytest.approx(30 * 1.5 - 10)
    assert points[-1]["non_showdown"] == pytest.approx(points[-1]["net"])
    assert points[-1]["showdown"] == 0


def test_tournament_stats(client, fake_room):
    from app.domain.hand import TournamentInfo

    def last_hand(tid: str, finish: int, prize: float):
        h = fold_bb(int(tid))
        return h.model_copy(
            update={
                "hand_id": f"t{tid}",
                "tournament": TournamentInfo(
                    tournament_id=tid, buy_in=9, fee=1, finish=finish, prize=prize
                ),
            }
        )

    hands = [last_hand("1", 1, 50), last_hand("2", 7, 0), last_hand("3", 9, 0)]
    client.post("/api/imports", files=[("files", ("t.txt", fake_file(*hands), "text/plain"))])
    t = client.get("/api/stats/tournaments").json()
    assert t["tournaments"] == 3 and t["cost"] == 30 and t["prizes"] == 50
    assert t["roi"]["value"] == pytest.approx(20 / 30 * 100)
    assert t["itm"]["value"] == pytest.approx(100 / 3)
    assert t["chips_per_tournament"]["n"] == 3
    assert client.get("/api/stats/tournaments", params={"game_types": ["cash"]}).json() is None
