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
