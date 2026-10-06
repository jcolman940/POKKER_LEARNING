import numpy as np
import pytest

from app.recommend.preflop_equity import (
    class_index,
    combos_per_class,
    grid_to_text,
    hand_class,
    preflop_equity,
    range_vector,
)
from app.recommend.pushfold import PushFoldSpot, solve_push_fold

WEIGHTS = combos_per_class() / 1326


def share(grid: np.ndarray) -> float:
    return float(WEIGHTS @ grid)


def test_hand_class_and_grid_text():
    assert hand_class("AhKh") == "AKs"
    assert hand_class("Kd As") == "AKo"
    assert hand_class("7c7d") == "77"
    text = grid_to_text(range_vector("QQ+, AKs:0.5"))
    assert text == "AA,AKs:0.5,KK,QQ"
    assert np.allclose(range_vector(text), range_vector("QQ+, AKs:0.5"))


def test_preflop_equity_card_removal():
    pe = preflop_equity()
    i = class_index()
    assert pe.compat.sum() == 1326 * 1225
    assert pe.compat[i["AA"], i["AA"]] == 6
    assert pe.compat[i["AKs"], i["AA"]] == 12
    assert pe.equity[i["AA"], i["KK"]] == pytest.approx(0.82, abs=0.005)
    assert pe.vs_range(np.ones(169))[i["AA"]] == pytest.approx(0.852, abs=0.003)
    # Holding an ace makes the villain less likely to hold AA.
    aa = range_vector("AA")
    assert pe.play_probability(aa)[i["AKo"]] < pe.play_probability(aa)[i["KQo"]]


@pytest.mark.parametrize(("stack", "push", "call"), [(10, 0.577, 0.370), (20, 0.40, 0.22)])
def test_heads_up_chip_ev_matches_published_nash(stack, push, call):
    r = solve_push_fold(PushFoldSpot(stacks=[stack, stack]))
    assert r.converged
    assert share(r.push["BTN"]) == pytest.approx(push, abs=0.02)
    assert share(r.call[("BTN", "BB")]) == pytest.approx(call, abs=0.02)
    i = class_index()
    assert r.push["BTN"][i["AA"]] == 1.0 and r.push["BTN"][i["72o"]] == 0.0


def test_full_table_ranges_widen_towards_the_button():
    r = solve_push_fold(PushFoldSpot(stacks=[12] * 6, ante=0.125))
    shares = [share(r.push[p]) for p in ["LJ", "HJ", "CO", "BTN", "SB"]]
    assert shares == sorted(shares)
    assert r.unit == "bb"


def test_icm_tightens_calls_on_the_bubble():
    stacks = [20, 20, 20, 20]
    chip = solve_push_fold(PushFoldSpot(stacks=stacks))
    icm = solve_push_fold(PushFoldSpot(stacks=stacks, payouts=[50, 30, 20]))
    assert icm.unit == "$"
    assert share(icm.call[("CO", "BB")]) < share(chip.call[("CO", "BB")])
    assert share(icm.push["CO"]) < share(chip.push["CO"])


def test_invalid_spots():
    with pytest.raises(ValueError):
        solve_push_fold(PushFoldSpot(stacks=[10]))
    with pytest.raises(ValueError):
        solve_push_fold(PushFoldSpot(stacks=[10, 0]))


def test_pushfold_api(client):
    resp = client.post("/api/pushfold/solve", json={"stacks_bb": [10, 10, 10], "payouts": [65, 35]})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["positions"] == ["BTN", "SB", "BB"]
    assert data["unit"] == "$"
    assert [p["position"] for p in data["push"]] == ["BTN", "SB"]
    assert {(c["vs_position"], c["position"]) for c in data["call"]} == {
        ("BTN", "SB"),
        ("BTN", "BB"),
        ("SB", "BB"),
    }
    assert sum(data["icm_equity"]) == pytest.approx(100)
    assert len(data["push"][0]["grid"]) == 169

    bad = client.post("/api/pushfold/solve", json={"stacks_bb": [10, 10], "payouts": [1, 1, 1]})
    assert bad.status_code == 422
