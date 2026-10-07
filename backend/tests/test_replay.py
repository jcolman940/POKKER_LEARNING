import pytest

from app.domain.scenario import Scenario
from app.replay.service import build_replay
from tests.hands import act, make_hand


def cbet_hand():
    return make_hand(
        {"CO_p": 100, "Hero": 100, "SB_p": 100, "BB_p": 100},
        [
            act("p", "CO_p", "raise", 2.5),
            act("p", "Hero", "call", 2.5),
            act("p", "SB_p", "fold"),
            act("p", "BB_p", "fold"),
            act("f", "CO_p", "bet", 3),
            act("f", "Hero", "raise", 9),
            act("f", "CO_p", "fold"),
            act("f", "Hero", "return", 6),
        ],
        button="Hero",
        hero_cards="7h7d",
        board="Kd7c2s",
        collected={"Hero": 12.5},
    )


def test_replay_steps_pot_and_equity():
    replay = build_replay(cbet_hand(), {"CO_p": "TT+,AJs+,KQs,AQo+"})
    texts = [s.description for s in replay.steps]
    assert texts[0] == "Ciegas"
    assert texts[1] == "CO (CO_p) sube a 2.5bb"
    assert "Flop: Kd 7c 2s" in texts
    assert texts[-1] == "BTN (Hero) gana 12.5bb"

    first = replay.steps[0]
    assert first.pot_bb == 1.5 and first.bets_bb["BB_p"] == 1
    flop = next(s for s in replay.steps if s.description.startswith("Flop"))
    assert flop.pot_bb == pytest.approx(6.5) and flop.bets_bb["Hero"] == 0
    # Set of sevens vs a strong range on K72: big favourite.
    assert flop.hero_equity.equity > 0.8
    assert replay.result["Hero"] == pytest.approx(7.0)  # pot 12.5 - 5.5 invested
    assert replay.ranges["CO_p"] == "TT+,AJs+,KQs,AQo+"
    hero = next(p for p in replay.players if p.is_hero)
    assert hero.position == "BTN" and hero.cards == "7h7d"


def test_hero_decision_points_carry_valid_scenarios():
    replay = build_replay(cbet_hand(), {"CO_p": "QQ+"})
    points = [s for s in replay.steps if s.scenario]
    assert len(points) == 2  # preflop call and flop raise
    pre, flop = (p.scenario for p in points)
    assert pre["situation"] == "vs_open"
    assert pre["villains"][0] == {"position": "CO", "range": "QQ+", "hand": None}
    assert pre["to_call_bb"] == 2.5 and pre["pot_bb"] == 4.0
    assert flop["board"] == "Kd7c2s" and flop["to_call_bb"] == 3
    assert "CO (CO_p) apuesta 3bb" in flop["previous_action"]
    for s in (pre, flop):
        Scenario.model_validate(s)  # the simulator accepts it as-is


def test_allin_runout_reveals_board_and_situation():
    h = make_hand(
        {"V": 20, "Hero": 20},
        [act("p", "V", "raise", 19.5, all_in=True), act("p", "Hero", "call", 19, all_in=True)],
        button="V",
        hero_cards="AhAd",
        board="Kd7c2s3h9c",
        shown={"V": "KcKs"},
        collected={"V": 40},
        game_type="mtt",
    )
    replay = build_replay(h)
    texts = [s.description for s in replay.steps]
    assert texts[-4:-1] == ["Flop: Kd 7c 2s", "Turn: 3h", "River: 9c"] or texts[-4].startswith(
        "Flop"
    )
    decision = next(s for s in replay.steps if s.scenario)
    assert decision.scenario["situation"] == "vs_allin"
    assert decision.scenario["villains"][0]["hand"] == "KcKs"  # informative only
    assert decision.scenario["stacks_bb"] == {"BTN": 20, "BB": 20}
    assert next(p for p in replay.players if p.name == "V").cards == "KcKs"


def test_replay_api(client, fake_room):
    from tests.fake_parser import fake_file

    h = cbet_hand().model_copy(update={"site": "fake"})
    client.post("/api/imports", files=[("files", ("a.txt", fake_file(h), "text/plain"))])
    hand_id = client.get("/api/hands").json()["items"][0]["id"]
    detail = client.get(f"/api/hands/{hand_id}").json()
    assert detail["record"]["hand_id"] == "1" and "#FAKE-HAND" not in detail["raw_text"][1:]
    replay = client.post(f"/api/hands/{hand_id}/replay", json={"ranges": {"CO_p": "AA"}}).json()
    assert replay["ranges"] == {"CO_p": "AA", "SB_p": "random", "BB_p": "random"}
    assert any(s["scenario"] for s in replay["steps"])
