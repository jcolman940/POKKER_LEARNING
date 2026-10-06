import pytest

from app.recommend.preflop_equity import range_vector


def grid(text: str) -> list[float]:
    return range_vector(text).tolist()


def scenario(**overrides):
    body = {
        "format": "cash",
        "num_players": 6,
        "hero_position": "BTN",
        "hero_hand": "AhJh",
        "villains": [{"position": "BB", "range": "random"}],
        "effective_stack_bb": 100,
        "pot_bb": 1.5,
        "situation": "rfi",
    }
    body.update(overrides)
    return body


def add_chart(client, **overrides):
    body = {
        "name": "BTN RFI",
        "source": "pokalab",
        "game_format": "cash",
        "players": 6,
        "position": "BTN",
        "stack_bb": 100,
        "situation": "rfi",
        "actions": {"raise": grid("22+,A2s+,K9s+,ATo+,AJs:0.6")},
    }
    body.update(overrides)
    resp = client.post("/api/charts", json=body)
    assert resp.status_code == 201, resp.text


def rec(client, **overrides):
    resp = client.post("/api/simulator/analyze", json=scenario(**overrides))
    assert resp.status_code == 200, resp.text
    return resp.json()["recommendation"]


def test_chart_recommendation_exact_with_mixed_strategy(client):
    add_chart(client)
    r = rec(client)
    assert r["available"] and r["source"] == "chart" and r["confidence"] == "exact"
    assert r["hand_class"] == "AJs"
    freqs = {a["action"]: a["frequency"] for a in r["actions"]}
    assert freqs == pytest.approx({"raise": 0.6, "fold": 0.4})
    assert r["reference"].startswith("Fuente externa: Pokalab")
    assert any("mixta" in e for e in r["explanation"])
    assert r["warnings"] == []


def test_chart_recommendation_uses_closest_and_warns(client):
    add_chart(client)
    add_chart(client, name="BTN RFI 40bb", stack_bb=40)
    r = rec(client, effective_stack_bb=45, num_players=9, format="mtt", ante_bb=0.12)
    assert r["confidence"] == "approximate"
    assert r["reference"].endswith("BTN RFI 40bb")
    text = " ".join(r["warnings"])
    assert "aproximado" in text and "9" in text and "MTT" in text and "Ante" in text


def test_hand_outside_chart_folds(client):
    add_chart(client)
    r = rec(client, hero_hand="7c2d")
    assert [a["action"] for a in r["actions"]] == ["fold"]
    assert r["explanation"] == ["La mano está fuera del rango: fold."]


def test_missing_inputs_and_postflop(client):
    assert "No hay rangos" in rec(client)["message"]
    assert "posición de Hero" in rec(client, hero_position=None)["message"]
    assert "situación" in rec(client, situation=None)["message"]
    assert "fase 5" in rec(client, board="Kh7s2c")["message"]


def test_push_fold_recommendation_in_tournaments(client):
    r = rec(client, format="mtt", effective_stack_bb=10, hero_hand="AhAd")
    assert r["source"] == "nash" and r["ev_unit"] == "bb"
    assert r["actions"][0] == pytest.approx(
        {"action": "allin", "frequency": 1.0, "ev": r["actions"][0]["ev"]}
    )
    assert r["actions"][0]["ev"] > r["actions"][1]["ev"]

    trash = rec(client, format="mtt", effective_stack_bb=10, hero_position="LJ", hero_hand="7c2d")
    assert trash["actions"][0]["frequency"] == 0.0

    icm = rec(
        client,
        format="sng",
        effective_stack_bb=12,
        hero_position="BB",
        situation="vs_allin",
        villains=[{"position": "BTN", "range": "random"}],
        stacks_bb={"BTN": 12, "SB": 30, "BB": 8},
        num_players=3,
        payouts=[50, 30, 20],
        hero_hand="KhQd",
    )
    assert icm["source"] == "nash" and icm["ev_unit"] == "$"
    assert icm["actions"][0]["action"] == "call"
    assert "ICM" in icm["explanation"][0]


def test_push_fold_input_errors(client):
    bb = rec(
        client,
        format="mtt",
        effective_stack_bb=10,
        hero_position="BB",
        villains=[{"position": "SB"}],
    )
    assert not bb["available"]
    late = rec(
        client,
        format="mtt",
        effective_stack_bb=10,
        hero_position="CO",
        situation="vs_allin",
        villains=[{"position": "BTN"}],
    )
    assert "antes que Hero" in late["message"]
