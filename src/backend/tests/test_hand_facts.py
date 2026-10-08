import pytest

from app.domain.hand import HandRecord
from app.stats.facts import allin_adjusted_net, hero_facts
from tests.hands import act, make_hand

SIX = {"UTG_p": 100, "HJ_p": 100, "CO_p": 100, "Hero": 100, "SB_p": 100, "BB_p": 100}


def test_positions_and_net_for_open_and_cbet():
    h = make_hand(
        SIX,
        [
            act("p", "UTG_p", "fold"),
            act("p", "HJ_p", "fold"),
            act("p", "CO_p", "fold"),
            act("p", "Hero", "raise", 2.5),
            act("p", "SB_p", "fold"),
            act("p", "BB_p", "call", 1.5),
            act("f", "BB_p", "check"),
            act("f", "Hero", "bet", 2),
            act("f", "BB_p", "fold"),
            act("f", "Hero", "return", 2),
        ],
        button="Hero",
        board="Kd7c2s",
        collected={"Hero": 5.5},
    )
    assert h.positions()["UTG_p"] == "LJ"
    assert h.positions()["Hero"] == "BTN"
    f = hero_facts(h)
    assert f.position == "BTN" and f.table_size == 6 and f.hand_class == "AKs"
    assert f.net_chips == pytest.approx(3.0)
    assert (f.vpip, f.pfr, f.threebet_opp, f.saw_flop) == (1, 1, 0, 1)
    assert (f.cbet_flop_opp, f.cbet_flop) == (1, 1)
    assert (f.wtsd, f.non_showdown_bb, f.showdown_bb) == (0, 3.0, 0.0)
    assert (f.agg_bets, f.agg_calls) == (1, 0)
    assert f.allin_adjusted == 0 and f.allin_adj_bb == f.net_bb


def test_three_bet_from_the_big_blind():
    h = make_hand(
        {"V": 100, "SB_p": 100, "Hero": 100},
        [
            act("p", "V", "raise", 2.5),
            act("p", "SB_p", "fold"),
            act("p", "Hero", "raise", 9),  # raises to 10: 9 more on top of the blind
            act("p", "V", "fold"),
            act("p", "Hero", "return", 7.5),
        ],
        button="V",
        collected={"Hero": 5.5},
    )
    f = hero_facts(h)
    assert f.position == "BB"
    assert (f.vpip, f.pfr, f.threebet_opp, f.threebet) == (1, 1, 1, 1)
    assert f.net_bb == pytest.approx(3.0)


def test_fold_to_three_bet_and_no_vpip_for_blind_checks():
    h = make_hand(
        {"Hero": 100, "SB_p": 100, "BB_p": 100},
        [
            act("p", "Hero", "raise", 2.5),
            act("p", "SB_p", "fold"),
            act("p", "BB_p", "raise", 10),
            act("p", "Hero", "fold"),
        ],
        button="Hero",
    )
    f = hero_facts(h)
    assert (f.fold3b_opp, f.fold3b, f.threebet_opp) == (1, 1, 0)

    walk = make_hand(
        {"V": 100, "SB_p": 100, "Hero": 100},
        [act("p", "V", "fold"), act("p", "SB_p", "call", 0.5), act("p", "Hero", "check")],
        button="V",
        board="2c3d4h",
    )
    assert hero_facts(walk).vpip == 0


def test_fold_to_cbet_after_checking():
    h = make_hand(
        {"V": 100, "SB_p": 100, "Hero": 100},
        [
            act("p", "V", "raise", 2.5),
            act("p", "SB_p", "fold"),
            act("p", "Hero", "call", 1.5),
            act("f", "Hero", "check"),
            act("f", "V", "bet", 2),
            act("f", "Hero", "fold"),
        ],
        button="V",
        board="Kd7c2s",
    )
    f = hero_facts(h)
    assert (f.fold_cbet_opp, f.fold_cbet, f.cbet_flop_opp) == (1, 1, 0)
    assert (f.agg_folds, f.saw_flop, f.wtsd) == (1, 1, 0)


def test_river_showdown_flags():
    h = make_hand(
        {"V": 100, "Hero": 100},
        [
            act("p", "V", "call", 0.5),
            act("p", "Hero", "check"),
            act("f", "Hero", "check"),
            act("f", "V", "check"),
            act("t", "Hero", "check"),
            act("t", "V", "check"),
            act("r", "Hero", "bet", 1),
            act("r", "V", "call", 1),
        ],
        button="V",
        hero_cards="AhAd",
        board="Kd7c2s3h9c",
        shown={"V": "QsQc"},
        collected={"Hero": 4},
    )
    f = hero_facts(h)
    assert (f.wtsd, f.wsd) == (1, 1)
    assert f.showdown_bb == pytest.approx(2.0)
    assert f.allin_adjusted == 0  # no all-in


def test_allin_ev_adjusted_heads_up():
    # AA vs KK all-in preflop, KK hits: real -100, expected ~ +64 (82% of 200 - 100).
    h = make_hand(
        {"V": 100, "Hero": 100},
        [
            act("p", "V", "raise", 99.5, all_in=True),
            act("p", "Hero", "call", 99, all_in=True),
        ],
        button="V",
        hero_cards="AhAd",
        board="Kd7c2s3h9c",
        shown={"V": "KcKs"},
        collected={"V": 200},
    )
    f = hero_facts(h)
    assert f.net_bb == pytest.approx(-100)
    assert f.allin_adjusted == 1
    assert f.allin_adj_bb == pytest.approx(0.82 * 200 - 100, abs=1.5)


def test_allin_ev_side_pots_sum_to_zero_and_rake_share():
    h = make_hand(
        {"Short": 20, "Mid": 50, "Hero": 100},
        [
            act("p", "Short", "raise", 20, all_in=True),
            act("p", "Mid", "raise", 49.5, all_in=True),
            act("p", "Hero", "call", 49),
        ],
        button="Short",
        hero_cards="AhAd",
        board="Kd7c2s3h9c",
        shown={"Short": "KcKs", "Mid": "QcQs"},
        collected={"Short": 60, "Mid": 60},
    )
    total = sum(allin_adjusted_net(h, p) for p in ["Short", "Mid", "Hero"])
    assert total == pytest.approx(0.0, abs=1e-6)

    raked = h.model_copy(update={"collected": {"Short": 57, "Mid": 60}, "rake": 3})
    raked_total = sum(allin_adjusted_net(raked, p) for p in ["Short", "Mid", "Hero"])
    assert raked_total == pytest.approx(-3.0, abs=1e-6)


def test_allin_ev_needs_known_hands_and_early_allin():
    base = dict(button="V", hero_cards="AhAd", board="Kd7c2s3h9c", collected={"V": 200})
    actions = [act("p", "V", "raise", 99.5, all_in=True), act("p", "Hero", "call", 99, all_in=True)]
    assert allin_adjusted_net(make_hand({"V": 100, "Hero": 100}, actions, **base), "Hero") is None


def test_sitting_out_players_do_not_count():
    h = make_hand(
        {"A": 100, "Away": 100, "Hero": 100, "C": 100},
        [act("p", "A", "fold"), act("p", "Hero", "fold")],
        button="A",
        sitting_out=("Away",),
    )
    assert h.table_size == 3
    assert h.positions() == {"A": "BTN", "Hero": "SB", "C": "BB"}


def test_record_validation():
    with pytest.raises(ValueError):
        make_hand({"A": 100, "Hero": 100}, [act("p", "Ghost", "fold")], button="A")
    h = make_hand({"A": 100, "Hero": 100}, [], button="A")
    data = h.model_dump()
    data["board"] = "AhKhQhJhTh9h"
    with pytest.raises(ValueError):
        HandRecord.model_validate(data)
