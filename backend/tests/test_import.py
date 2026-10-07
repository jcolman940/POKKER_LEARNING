import io
import zipfile

import pytest

from app.parsers.base import split_on
from app.parsers.importer import decode
from tests.fake_parser import fake_file
from tests.hands import act, make_hand


def hand(hand_id: str, net: float = 1.0, **kw):
    # Hero (BB) checks behind a limp... simplest winning/losing hand.
    return make_hand(
        {"V": 100, "Hero": 100},
        [act("p", "V", "raise", 2.5), act("p", "Hero", "fold")]
        if net < 0
        else [act("p", "V", "fold")],
        button="V",
        hand_id=hand_id,
        site="fake",
        collected={"Hero": 1.5} if net >= 0 else {"V": 4.0},
        **kw,
    )


def upload(client, *files: tuple[str, bytes]):
    resp = client.post(
        "/api/imports", files=[("files", (name, data, "text/plain")) for name, data in files]
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["report"]


def test_unknown_room_is_reported_not_fatal(client):
    report = upload(client, ("x.txt", b"some unknown text"))
    assert report["totals"]["imported"] == 0
    assert "No se reconoce la sala" in report["errors"][0]["message"]
    assert client.get("/api/parsers").json() == []


def test_import_is_idempotent_and_reports_failures(client, fake_room):
    good = fake_file(hand("1"), hand("2", net=-1), "{ not json", hand("2"))
    report = upload(client, ("a.txt", good))
    assert report["totals"] == {
        "files": 1,
        "hands_found": 4,
        "imported": 2,
        "duplicates": 1,
        "failed": 1,
    }
    err = report["errors"][0]
    assert err["hand"] == 3 and "JSON inválido" in err["message"]
    assert err["line"] > 1 and err["excerpt"]

    again = upload(client, ("a.txt", good))
    assert again["totals"]["imported"] == 0
    assert again["totals"]["duplicates"] == 3

    hands = client.get("/api/hands").json()
    assert hands["total"] == 2
    assert {h["hand_id"] for h in hands["items"]} == {"1", "2"}
    assert len(client.get("/api/imports").json()) == 2


def test_zip_import_and_encodings(client, fake_room):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("hh/day1.txt", fake_file(hand("10")))
        z.writestr("hh/day2.txt", fake_file(hand("11")).decode().encode("utf-16"))
        z.writestr("__MACOSX/._day1.txt", b"junk")
        z.writestr("notes.pdf", b"%PDF")
    report = upload(client, ("hands.zip", buffer.getvalue()))
    assert report["totals"]["imported"] == 2
    assert [f["name"] for f in report["files"]] == [
        "hands.zip/hh/day1.txt",
        "hands.zip/hh/day2.txt",
    ]

    broken = upload(client, ("bad.zip", b"not a zip"))
    assert "dañado" in broken["errors"][0]["message"]


def test_hero_fallback_from_settings(client, fake_room, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "hero_names", ["Hero"])
    upload(client, ("a.txt", fake_file(hand("5", hero=None, hero_cards=None))))
    item = client.get("/api/hands").json()["items"][0]
    assert item["position"] == "BB"


def test_split_and_decode_helpers():
    import re

    raws = split_on(re.compile(r"^HAND"), "junk\nHAND 1\na\n\nHAND 2\nb\n")
    assert [(r.start_line, r.text) for r in raws] == [(2, "HAND 1\na"), (5, "HAND 2\nb")]
    assert decode("ñ".encode("cp1252")) == "ñ"
    assert decode("﻿hola".encode()) == "hola"


@pytest.mark.parametrize("path", ["/api/hands/999", "/api/hands/999/replay"])
def test_missing_hand(client, path):
    resp = client.get(path) if path.endswith("999") else client.post(path, json={})
    assert resp.status_code == 404
