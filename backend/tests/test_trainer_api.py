import random

import pytest

from app.api.trainer import get_rng
from app.db.models import PreflopChart, TrainerCard
from app.db.session import _session_factory
from app.domain.scenario import Scenario
from app.recommend.engine import recommend
from app.recommend.preflop_equity import class_names

FORBIDDEN = {"recommendation", "reference", "actions", "frequency", "ev"}


@pytest.fixture
def seeded(client):
    rng = random.Random(11)
    client.app.dependency_overrides[get_rng] = lambda: rng
    yield rng
    client.app.dependency_overrides.pop(get_rng, None)


def _grid(**by_class: float) -> list[float]:
    return [by_class.get(n, 0.0) for n in class_names()]


def _add_chart() -> int:
    with _session_factory()() as s:
        chart = PreflopChart(
            name="BTN RFI",
            source="custom",
            game_format="cash",
            players=6,
            position="BTN",
            stack_bb=100.0,
            situation="rfi",
            actions={"raise": _grid(AA=1.0, KK=1.0, QQ=1.0, AKs=0.5, AKo=1.0)},
        )
        s.add(chart)
        s.commit()
        return chart.id


def _session(client, **kw) -> int:
    body = {"sources": ["pushfold"], "difficulty": 0} | kw
    r = client.post("/api/trainer/sessions", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _keys(obj) -> set[str]:
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in _keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in _keys(v)}
    return set()


def _pick_action(spot, worst: bool) -> str:
    """The offered action with the lowest (or highest) EV, computed independently of the API."""
    with _session_factory()() as s:
        rec = recommend(Scenario(**spot["scenario"]), s)
    evs = {a.action: a.ev for a in rec.actions}
    return (min if worst else max)(evs, key=lambda k: evs[k])


def _next(client, sid) -> dict:
    r = client.post(f"/api/trainer/sessions/{sid}/next")
    assert r.status_code == 200, r.text
    return r.json()


def test_sources_without_charts(client):
    data = client.get("/api/trainer/sources").json()
    assert data["pushfold"]["available"] is True
    assert data["chart"]["available"] is False and data["chart"]["reason"]
    assert data["range"]["available"] is False
    _add_chart()
    data = client.get("/api/trainer/sources").json()
    assert data["chart"]["available"] and data["range"]["available"]


def test_pushfold_cycle_hides_reference(client, seeded):
    sid = _session(client)
    spot = _next(client, sid)
    assert spot["kind"] == "hand" and spot["source"] == "pushfold"
    assert spot["card_id"] is None and spot["review"] is False
    assert not (_keys(spot) & FORBIDDEN)
    assert spot["offered"] in (["allin", "fold"], ["call", "fold"])
    fb = client.post(f"/api/trainer/spots/{spot['spot_id']}/answer", json={"action": "fold"})
    assert fb.status_code == 200, fb.text
    data = fb.json()
    assert data["verdict"] in ("correct", "error")
    assert data["recommendation"]["available"] and data["recommendation"]["actions"]
    assert len(data["reference_layers"]) == 1
    assert len(data["reference_layers"][0]["grid"]) == 169
    assert data["reference_layers"][0]["action"] in ("allin", "call")
    assert 0 <= data["hand_index"] < 169
    assert data["range"] is None
    assert data["card"]["due_at"] and data["card"]["ease"] > 0


def test_unknown_action_is_422(client, seeded):
    sid = _session(client)
    spot = _next(client, sid)
    r = client.post(f"/api/trainer/spots/{spot['spot_id']}/answer", json={"action": "raise"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Acción no disponible en este spot"
    assert client.post("/api/trainer/spots/nope/answer", json={"action": "fold"}).status_code == 404


def test_answer_is_idempotent(client, seeded):
    sid = _session(client)
    spot = _next(client, sid)
    url = f"/api/trainer/spots/{spot['spot_id']}/answer"
    first = client.post(url, json={"action": "fold"}).json()
    again = client.post(url, json={"action": spot["offered"][0]}).json()
    assert again == first
    with _session_factory()() as s:
        card = s.query(TrainerCard).one()
        assert card.reps == 1


def _answer_error(client, spot) -> dict:
    return client.post(
        f"/api/trainer/spots/{spot['spot_id']}/answer", json={"action": _pick_action(spot, True)}
    ).json()


def test_error_comes_back_in_three_to_five_spots(client, seeded):
    sid = _session(client)
    for _ in range(40):
        spot = _next(client, sid)
        if _answer_error(client, spot)["verdict"] == "error":
            break
    else:
        pytest.fail("no error verdict in 40 spots")
    with _session_factory()() as s:
        failed = s.query(TrainerCard).filter(TrainerCard.lapses > 0).one()
        assert failed.interval_days == 0
        card_id = failed.id
    seen_at = None
    for i in range(1, 9):
        spot = _next(client, sid)
        if spot["card_id"] == card_id and spot["review"]:
            seen_at = i
            break
        best = _pick_action(spot, False)
        client.post(f"/api/trainer/spots/{spot['spot_id']}/answer", json={"action": best})
    # 3 to 5 spots in between: it is the 4th to 6th served after the failed one
    assert seen_at is not None and 4 <= seen_at <= 6


def test_chart_only_session_without_tables_is_422(client):
    r = client.post("/api/trainer/sessions", json={"sources": ["chart"]})
    assert r.status_code == 422
    assert "rangos" in r.json()["detail"].lower()
    r = client.post("/api/trainer/sessions", json={"sources": []})
    assert r.status_code == 422


def test_review_without_due_cards_is_409(client, seeded):
    sid = _session(client, mode="review")
    r = client.post(f"/api/trainer/sessions/{sid}/next")
    assert r.status_code == 409
    assert r.json()["detail"] == "No hay repasos pendientes"


def test_no_spots_for_filters_is_409(client, seeded):
    sid = _session(client, formats=["cash"])
    r = client.post(f"/api/trainer/sessions/{sid}/next")
    assert r.status_code == 409
    assert r.json()["detail"] == "No hay spots para estos filtros"


def test_unknown_session_is_404(client):
    assert client.post("/api/trainer/sessions/999/next").status_code == 404
    assert client.get("/api/trainer/sessions/999").status_code == 404


def test_payouts_crud(client):
    listed = client.get("/api/trainer/payouts").json()
    builtin = [p for p in listed if p["builtin"]]
    assert len(builtin) == 2
    r = client.delete(f"/api/trainer/payouts/{builtin[0]['id']}")
    assert r.status_code == 422
    r = client.post("/api/trainer/payouts", json={"name": "Mi mesa final", "payouts": [50, 30, 20]})
    assert r.status_code == 201
    pid = r.json()["id"]
    dup = client.post("/api/trainer/payouts", json={"name": "Mi mesa final", "payouts": [60, 40]})
    assert dup.status_code == 422
    assert client.post("/api/trainer/payouts", json={"name": "x", "payouts": []}).status_code == 422
    assert client.delete(f"/api/trainer/payouts/{pid}").status_code == 204
    assert client.delete(f"/api/trainer/payouts/{pid}").status_code == 404


def test_icm_session_uses_payouts(client, seeded):
    pid = client.get("/api/trainer/payouts").json()[0]["id"]
    sid = _session(client, payout_id=pid)
    spot = _next(client, sid)
    assert spot["scenario"]["payouts"]
    bad = client.post("/api/trainer/sessions", json={"sources": ["pushfold"], "payout_id": 9999})
    assert bad.status_code == 422


def test_chart_hand_spot_has_chart_layers(client, seeded):
    chart_id = _add_chart()
    sid = _session(client, sources=["chart"], difficulty=100)
    spot = _next(client, sid)
    assert spot["source"] == "chart" and "fold" in spot["offered"]
    assert not (_keys(spot) & FORBIDDEN)
    data = client.post(
        f"/api/trainer/spots/{spot['spot_id']}/answer", json={"action": "fold"}
    ).json()
    assert data["approximate"] is True and data["loss_unit"] == "freq"
    assert [layer["action"] for layer in data["reference_layers"]] == ["raise"]
    with _session_factory()() as s:
        s.delete(s.get(PreflopChart, chart_id))
        s.commit()
    # the card's chart is gone: the stored feedback is unchanged
    again = client.post(
        f"/api/trainer/spots/{spot['spot_id']}/answer", json={"action": "fold"}
    ).json()
    assert again == data


def test_range_drill_cycle(client, seeded):
    _add_chart()
    sid = _session(client, sources=["range"])
    spot = _next(client, sid)
    assert spot["kind"] == "range" and spot["source"] == "range"
    assert spot["scenario"] is None and spot["offered"] == ["raise"]
    assert not (_keys(spot) & FORBIDDEN)
    target = _grid(AA=1.0, KK=1.0, QQ=1.0, AKs=0.5, AKo=1.0)
    r = client.post(f"/api/trainer/spots/{spot['spot_id']}/answer", json={"painted": target})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["verdict"] == "correct" and data["range"]["precision"] == pytest.approx(1.0)
    assert data["recommendation"] is None and data["reference_layers"] == []
    assert len(data["range"]["target"]) == 169 and len(data["range"]["diff_grid"]) == 169
    bad = _next(client, sid)
    r = client.post(f"/api/trainer/spots/{bad['spot_id']}/answer", json={"painted": [1.0] * 5})
    assert r.status_code == 422
    both = client.post(
        f"/api/trainer/spots/{bad['spot_id']}/answer", json={"painted": target, "action": "x"}
    )
    assert both.status_code == 422


def test_summary_and_frequent_errors(client, seeded):
    sid = _session(client)
    assert client.get(f"/api/trainer/sessions/{sid}").json()["spots"] == 0
    losses = []
    for _ in range(8):
        spot = _next(client, sid)
        fb = _answer_error(client, spot)
        losses.append(fb)
    summary = client.get(f"/api/trainer/sessions/{sid}").json()
    assert summary["spots"] == 8
    assert summary["correct"] + summary["acceptable"] + summary["error"] == 8
    assert summary["error"] == sum(f["verdict"] == "error" for f in losses)
    assert summary["ev_loss_bb"] == pytest.approx(sum(f["loss"] for f in losses))
    assert summary["avg_freq_error"] is None and summary["avg_precision"] is None
    errs = client.get("/api/trainer/frequent-errors?limit=3").json()
    assert len(errs) <= 3
    assert all(e["lapses"] >= 1 and e["label"] and e["source"] == "pushfold" for e in errs)
    assert [e["lapses"] for e in errs] == sorted((e["lapses"] for e in errs), reverse=True)


def test_frequent_mode_serves_chosen_cards(client, seeded):
    sid = _session(client)
    for _ in range(6):
        _answer_error(client, _next(client, sid))
    errs = client.get("/api/trainer/frequent-errors").json()
    assert errs
    ids = [e["card_id"] for e in errs]
    sid2 = _session(client, mode="frequent", card_ids=ids)
    for _ in range(4):
        spot = _next(client, sid2)
        assert spot["card_id"] in ids and spot["review"] is True
    none = client.post("/api/trainer/sessions", json={"sources": ["pushfold"], "mode": "frequent"})
    assert none.status_code == 422
