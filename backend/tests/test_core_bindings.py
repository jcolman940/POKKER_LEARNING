import pokercore
import pytest


def test_evaluate_and_category():
    royal = pokercore.evaluate("AsKsQsJsTs")
    assert pokercore.hand_category(royal) == "straight_flush"
    assert pokercore.evaluate("AsAhKd7c2s") > pokercore.evaluate("AdAcQs7h2d")
    assert pokercore.hand_category(pokercore.evaluate("2c3dAsKsQsJsTs")) == "straight_flush"
    with pytest.raises(ValueError):
        pokercore.evaluate("AsKs")


def test_range_combos_with_card_removal():
    assert len(pokercore.range_combos("AA")) == 6
    assert len(pokercore.range_combos("AA", dead="Ah")) == 3
    weights = dict(pokercore.range_combos("AKs:0.5"))
    assert set(weights.values()) == {0.5}
    with pytest.raises(ValueError):
        pokercore.range_combos("AKx")


def test_equity_hand_vs_hand_exact():
    r = pokercore.equity(["AhAd", "KcKd"], "Kh7s2c3d")
    assert r.exact
    assert r.players[0].equity == pytest.approx(2 / 44)
    assert r.players[1].win == pytest.approx(42 / 44)


def test_equity_range_vs_range_monte_carlo_reproducible():
    a = pokercore.equity(["22+,A2s+", "random"], mode="monte_carlo", iterations=20_000, seed=3)
    b = pokercore.equity(["22+,A2s+", "random"], mode="monte_carlo", iterations=20_000, seed=3)
    assert not a.exact
    assert a.seed == 3
    assert a.players[0].equity == b.players[0].equity
    assert a.players[0].std_error > 0
    assert sum(p.equity for p in a.players) == pytest.approx(1.0)


def test_equity_errors():
    with pytest.raises(ValueError):
        pokercore.equity(["AA"])
    with pytest.raises(ValueError):
        pokercore.equity(["AA", "KK"], mode="fast")
    with pytest.raises(RuntimeError):
        pokercore.equity(["AhKh", "AhQd"], mode="exact")
