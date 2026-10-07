from app.domain.scenario import GameFormat
from app.stats.decisions import extract_decisions
from tests.hands import act, make_hand

SIX = {"U": 100, "H": 100, "C": 100, "Hero": 100, "S": 100, "B": 100}  # Hero on BTN


def d(record):
    return [
        (x.idx, x.position, x.situation, x.vs_position, x.action) for x in extract_decisions(record)
    ]


def test_rfi_open():
    r = make_hand(
        SIX,
        [
            act("p", "U", "fold"),
            act("p", "H", "fold"),
            act("p", "C", "fold"),
            act("p", "Hero", "raise", 2.5),
        ],
        button="Hero",
        hero_cards="AhKh",
    )
    assert d(r) == [(1, "BTN", "rfi", None, "raise")]
    assert extract_decisions(r)[0].hand_class == "AKs"
    assert extract_decisions(r)[0].stack_bb == 100.0


def test_fold_vs_open():
    r = make_hand(
        SIX,
        [
            act("p", "U", "fold"),
            act("p", "H", "fold"),
            act("p", "C", "raise", 2.5),
            act("p", "Hero", "fold"),
        ],
        button="Hero",
    )
    assert d(r) == [(1, "BTN", "vs_open", "CO", "fold")]


def test_open_then_fold_to_3bet_gives_two_decisions():
    r = make_hand(
        SIX,
        [
            act("p", "U", "fold"),
            act("p", "H", "fold"),
            act("p", "C", "fold"),
            act("p", "Hero", "raise", 2.5),
            act("p", "S", "raise", 11),
            act("p", "B", "fold"),
            act("p", "Hero", "fold"),
        ],
        button="Hero",
    )
    assert d(r) == [(1, "BTN", "rfi", None, "raise"), (2, "BTN", "vs_3bet", "SB", "fold")]


def test_limp_and_3bet_labels():
    r = make_hand(
        SIX,
        [
            act("p", "U", "call", 1),
            act("p", "H", "fold"),
            act("p", "C", "fold"),
            act("p", "Hero", "call", 1),
        ],
        button="Hero",
    )
    assert d(r)[0][4] == "limp"
    r2 = make_hand(
        SIX,
        [
            act("p", "U", "raise", 2.5),
            act("p", "H", "fold"),
            act("p", "C", "fold"),
            act("p", "Hero", "raise", 8),
        ],
        button="Hero",
    )
    assert d(r2)[0][4] == "3bet"


def test_bb_check_is_not_a_decision():
    r = make_hand(
        {"S": 100, "Hero": 100}, [act("p", "S", "call", 0.5), act("p", "Hero", "check")], button="S"
    )
    assert extract_decisions(r) == []


def test_pushfold_spot_in_tournament():
    stacks = {"U": 20, "H": 30, "C": 25, "Hero": 10, "S": 40, "B": 15}
    r = make_hand(
        stacks,
        [
            act("p", "U", "fold"),
            act("p", "H", "fold"),
            act("p", "C", "fold"),
            act("p", "Hero", "raise", 10, all_in=True),
        ],
        button="Hero",
        ante=0.125,
        game_type=GameFormat.MTT,
    )
    (dec,) = extract_decisions(r)
    assert dec.action == "allin" and dec.situation == "rfi"
    assert dec.spot["stacks_bb"]["BTN"] == 10.0 and dec.spot["ante_bb"] == 0.125


def test_no_hero_no_decisions():
    r = make_hand(SIX, [act("p", "U", "fold")], button="Hero", hero=None)
    assert extract_decisions(r) == []


def test_import_stores_decisions_and_backfill_is_idempotent(client, fake_room):
    from app.db.models import HandDecision
    from app.db.session import _session_factory
    from app.stats.decisions import backfill_decisions
    from tests.fake_parser import fake_file

    r = make_hand(
        SIX,
        [
            act("p", "U", "fold"),
            act("p", "H", "fold"),
            act("p", "C", "fold"),
            act("p", "Hero", "raise", 2.5),
        ],
        button="Hero",
    )
    resp = client.post("/api/imports", files={"files": ("h.txt", fake_file(r), "text/plain")})
    assert resp.status_code == 200
    with _session_factory()() as s:
        assert s.query(HandDecision).count() == 1
        assert backfill_decisions(s) == 0  # already at current version


def _hand_rows(session, n):
    from app.parsers.importer import hand_row

    for i in range(n):
        r = make_hand(
            SIX,
            [
                act("p", "U", "fold"),
                act("p", "H", "fold"),
                act("p", "C", "fold"),
                act("p", "Hero", "raise", 2.5),
            ],
            button="Hero",
            hand_id=str(100 + i),
        )
        session.add(hand_row(r, "", None))
    session.commit()


def _reset_version(session):
    from app.db.models import AppMeta, HandDecision
    from app.stats.decisions import VERSION_KEY

    session.query(HandDecision).delete()
    session.query(AppMeta).filter(AppMeta.key == VERSION_KEY).delete()
    session.commit()


def test_backfill_recomputes_when_version_cleared(db_session):
    from app.db.models import HandDecision
    from app.stats.decisions import backfill_decisions

    _hand_rows(db_session, 3)
    _reset_version(db_session)
    assert backfill_decisions(db_session) == 3
    assert db_session.query(HandDecision).count() == 3
    assert backfill_decisions(db_session) == 0


def test_backfill_skips_corrupted_records(db_session, caplog):
    from app.db.models import Hand, HandDecision
    from app.stats.decisions import backfill_decisions

    _hand_rows(db_session, 3)
    bad = db_session.query(Hand).first()
    record = dict(bad.record)
    del record["seats"]
    bad.record = record
    db_session.commit()
    _reset_version(db_session)
    with caplog.at_level("WARNING"):
        assert backfill_decisions(db_session) == 2
    assert db_session.query(HandDecision).count() == 2
    assert "1" in caplog.text and "skipped" in caplog.text
    assert backfill_decisions(db_session) == 0


def test_app_boots_with_a_corrupted_stored_record(client):
    from fastapi.testclient import TestClient

    from app.db.models import AppMeta, Hand
    from app.db.session import _session_factory
    from app.main import create_app
    from app.stats.decisions import VERSION_KEY

    with _session_factory()() as s:
        _hand_rows(s, 2)
        h = s.query(Hand).first()
        record = dict(h.record)
        del record["seats"]
        h.record = record
        s.query(AppMeta).filter(AppMeta.key == VERSION_KEY).delete()
        s.commit()
    with TestClient(create_app()) as c2:
        assert c2.get("/api/version").status_code == 200


def test_lifespan_survives_unexpected_backfill_failure(client, monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as main

    def boom(_session):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(main, "backfill_decisions", boom)
    with TestClient(main.create_app()) as c2:
        assert c2.get("/api/version").status_code == 200


def _tourney(actions, stacks):
    return make_hand(stacks, actions, button="Hero", game_type=GameFormat.MTT, ante=0.125)


def test_pushfold_spot_only_for_cold_decisions():
    stacks = {"U": 12, "H": 12, "C": 12, "Hero": 12, "S": 12, "B": 12}
    # BTN opens 2.2, SB shoves, BTN calls: decision 2 is not cold.
    r = _tourney(
        [
            act("p", "U", "fold"),
            act("p", "H", "fold"),
            act("p", "C", "fold"),
            act("p", "Hero", "raise", 2.2),
            act("p", "S", "raise", 12, all_in=True),
            act("p", "B", "fold"),
            act("p", "Hero", "call", 12),
        ],
        stacks,
    )
    decs = extract_decisions(r)
    assert [x.idx for x in decs] == [1, 2]
    assert decs[0].spot is not None
    assert decs[1].situation == "vs_allin" and decs[1].spot is None
    # Cold vs a shove keeps its spot.
    r2 = _tourney(
        [
            act("p", "U", "fold"),
            act("p", "H", "fold"),
            act("p", "C", "raise", 12, all_in=True),
            act("p", "Hero", "call", 12),
        ],
        stacks,
    )
    (dec,) = extract_decisions(r2)
    assert dec.situation == "vs_allin" and dec.spot is not None


def test_limp_then_shove_is_not_cold():
    stacks = {"U": 12, "H": 12, "C": 12, "Hero": 12, "S": 12, "B": 12}
    r = _tourney(
        [
            act("p", "U", "fold"),
            act("p", "H", "fold"),
            act("p", "C", "fold"),
            act("p", "Hero", "call", 1),
            act("p", "S", "raise", 12, all_in=True),
            act("p", "B", "fold"),
            act("p", "Hero", "call", 12),
        ],
        stacks,
    )
    decs = extract_decisions(r)
    assert decs[0].action == "limp"
    assert all(x.spot is None for x in decs[1:])


def test_decisions_version_is_bumped():
    from app.stats.decisions import DECISIONS_VERSION

    assert DECISIONS_VERSION == 2
