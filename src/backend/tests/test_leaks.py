import random

import pytest

from app.config import get_settings
from app.db.models import HandDecision, PreflopChart
from app.domain.scenario import GameFormat
from app.leaks.finder import find_leaks, leak_detail, stack_bucket
from app.parsers.importer import hand_row
from app.recommend.preflop_equity import class_names, range_vector
from app.stats.engine import StatsFilter
from tests.hands import act, make_hand

SIX = {"U": 100, "H": 100, "C": 100, "Hero": 100, "S": 100, "B": 100}  # Hero on BTN
TEN = {k: 10 for k in SIX}
RANGE = "22+,A2s+,K5s+,Q8s+,J8s+,T8s+,97s+,86s+,75s+,65s,54s,A8o+,KTo+,QTo+,JTo"
PREMIUMS = ["AA", "KK", "QQ", "JJ", "TT", "AKs"]
NAMES = list(class_names())


def cards(cls: str) -> str:
    if len(cls) == 2:
        return f"{cls[0]}h{cls[1]}d"
    return f"{cls[0]}h{cls[1]}{'h' if cls[2] == 's' else 'd'}"


_counter = iter(range(1, 10**6))


def add_hands(session, classes, opens, *, stacks=SIX, fmt=GameFormat.CASH, shove=False):
    for cls, opened in zip(classes, opens, strict=True):
        kind = ("raise", stacks["Hero"], True) if shove else ("raise", 2.5, False)
        hero_act = (
            act("p", "Hero", kind[0], kind[1], all_in=kind[2])
            if opened
            else act("p", "Hero", "fold")
        )
        record = make_hand(
            stacks,
            [act("p", "U", "fold"), act("p", "H", "fold"), act("p", "C", "fold"), hero_act],
            button="Hero",
            hero_cards=cards(cls),
            hand_id=str(next(_counter)),
            game_type=fmt,
        )
        session.add(hand_row(record, "", None))
    session.commit()


def add_chart(session):
    session.add(
        PreflopChart(
            name="BTN RFI",
            source="custom",
            game_format="cash",
            players=6,
            position="BTN",
            vs_position=None,
            stack_bb=100.0,
            situation="rfi",
            ante_bb=0.0,
            note="",
            actions={"raise": [float(x) for x in range_vector(RANGE)]},
        )
    )
    session.commit()


def tight_hero(session, n):
    rng = random.Random(7)
    classes = [rng.choice(NAMES) for _ in range(n)]
    add_hands(session, classes, [c in PREMIUMS for c in classes])


def test_stack_bucket_edges():
    assert [stack_bucket(x, True) for x in (3, 5, 6, 8, 9, 11, 12, 15)] == [
        "3-5", "3-5", "6-8", "6-8", "9-11", "9-11", "12-15", "12-15",
    ]  # fmt: skip
    assert [stack_bucket(x, False) for x in (16, 30, 31, 60, 61, 120, 121)] == [
        "16-30", "16-30", "31-60", "31-60", "61-120", "61-120", "120+",
    ]  # fmt: skip
    # Cash short stacks never pool with 30bb.
    assert [stack_bucket(x, False) for x in (5, 15)] == ["≤15", "≤15"]


def test_no_decisions_warns(db_session):
    report = find_leaks(db_session, StatsFilter())
    assert report.leaks == [] and report.total_hands == 0
    assert any("Importá historiales" in w for w in report.warnings)


def test_tight_open_is_a_leak(db_session):
    add_chart(db_session)
    tight_hero(db_session, 60)
    report = find_leaks(db_session, StatsFilter())
    assert report.total_hands == 60
    assert len(report.leaks) == 1
    g = report.leaks[0]
    assert g.source == "chart" and g.approximate and g.impact_unit == "pts/100"
    assert g.position == "BTN" and g.situation == "rfi" and g.stack_bucket == "61-120"
    raise_leak = next(a for a in g.actions if a.action == "raise")
    assert raise_leak.significant and raise_leak.observed < raise_leak.expected
    assert g.impact > 0


def test_small_sample_is_insufficient(db_session):
    add_chart(db_session)
    tight_hero(db_session, 20)
    report = find_leaks(db_session, StatsFilter())
    assert report.leaks == [] and len(report.insufficient) == 1
    assert report.insufficient[0].n == 20


def test_expected_is_per_class(db_session):
    add_chart(db_session)
    classes = [PREMIUMS[i % 6] for i in range(60)]
    add_hands(db_session, classes, [True] * 60)
    report = find_leaks(db_session, StatsFilter())
    assert report.leaks == []
    g = report.other[0]
    r = next(a for a in g.actions if a.action == "raise")
    assert r.expected == pytest.approx(1.0) and r.observed == pytest.approx(1.0)


def test_decisions_without_chart_warn(db_session):
    tight_hero(db_session, 5)
    report = find_leaks(db_session, StatsFilter())
    assert any("5 decisiones sin tabla" in w for w in report.warnings)


def test_pushfold_uses_nash(db_session):
    classes = [PREMIUMS[i % 6] for i in range(60)]
    add_hands(db_session, classes, [False] * 60, stacks=TEN, fmt=GameFormat.MTT)
    report = find_leaks(db_session, StatsFilter())
    assert len(report.leaks) == 1
    g = report.leaks[0]
    assert g.source == "nash" and g.impact_unit == "bb/100" and not g.approximate
    assert g.ev_loss_bb is not None and g.ev_loss_bb > 0
    assert g.impact > 0 and g.stack_bucket == "9-11"


def test_detail_has_top_classes_and_grid(db_session):
    add_chart(db_session)
    tight_hero(db_session, 60)
    report = find_leaks(db_session, StatsFilter())
    detail = leak_detail(db_session, StatsFilter(), report.leaks[0].key)
    assert detail is not None and detail.group.key == report.leaks[0].key
    assert 0 < len(detail.top_classes) <= 10
    assert len(detail.grid) == 169
    assert any(v is not None for v in detail.grid)
    assert leak_detail(db_session, StatsFilter(), "nope") is None


def test_settings_default():
    assert get_settings().leaks_min_sample == 50


def all_groups(report):
    return report.leaks + report.insufficient + report.other


def test_chart_notes_are_per_query(db_session):
    add_chart(db_session)
    rng = random.Random(3)
    deep = [rng.choice(NAMES) for _ in range(30)]
    short = [rng.choice(NAMES) for _ in range(30)]
    add_hands(db_session, short, [False] * 30, stacks={k: 40 for k in SIX})
    add_hands(db_session, deep, [False] * 30)
    groups = {g.stack_bucket: g for g in all_groups(find_leaks(db_session, StatsFilter()))}
    assert groups["61-120"].notes == []
    assert any("40bb" in n for n in groups["31-60"].notes)


def test_detail_action_prefers_non_fold_on_ties(db_session):
    add_chart(db_session)
    tight_hero(db_session, 60)
    report = find_leaks(db_session, StatsFilter())
    detail = leak_detail(db_session, StatsFilter(), report.leaks[0].key)
    assert detail.action == "raise"


def test_nash_mapped_actions_are_approximate(db_session):
    classes = [PREMIUMS[i % 6] for i in range(60)]
    add_hands(db_session, classes, [True] * 60, stacks=TEN, fmt=GameFormat.MTT)  # min-raises
    g = all_groups(find_leaks(db_session, StatsFilter()))[0]
    assert g.source == "nash" and g.approximate
    assert any("asimilaron a push/fold" in n for n in g.notes)


def test_unresolvable_nash_spot_has_its_own_warning(db_session):
    add_hands(db_session, ["AA"], [True], stacks=TEN, fmt=GameFormat.MTT)
    for d in db_session.query(HandDecision):
        d.spot = {"stacks_bb": {"UTG": 10.0}, "ante_bb": 0.0}
    db_session.commit()
    report = find_leaks(db_session, StatsFilter())
    assert any("1 decisiones de push/fold no se pudieron evaluar" in w for w in report.warnings)
    assert not any("sin tabla" in w for w in report.warnings)
    assert all_groups(report) == []


def add_vs_shove(session, classes, calls):
    for cls, called in zip(classes, calls, strict=True):
        record = make_hand(
            TEN,
            [
                act("p", "U", "raise", 10, all_in=True),
                act("p", "H", "fold"),
                act("p", "C", "fold"),
                act("p", "Hero", "call", 10, all_in=True) if called else act("p", "Hero", "fold"),
            ],
            button="Hero",
            hero_cards=cards(cls),
            hand_id=str(next(_counter)),
            game_type=GameFormat.MTT,
        )
        session.add(hand_row(record, "", None))
    session.commit()


def test_vs_allin_nash_fold_loses_ev(db_session):
    add_vs_shove(db_session, ["AA", "KK", "QQ", "JJ", "TT", "AKs"] * 10, [False] * 60)
    g = find_leaks(db_session, StatsFilter()).leaks[0]
    assert g.source == "nash" and g.situation == "vs_allin" and g.vs_position == "LJ"
    assert {a.action for a in g.actions} == {"call", "fold"}
    assert g.ev_loss_bb > 0


def test_vs_allin_nash_call_is_correct(db_session):
    add_vs_shove(db_session, ["AA", "KK", "QQ", "JJ", "TT", "AKs"] * 10, [True] * 60)
    report = find_leaks(db_session, StatsFilter())
    g = all_groups(report)[0]
    assert report.leaks == [] and g.ev_loss_bb == 0 and not g.approximate
    assert next(a for a in g.actions if a.action == "call").observed == 1.0


def test_mtt_10bb_chart_decision_uses_pushfold_buckets(db_session):
    db_session.add(
        PreflopChart(
            name="BTN vs UTG",
            source="custom",
            game_format="mtt",
            players=6,
            position="BTN",
            vs_position="LJ",
            stack_bb=10.0,
            situation="vs_open",
            ante_bb=0.0,
            note="",
            actions={"call": [float(x) for x in range_vector(RANGE)]},
        )
    )
    db_session.commit()
    for i in range(60):
        record = make_hand(
            TEN,
            [
                act("p", "U", "raise", 2.0),
                act("p", "H", "fold"),
                act("p", "C", "fold"),
                act("p", "Hero", "fold"),
            ],
            button="Hero",
            hero_cards=cards(PREMIUMS[i % 6]),
            hand_id=f"vo{i}",
            game_type=GameFormat.MTT,
        )
        db_session.add(hand_row(record, "", None))
    db_session.commit()
    groups = all_groups(find_leaks(db_session, StatsFilter()))
    assert [g.stack_bucket for g in groups] == ["9-11"]
    assert groups[0].source == "chart"
