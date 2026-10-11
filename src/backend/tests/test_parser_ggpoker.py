"""GGPoker parser, closed against the real tournament samples in
tests/fixtures/hand_histories/ggpoker (exported by the user from GGPoker)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.domain.hand import ActionType
from app.domain.scenario import GameFormat, Street
from app.parsers import detect_parser
from app.parsers.base import RawHand
from app.parsers.ggpoker import GGPokerParser

SAMPLES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "hand_histories" / "ggpoker"
CLASSIC = SAMPLES / "mtt-daily-classic.txt"
HYPER = SAMPLES / "mtt-daily-hyper.txt"

parser = GGPokerParser()


def hand(path: Path, hand_id: str):
    raws = parser.split(path.read_text(encoding="utf-8"))
    raw = next(r for r in raws if r.text.startswith(f"Poker Hand #{hand_id}:"))
    return parser.parse(raw)


def test_detects_gg_files_only():
    text = CLASSIC.read_text(encoding="utf-8")
    assert parser.detect(text)
    assert not parser.detect("PokerStars Hand #1: Tournament #2, $1+$0.10 USD Hold'em No Limit")
    assert not parser.detect("#FAKE-HAND\n{}")


def test_splits_every_hand_with_its_line():
    raws = parser.split(CLASSIC.read_text(encoding="utf-8"))
    assert len(raws) == 30
    assert raws[0].start_line == 1
    assert raws[1].text.startswith("Poker Hand #TM6518182972:")
    lines = CLASSIC.read_text(encoding="utf-8").splitlines()
    assert lines[raws[1].start_line - 1].startswith("Poker Hand #TM6518182972:")


def test_header_seats_and_hero():
    r = hand(CLASSIC, "TM6518182981")
    assert r.site == "ggpoker"
    assert r.hand_id == "TM6518182981"
    assert r.game_type == GameFormat.MTT
    assert r.tournament.tournament_id == "317477887"
    assert r.tournament.level == "9"
    assert r.tournament.currency == "USD"
    assert (r.sb, r.bb, r.ante) == (225, 450, 55)
    assert r.table_name == "7"
    assert r.max_seats == 8
    assert r.button_seat == 7
    assert len(r.seats) == 8
    assert r.stack_of("Hero") == 5128
    assert r.stack_of("2d3c11b9") == 31688
    assert r.hero == "Hero"
    assert r.hero_cards == "8d8c"
    assert r.positions()["Hero"] == "HJ"
    # Hand times are the player's local time; stored timezone-aware.
    assert r.played_at.tzinfo is not None
    assert r.played_at == datetime(2026, 10, 10, 15, 19, 9).astimezone()


def test_preflop_all_in_with_uncalled_return():
    r = hand(CLASSIC, "TM6518182981")
    posts = [a for a in r.actions if a.type == ActionType.POST_ANTE]
    assert len(posts) == 8 and all(a.amount == 55 for a in posts)
    sb, bb = (
        next(a for a in r.actions if a.type == t) for t in (ActionType.POST_SB, ActionType.POST_BB)
    )
    assert (sb.player, sb.amount, bb.player, bb.amount) == ("b9348ed5", 225, "4173e6c", 450)

    hero_raise, shove, hero_call = (
        a for a in r.actions if a.type in (ActionType.RAISE, ActionType.CALL)
    )
    assert (hero_raise.player, hero_raise.amount, hero_raise.to_amount) == ("Hero", 900, 900)
    assert (shove.player, shove.amount, shove.to_amount, shove.all_in) == (
        "1acb366d",
        12248,
        12248,
        True,
    )
    assert (hero_call.amount, hero_call.all_in) == (4173, True)
    ret = next(a for a in r.actions if a.type == ActionType.RETURN)
    assert (ret.player, ret.amount, ret.street) == ("1acb366d", 7175, Street.PREFLOP)

    assert r.board == "5hQsAh3dQh"
    assert r.shown == {"1acb366d": "AsKd", "Hero": "8d8c"}
    assert r.collected == {"1acb366d": 11261}
    assert r.rake == 0


def test_postflop_streets_and_fold():
    r = hand(HYPER, "TM6518444548")
    assert r.game_type == GameFormat.MTT
    assert (r.sb, r.bb, r.ante, r.max_seats) == (50, 100, 12, 6)
    hero_call = next(a for a in r.actions if a.player == "Hero" and a.type == ActionType.CALL)
    assert (hero_call.street, hero_call.amount) == (Street.PREFLOP, 100)
    flop = [a for a in r.actions if a.street == Street.FLOP]
    assert [(a.player, a.type, a.amount) for a in flop] == [
        ("Hero", ActionType.CHECK, 0),
        ("7fb21414", ActionType.BET, 173),
        ("Hero", ActionType.FOLD, 0),
        ("7fb21414", ActionType.RETURN, 173),
    ]
    assert r.board == "ThAhQc"
    assert r.shown == {}
    assert r.collected == {"7fb21414": 522}


def test_side_pots_add_up_per_player():
    r = hand(CLASSIC, "TM6518182512")
    assert r.collected == {"18f7b434": 26536}
    shove = next(a for a in r.actions if a.player == "18f7b434" and a.to_amount == 25219)
    # It had 750 in already: the raise moves the rest.
    assert shove.amount == 25219 - 750
    assert r.shown == {"18f7b434": "AcAs", "5bdbad84": "4s5d", "1f3f9496": "9dQd"}


def test_short_big_blind_is_all_in():
    r = hand(HYPER, "TM6519809083")
    bb = next(a for a in r.actions if a.type == ActionType.POST_BB)
    assert (bb.player, bb.amount, bb.all_in) == ("4a7384e6", 1314, True)
    hero_raise = next(a for a in r.actions if a.player == "Hero" and a.type == ActionType.RAISE)
    assert (hero_raise.amount, hero_raise.to_amount) == (3200, 3200)
    assert r.collected == {"Hero": 9714}
    assert r.shown == {"Hero": "AcKs", "4a7384e6": "2c7d"}


@pytest.mark.parametrize("path", [CLASSIC, HYPER], ids=["classic", "hyper"])
def test_every_sample_hand_parses_and_chips_add_up(path):
    raws = parser.split(path.read_text(encoding="utf-8"))
    assert raws
    for raw in raws:
        r = parser.parse(raw)
        assert r.hero == "Hero"
        put_in = sum(r.contributions().values())
        assert put_in == pytest.approx(sum(r.collected.values()) + r.rake), r.hand_id
        for seat in r.seats:
            assert r.contributions()[seat.name] <= seat.stack, (r.hand_id, seat.name)


def test_formats_from_the_tournament_name():
    text = HYPER.read_text(encoding="utf-8")
    first = parser.split(text)[0].text
    spin = first.replace("Daily Hyper $3", "Spin & Gold #5 $1", 1)
    assert parser.parse(RawHand(spin, 1)).game_type == GameFormat.SPIN


def test_bad_action_line_reports_its_line():
    raw = parser.split(CLASSIC.read_text(encoding="utf-8"))[0]
    lines = raw.text.splitlines()
    index = lines.index("Hero: raises 450 to 900")
    lines[index] = "Hero: dances 450"
    with pytest.raises(ValueError) as info:
        parser.parse(RawHand("\n".join(lines), 1))
    assert getattr(info.value, "line", None) == index + 1


def test_registered_and_detected_by_content():
    found = detect_parser(HYPER.read_text(encoding="utf-8"))
    assert found is not None and found.site == "ggpoker"


def test_import_endpoint_reads_the_samples(db_session):
    from app.parsers.importer import import_files

    files = [(p.name, p.read_bytes()) for p in (CLASSIC, HYPER)]
    _, report = import_files(db_session, files)
    assert report.totals["failed"] == 0, report.errors
    assert report.totals["imported"] == 133
    _, again = import_files(db_session, files)
    assert again.totals["duplicates"] == 133


SUMMARY_CLASSIC = SAMPLES / "summary-daily-classic.txt"
SUMMARY_HYPER = SAMPLES / "summary-daily-hyper.txt"


def test_tournament_summary():
    s = parser.parse_summary(SUMMARY_HYPER.read_text(encoding="utf-8"))
    assert s is not None
    assert (s.site, s.tournament_id, s.game_type) == ("ggpoker", "317487008", GameFormat.MTT)
    assert (s.buy_in, s.fee, s.currency) == (2.76, 0.24, "USD")
    assert (s.finish, s.prize, s.entrants) == (70, 10.93, 1734)
    assert s.played_at == datetime(2026, 10, 10, 14, 45).astimezone()

    out = parser.parse_summary(SUMMARY_CLASSIC.read_text(encoding="utf-8"))
    assert (out.finish, out.prize, out.entrants, out.buy_in) == (833, 0, 1333, 1.84)


def test_hand_files_are_not_summaries():
    assert parser.parse_summary(CLASSIC.read_text(encoding="utf-8")) is None
    assert parser.parse_summary("some unknown text") is None


def test_broken_summary_reports_its_line():
    text = SUMMARY_HYPER.read_text(encoding="utf-8").replace("Buy-in: $2.76+$0.24", "Buy-in: ???")
    with pytest.raises(ValueError) as info:
        parser.parse_summary(text)
    assert getattr(info.value, "line", None) == 2


def test_import_summaries_feed_tournament_stats(client):
    files = [
        ("files", (p.name, p.read_bytes(), "text/plain"))
        for p in (CLASSIC, HYPER, SUMMARY_CLASSIC, SUMMARY_HYPER)
    ]
    report = client.post("/api/imports", files=files).json()["report"]
    assert report["totals"]["imported"] == 133
    assert report["totals"]["tournaments"] == 2
    assert report["totals"]["failed"] == 0 and report["errors"] == []
    summary_files = [f for f in report["files"] if f["name"].startswith("summary")]
    assert [(f["site"], f["tournaments"], f["hands"]) for f in summary_files] == [
        ("ggpoker", 1, 0),
        ("ggpoker", 1, 0),
    ]

    stats = client.get("/api/stats/tournaments").json()
    assert stats["tournaments"] == 2
    # Cost 2 + 3 = 5, prize 10.93: ROI is the mean profit over the mean cost.
    assert stats["roi"]["value"] == pytest.approx((10.93 - 5) / 2 / 2.5 * 100)
    assert stats["itm"]["value"] == pytest.approx(50)

    again = client.post("/api/imports", files=files).json()["report"]
    assert again["totals"]["tournaments"] == 2
    assert client.get("/api/stats/tournaments").json()["tournaments"] == 2
