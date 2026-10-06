import pytest

from app.simulator.service import compute_outs


def scenario(**overrides):
    base = {
        "num_players": 6,
        "hero_position": "BTN",
        "hero_hand": "AhAd",
        "villains": [{"position": "BB", "range": "KK,QQ"}],
        "board": "Kh7s2c3d",
        "pot_bb": 20,
        "to_call_bb": 10,
        "effective_stack_bb": 80,
    }
    base.update(overrides)
    return base


def test_analyze_uses_range_and_reports_exact_hand_separately(client):
    body = scenario(villains=[{"position": "BB", "range": "KK,QQ", "hand": "KcKd"}])
    resp = client.post("/api/simulator/analyze", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["street"] == "turn"

    # Against the range (3 KK sets + 6 QQ) AA is well ahead...
    main = data["equity"]
    assert main["exact"]
    assert main["hero"]["equity"] > 0.6
    assert main["hero"]["equity"] + main["villains"][0]["equity"] == pytest.approx(1.0)
    # ...while against the fixed set of kings it only has the two aces.
    vs_hands = data["equity_vs_hands"]
    assert vs_hands["hero"]["equity"] == pytest.approx(2 / 44)

    assert data["ranges"][0]["combos"] == pytest.approx(3 + 6)
    assert data["metrics"]["required_equity"] == pytest.approx(1 / 3)
    assert data["metrics"]["mdf"] == pytest.approx(0.5)
    assert data["metrics"]["spr"] == pytest.approx(4.0)
    assert data["recommendation"]["available"] is False


def test_analyze_without_fixed_hand_has_no_informative_equity(client):
    data = client.post("/api/simulator/analyze", json=scenario()).json()
    assert data["equity_vs_hands"] is None


def test_analyze_preflop_multiway_monte_carlo(client):
    body = scenario(
        board="",
        villains=[{"range": "22+,A2s+,KTo+"}, {"range": "random"}, {"range": "QQ+"}],
    )
    data = client.post("/api/simulator/analyze", json=body).json()
    assert data["street"] == "preflop"
    assert not data["equity"]["exact"]
    assert data["equity"]["hero"]["std_error"] > 0
    assert data["outs"]["available"] is False


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"hero_hand": "Ah"}, "2 cartas"),
        ({"board": "Kh7s"}, "0, 3, 4 o 5"),
        ({"board": "AhKs7d"}, "Ah"),
        ({"villains": [{"range": "AKx"}]}, "Rango inválido"),
        ({"board": "AsAc7d", "villains": [{"range": "AA"}]}, "queda vacío"),
        ({"villains": [{"position": "BTN"}]}, "misma posición"),
        ({"villains": [{"position": "UTG"}]}, "no existe"),
        ({"to_call_bb": 30}, "no puede superar"),
        ({"num_players": 2, "villains": [{}, {}]}, "más rivales"),
    ],
)
def test_analyze_rejects_invalid_scenarios(client, override, message):
    resp = client.post("/api/simulator/analyze", json=scenario(**override))
    assert resp.status_code == 422
    assert message in resp.text


def test_outs_flush_draw_against_sets():
    # Nut flush draw vs sets: 9 hearts left, but 2h pairs the board and gives
    # the sets a full house.
    outs = compute_outs("AhKh", ["QQ,77"], "Qh7h2c")
    assert outs.available and outs.currently_ahead is False
    assert sorted(outs.cards) == sorted(["3h", "4h", "5h", "6h", "8h", "9h", "Th", "Jh"])
    assert outs.count == 8
    assert outs.unseen == 47


def test_outs_when_ahead_or_not_applicable():
    ahead = compute_outs("AhAd", ["KK"], "As7c2d")
    assert ahead.currently_ahead is True and ahead.count == 0
    assert compute_outs("AhAd", ["KK"], "").available is False
    assert compute_outs("AhAd", ["KK"], "As7c2d4h5s").available is False


def test_deal_fills_missing_cards_reproducibly(client):
    body = {"street": "turn", "hero_hand": "AhKh", "deal_villains": [0], "seed": 5}
    first = client.post("/api/simulator/deal", json=body).json()
    second = client.post("/api/simulator/deal", json=body).json()
    assert first == second
    assert first["hero_hand"] == "AhKh"
    assert len(first["board"]) == 8
    assert len(first["villain_hands"][0]) == 4
    cards = [first["hero_hand"], first["board"], first["villain_hands"][0]]
    joined = "".join(cards)
    assert len({joined[i : i + 2] for i in range(0, len(joined), 2)}) == 8


def test_deal_keeps_fixed_board_and_validates(client):
    data = client.post("/api/simulator/deal", json={"street": "river", "board": "2c3c4c"}).json()
    assert data["board"].startswith("2c3c4c") and len(data["board"]) == 10
    assert len(data["hero_hand"]) == 4

    bad = client.post("/api/simulator/deal", json={"street": "flop", "board": "2c3c4c5c"})
    assert bad.status_code == 422
    clash = client.post("/api/simulator/deal", json={"hero_hand": "AhKh", "board": "Ah"})
    assert clash.status_code == 422


def test_positions_endpoint(client):
    assert client.get("/api/simulator/positions/6").json()[0] == "LJ"


def test_range_parse_endpoint(client):
    ok = client.post("/api/ranges/parse", json={"text": "22+, AKs:0.5"}).json()
    assert ok["valid"] and ok["combos"] == pytest.approx(78 + 2)
    assert len(ok["grid"]) == 169 and ok["grid"][0] == 1.0 and ok["grid"][1] == 0.5
    bad = client.post("/api/ranges/parse", json={"text": "AKx"}).json()
    assert not bad["valid"] and "inválido" in bad["error"]
