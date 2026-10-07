from app.db.models import PreflopChart
from app.domain.scenario import GameFormat
from app.recommend.ranges_prefill import PotType, PrefillQuery, prefill_ranges


def grid(classes: dict[str, float]):
    import pokercore

    names = pokercore.hand_class_names()
    return [classes.get(n, 0.0) for n in names]


def chart(session, **kw):
    base = dict(
        name="c",
        source="custom",
        game_format="cash",
        players=6,
        stack_bb=100.0,
        ante_bb=0.0,
        note="",
        vs_position=None,
        open_size_bb=2.5,
        rake=None,
    )
    base.update(kw)
    session.add(PreflopChart(**base))
    session.commit()


def q(**kw):
    base = dict(
        game_format=GameFormat.CASH,
        players=6,
        aggressor="BTN",
        caller="BB",
        pot_type=PotType.SRP,
        stack_bb=100.0,
    )
    base.update(kw)
    return PrefillQuery(**base)


def test_srp_uses_rfi_raise_and_vs_open_call(db_session):
    chart(
        db_session,
        position="BTN",
        situation="rfi",
        actions={"raise": grid({"AA": 1, "KK": 1})},
    )
    chart(
        db_session,
        position="BB",
        vs_position="BTN",
        situation="vs_open",
        actions={"call": grid({"QQ": 1, "JJ": 0.5}), "3bet": grid({"AA": 1})},
    )
    r = prefill_ranges(db_session, q())
    assert r.aggressor.text == "AA,KK" and not r.aggressor.approximate
    assert r.caller.text == "QQ,JJ:0.5"


def test_3bet_pot(db_session):
    chart(
        db_session,
        position="BB",
        vs_position="BTN",
        situation="vs_open",
        actions={"3bet": grid({"AA": 1})},
    )
    chart(
        db_session,
        position="BTN",
        vs_position="BB",
        situation="vs_3bet",
        actions={"call": grid({"QQ": 1})},
    )
    r = prefill_ranges(db_session, q(aggressor="BB", caller="BTN", pot_type=PotType.THREE_BET))
    assert r.aggressor.text == "AA"
    assert r.caller.text == "QQ"


def test_nearest_chart_is_marked_approximate(db_session):
    chart(
        db_session,
        position="BTN",
        situation="rfi",
        stack_bb=40.0,
        actions={"raise": grid({"AA": 1})},
    )
    r = prefill_ranges(db_session, q())
    assert r.aggressor.approximate
    assert any("Stack del rango" in n for n in r.aggressor.notes)


def test_missing_chart(db_session):
    r = prefill_ranges(db_session, q())
    assert r.aggressor.text is None
    assert r.aggressor.missing == "BTN RFI"
    assert r.caller.missing == "BB vs open de BTN"
