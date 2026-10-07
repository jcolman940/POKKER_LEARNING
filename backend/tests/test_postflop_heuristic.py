from app.domain.scenario import Scenario, Villain
from app.recommend.postflop_heuristic import recommend_heuristic


def scen(hero, board, ranges, *, pot=10.0, to_call=0.0, hero_pos="BTN", positions=("SB", "BB")):
    return Scenario(
        num_players=6,
        hero_position=hero_pos,
        hero_hand=hero,
        board=board,
        villains=[Villain(position=p, range=r) for p, r in zip(positions, ranges, strict=True)],
        pot_bb=pot,
        to_call_bb=to_call,
        effective_stack_bb=100.0,
    )


def freq(rec, action):
    return sum(a.frequency for a in rec.actions if a.action == action)


def test_always_heuristic_and_approximate():
    rec = recommend_heuristic(scen("AsAd", "AhKc2d", ["random", "random"]))
    assert rec.source == "heuristic" and rec.confidence == "approximate"
    assert all(a.ev is None for a in rec.actions)
    assert any("umbral heurístico" in e for e in rec.explanation)


def test_nuts_bets_for_value():
    rec = recommend_heuristic(scen("AsAd", "AhKc2d", ["random", "random"]))
    assert freq(rec, "bet") == 1.0


def test_air_checks():
    rec = recommend_heuristic(scen("3c4d", "AhKcJd", ["QQ+,AK", "TT+,AQ+"]))
    assert freq(rec, "check") == 1.0


def test_air_folds_to_overbet():
    rec = recommend_heuristic(scen("3c4d", "AhKcJd", ["QQ+,AK", "TT+,AQ+"], pot=40.0, to_call=20.0))
    assert freq(rec, "fold") == 1.0


def test_monster_raises_facing_a_bet():
    rec = recommend_heuristic(scen("AsAd", "AhKc2d", ["random", "random"], pot=15.0, to_call=5.0))
    assert freq(rec, "raise") >= 0.5


def test_semibluff_needs_outs_and_last_position():
    rec = recommend_heuristic(scen("9h8h", "Th7h2c", ["QQ+,AK", "TT+,AQ+"]))
    assert freq(rec, "bet") == 1.0  # OESD + flush draw, BTN is last
    rec = recommend_heuristic(
        scen("9h8h", "Th7h2c", ["QQ+,AK", "TT+,AQ+"], hero_pos="SB", positions=("BB", "BTN"))
    )
    assert freq(rec, "bet") == 0.0


def test_near_threshold_is_mixed(monkeypatch):
    from app.config import get_settings

    rec = recommend_heuristic(scen("AsAd", "AhKc2d", ["random", "random"]))
    share = float(rec.reference.split("le ganás a ")[1].split("%")[0]) / 100
    monkeypatch.setattr(get_settings(), "heuristic_value_share", share - 0.01)
    mixed = recommend_heuristic(scen("AsAd", "AhKc2d", ["random", "random"]))
    assert freq(mixed, "bet") == 0.5 and freq(mixed, "check") == 0.5
    assert any("cerca del umbral" in w for w in mixed.warnings)
