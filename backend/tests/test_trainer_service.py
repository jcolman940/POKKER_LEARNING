import random
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import PreflopChart, TrainerCard
from app.domain.scenario import Scenario
from app.recommend.preflop_equity import class_index, class_names, hand_class
from app.trainer import selection, service

LATER = datetime.now(UTC) + timedelta(days=60)


def _chart(raise_grid: list[float]) -> PreflopChart:
    return PreflopChart(
        name="BTN RFI",
        source="custom",
        game_format="cash",
        players=6,
        position="BTN",
        stack_bb=100.0,
        situation="rfi",
        actions={"raise": raise_grid},
    )


def _grid(**by_class: float) -> list[float]:
    return [by_class.get(n, 0.0) for n in class_names()]


def _start(db_session, **filters):
    base = {"sources": ["pushfold"], "difficulty": 0} | filters
    return service.create_session(db_session, base)


def test_chart_spot_is_scored_against_its_own_chart(db_session):
    low = _chart([1.0] * 169)  # raises everything
    high = _chart(_grid(AA=1.0))  # raises only AA
    db_session.add_all([low, high])
    db_session.commit()
    by_id = {low.id: low, high.id: high}
    ts = _start(db_session, sources=["chart"], difficulty=100)
    rng = random.Random(5)
    seen = set()
    for _ in range(40):
        attempt, served = service.next_spot(db_session, ts.id, rng)
        chart = by_id[attempt.reference["chart_id"]]
        seen.add(chart.id)
        cls = class_index()[hand_class(Scenario(**attempt.scenario).hero_hand)]
        freq = {a["action"]: a["frequency"] for a in attempt.reference["recommendation"]["actions"]}
        assert freq.get("raise", 0.0) == pytest.approx(chart.actions["raise"][cls])
    assert seen == {low.id, high.id}


def _answered_card(db_session, **filters):
    ts = _start(db_session, **filters)
    rng = random.Random(2)
    attempt, served = service.next_spot(db_session, ts.id, rng)
    service.answer_spot(db_session, attempt.spot_id, {"action": served.offered[0]}, rng)
    return ts, rng, db_session.query(TrainerCard).one()


def test_review_mode_serves_a_due_card(db_session):
    ts, rng, card = _answered_card(db_session)
    review_ts = _start(db_session, mode="review")
    attempt, served = service.next_spot(db_session, review_ts.id, rng, now=LATER)
    assert served.review is True and attempt.card_id == card.id


def test_missing_chart_archives_the_card(db_session):
    chart = _chart(_grid(AA=1.0, KK=1.0))
    db_session.add(chart)
    db_session.commit()
    ts = _start(db_session, sources=["chart", "pushfold"], difficulty=100)
    rng = random.Random(4)
    for _ in range(30):
        attempt, served = service.next_spot(db_session, ts.id, rng)
        if served.source == "chart":
            break
    service.answer_spot(db_session, attempt.spot_id, {"action": "fold"}, rng)
    card = db_session.query(TrainerCard).filter_by(source="chart").one()
    ts2 = _start(db_session, sources=["chart", "pushfold"], mode="review")
    db_session.delete(chart)
    db_session.commit()
    try:
        _, served = service.next_spot(db_session, ts2.id, rng, now=LATER)
        assert served.card is None or served.card.id != card.id
    except selection.NoSpots:
        pass
    db_session.refresh(card)
    assert card.archived is True


def test_unbuildable_spot_does_not_archive(db_session, monkeypatch):
    ts, rng, card = _answered_card(db_session)
    monkeypatch.setattr(selection, "_hand_spot", lambda *a, **k: None)
    review_ts = _start(db_session, mode="review")
    with pytest.raises(selection.NoSpots):
        service.next_spot(db_session, review_ts.id, rng, now=LATER)
    db_session.refresh(card)
    assert card.archived is False


def test_prefer_due_always_serves_the_due_card(db_session):
    ts, rng, card = _answered_card(db_session)
    plain = _start(db_session, mode="normal")
    prefer = _start(db_session, mode="normal", prefer_due=True)
    served_plain = []
    for i in range(30):
        attempt, served = service.next_spot(db_session, prefer.id, random.Random(i), now=LATER)
        assert served.review is True and attempt.card_id == card.id
    for i in range(30):
        attempt, served = service.next_spot(db_session, plain.id, random.Random(i), now=LATER)
        served_plain.append(served.review)
    assert not all(served_plain)  # the 70/30 mix still serves new spots
