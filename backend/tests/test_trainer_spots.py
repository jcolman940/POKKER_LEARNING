import random

import numpy as np

from app.db.models import PreflopChart
from app.domain.positions import preflop_order
from app.domain.scenario import Scenario, Situation, Villain
from app.recommend.engine import recommend
from app.recommend.preflop_equity import class_names, combos_per_class, hand_class
from app.recommend.schemas import ActionOut, RecommendationOut
from app.trainer.scoring import score_hand
from app.trainer.spots import (
    PUSHFOLD_TABLES,
    card_key,
    chart_frontier,
    generate_chart,
    generate_pushfold,
    pick_hand,
    pushfold_frontier,
    pushfold_pool,
)


def _grid(**by_class: float) -> list[float]:
    return [by_class.get(n, 0.0) for n in class_names()]


def _chart(**kw) -> PreflopChart:
    base = dict(
        name="BTN RFI",
        source="custom",
        game_format="cash",
        players=6,
        position="BTN",
        stack_bb=100.0,
        situation="rfi",
        actions={"raise": _grid(AA=1.0, KK=1.0, AKs=0.5)},
    )
    base.update(kw)
    return PreflopChart(**base)


def test_pool_is_deterministic_and_sized():
    assert PUSHFOLD_TABLES == (9, 6, 3, 2)
    pool = pushfold_pool(9)
    assert len(pool) == 12 and all(len(c) == 9 for c in pool)
    assert pool == pushfold_pool(9)
    assert all(3 <= s <= 40 for c in pool for s in c)
    for n in PUSHFOLD_TABLES:
        assert all(len(c) == n for c in pushfold_pool(n))


def test_generate_pushfold_spot(db_session):
    spot = generate_pushfold(db_session, random.Random(3), {}, [])
    assert spot is not None and spot.source == "pushfold" and spot.chart_id is None
    rec = recommend(spot.scenario, db_session)
    assert rec.available and rec.source == "nash"
    sc = spot.scenario
    if sc.situation == Situation.RFI:
        assert spot.offered == ["allin", "fold"]
        assert sc.hero_position != "BB"
    else:
        assert spot.offered == ["call", "fold"]
    assert not hasattr(spot, "recommendation")
    assert spot.card_key.startswith("pushfold|mtt|")
    assert spot.card_key.endswith("|" + hand_class(sc.hero_hand))


def test_generate_pushfold_filters(db_session):
    f = {"table_sizes": [2], "situations": ["vs_allin"], "positions": ["BB"]}
    spot = generate_pushfold(db_session, random.Random(1), f, [])
    assert spot is not None
    assert spot.scenario.num_players == 2
    assert spot.scenario.situation == Situation.VS_ALLIN
    assert spot.scenario.hero_position == "BB"
    assert spot.scenario.villains[0].position == "BTN"
    assert recommend(spot.scenario, db_session).available
    assert generate_pushfold(db_session, random.Random(1), {"formats": ["cash"]}, []) is None
    no_utg = {"table_sizes": [2], "positions": ["UTG"]}
    assert generate_pushfold(db_session, random.Random(1), no_utg, []) is None


def test_pick_hand_difficulty():
    combos = combos_per_class()
    names = class_names()
    frontier = np.zeros(169, bool)
    for n in ("A5s", "T9s", "22"):
        frontier[names.index(n)] = True
    rng = random.Random(7)
    for _ in range(100):
        hand = pick_hand(rng, combos, frontier, 100)
        assert len(hand) == 4 and hand_class(hand) in ("A5s", "T9s", "22")
        assert hand[:2] != hand[2:]
    hits = sum(
        hand_class(pick_hand(rng, combos, frontier, 0)) in ("A5s", "T9s", "22") for _ in range(500)
    )
    assert hits < 60  # about 14/1326 of combos by chance
    # empty frontier falls back to everything
    assert len(pick_hand(rng, combos, np.zeros(169, bool), 100)) == 4


def test_pick_hand_suits_match_class():
    combos = combos_per_class()
    rng = random.Random(1)
    for name in ("AKs", "AKo", "77"):
        only = np.zeros(169, bool)
        only[class_names().index(name)] = True
        for _ in range(30):
            h = pick_hand(rng, combos, only, 100)
            assert hand_class(h) == name


def test_pushfold_frontier():
    ev = np.array([1.5, 0.4, -0.2, 3.0])
    assert pushfold_frontier(ev, 0.0, 1.0).tolist() == [False, True, True, False]
    assert pushfold_frontier(ev, 0.0, 2.0).tolist() == [True, True, True, False]


def test_chart_frontier_mixed_and_edges():
    names = class_names()
    f = chart_frontier({"raise": _grid(AA=1.0, KK=1.0, AKs=0.5)})
    assert f[names.index("AKs")]  # mixed
    assert f[names.index("KQs")]  # out, next to KK and AKs
    assert f[names.index("KK")]  # in, next to QQ (out)
    assert not f[names.index("72o")]


def test_generate_chart_none_without_tables(db_session):
    assert generate_chart(db_session, random.Random(1), {}) is None


def test_generate_chart_btn_rfi(db_session):
    chart = _chart()
    db_session.add(chart)
    db_session.commit()
    spot = generate_chart(db_session, random.Random(1), {})
    assert spot is not None and spot.source == "chart" and spot.chart_id == chart.id
    sc = spot.scenario
    assert (sc.format.value, sc.num_players, sc.hero_position) == ("cash", 6, "BTN")
    assert sc.situation == Situation.RFI and sc.effective_stack_bb == 100.0
    assert sc.villains[0].position != "BTN"
    assert spot.offered == ["fold", "raise"]
    assert spot.card_key == f"chart|{chart.id}|{hand_class(sc.hero_hand)}"
    rec = recommend(sc, db_session)
    assert rec.available and rec.source == "chart"
    assert generate_chart(db_session, random.Random(1), {"positions": ["UTG"]}) is None
    assert generate_chart(db_session, random.Random(1), {"formats": ["mtt"]}) is None


def _nash(ev_a: float, ev_f: float, conf="exact") -> RecommendationOut:
    return RecommendationOut(
        available=True,
        source="nash",
        confidence=conf,
        ev_unit="bb",
        actions=[
            ActionOut(action="allin", frequency=1.0, ev=ev_a),
            ActionOut(action="fold", frequency=0.0, ev=ev_f),
        ],
    )


def test_score_nash():
    s = score_hand(_nash(1.2, 0.0), "fold", 1.0)
    assert round(s.loss, 6) == 1.2 and s.verdict == "error" and s.best == "allin"
    assert s.loss_unit == "bb" and not s.approximate
    s = score_hand(_nash(1.2, 0.0), "allin", 1.0)
    assert s.loss == 0 and s.verdict == "correct"
    s = score_hand(_nash(0.03, 0.0), "fold", 1.0)
    assert s.verdict == "correct" and round(s.loss, 6) == 0.03
    assert score_hand(_nash(0.4, 0.0), "fold", 10.0).verdict == "correct"  # ICM scale
    assert score_hand(_nash(1.0, 0.0, "approximate"), "allin", 1.0).approximate


def _chart_rec() -> RecommendationOut:
    return RecommendationOut(
        available=True,
        source="chart",
        confidence="exact",
        actions=[ActionOut(action="fold", frequency=0.7), ActionOut(action="raise", frequency=0.3)],
    )


def test_score_chart():
    s = score_hand(_chart_rec(), "raise", 1.0)
    assert round(s.loss, 6) == 0.7 and s.verdict == "acceptable" and s.best == "fold"
    assert s.loss_unit == "freq" and s.approximate and round(s.freq_chosen, 6) == 0.3
    s = score_hand(_chart_rec(), "fold", 1.0)
    assert round(s.loss, 6) == 0.3 and s.verdict == "correct"
    s = score_hand(_chart_rec(), "call", 1.0)
    assert s.loss == 1 and s.verdict == "error" and s.freq_chosen == 0


def test_hu_10bb_sb_push_aces(db_session):
    sc = Scenario(
        format="mtt",
        num_players=2,
        hero_position="BTN",
        hero_hand="AhAd",
        villains=[Villain(position="BB")],
        situation=Situation.RFI,
        effective_stack_bb=10,
        stacks_bb={"BTN": 10, "BB": 10},
        bb_ante_bb=1.0,
    )
    rec = recommend(sc, db_session)
    assert score_hand(rec, "allin", 1.0).verdict == "correct"
    assert score_hand(rec, "fold", 1.0).verdict == "error"


def test_card_key_pushfold(db_session):
    f = {"table_sizes": [2], "situations": ["rfi"]}
    spot = generate_pushfold(db_session, random.Random(5), f, [])
    assert spot is not None
    assert card_key(spot) == spot.card_key
    parts = spot.card_key.split("|")
    assert parts[:5] == ["pushfold", "mtt", "BTN", "rfi", "-"]


def test_generate_chart_skips_pushfold_spots(db_session):
    db_session.add(_chart(game_format="mtt", stack_bb=10.0))
    db_session.commit()
    assert generate_chart(db_session, random.Random(1), {}) is None
    db_session.add(_chart(game_format="mtt", stack_bb=30.0, name="30bb"))
    db_session.commit()
    spot = generate_chart(db_session, random.Random(1), {})
    assert spot is not None and spot.scenario.effective_stack_bb == 30.0
    assert recommend(spot.scenario, db_session).source == "chart"


def test_pushfold_nine_handed_vs_allin(db_session):
    f = {"table_sizes": [9], "situations": ["vs_allin"]}
    spot = generate_pushfold(db_session, random.Random(2), f, [])
    assert spot is not None
    sc = spot.scenario
    order = preflop_order(9)
    assert order.index(sc.villains[0].position) < order.index(sc.hero_position)
    assert recommend(sc, db_session).source == "nash"
