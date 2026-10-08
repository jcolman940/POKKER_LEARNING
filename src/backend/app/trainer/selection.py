"""Spot selection for a trainer session: relearn queue, due cards, new spots."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import PayoutStructure, PreflopChart, TrainerCard, TrainerSession
from app.domain.scenario import TOURNAMENT_FORMATS, GameFormat, Scenario
from app.leaks.finder import stack_bucket
from app.recommend.engine import recommend, recommend_from_chart
from app.recommend.preflop_equity import hand_class
from app.trainer.ranges import SITUATION_LABELS, generate_range_drill
from app.trainer.spots import (
    TrainerSpot,
    chart_usable,
    generate_chart,
    generate_pushfold,
    random_combo,
)
from app.trainer.srs import pick_kind

ATTEMPTS = 3


@dataclass
class ServedSpot:
    kind: str  # hand / range
    source: str  # pushfold / chart / range
    scenario: Scenario | None
    offered: list[str]
    title: str
    card: TrainerCard | None
    review: bool
    reference: dict  # server side only (recommendation or target grid)
    card_payload: dict  # what the card stores to regenerate the spot


class CardGone(Exception):
    """A card's chart no longer exists (or can no longer produce a spot)."""


class NoSpots(Exception):
    """Nothing matches the session (the API reports it as 409)."""


def aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _label(scenario: Scenario) -> str:
    sit = SITUATION_LABELS.get(scenario.situation.value, "") if scenario.situation else ""
    return f"{scenario.hero_position} · {sit} · {scenario.effective_stack_bb:g}bb"


def _hand_spot(
    session: Session, spot: TrainerSpot, card: TrainerCard | None, review: bool
) -> ServedSpot | None:
    chart = session.get(PreflopChart, spot.chart_id) if spot.chart_id else None
    if spot.source == "chart":
        if chart is None:
            return None
        rec = recommend_from_chart(chart, spot.scenario)  # the chart the spot came from
    else:
        rec = recommend(spot.scenario, session)
    if not rec.available or not rec.actions:
        return None
    title = _label(spot.scenario)
    return ServedSpot(
        kind="hand",
        source=spot.source,
        scenario=spot.scenario,
        offered=list(spot.offered),
        title=title,
        card=card,
        review=review,
        reference={
            "kind": "hand",
            "card_key": spot.card_key,
            "chart_id": spot.chart_id,
            "recommendation": rec.model_dump(mode="json"),
        },
        card_payload={
            "scenario": spot.scenario.model_dump(mode="json"),
            "offered": list(spot.offered),
            "chart_id": spot.chart_id,
            "title": title,
        },
    )


def _range_spot(
    chart: PreflopChart, action: str, title: str, key: str, card: TrainerCard | None, review: bool
) -> ServedSpot:
    return ServedSpot(
        kind="range",
        source="range",
        scenario=None,
        offered=[action],
        title=title,
        card=card,
        review=review,
        reference={
            "kind": "range",
            "card_key": key,
            "chart_id": chart.id,
            "action": action,
            "target": [float(v) for v in chart.actions[action]],
        },
        card_payload={"chart_id": chart.id, "action": action, "title": title},
    )


def _chart_offered(chart: PreflopChart) -> list[str]:
    present = [a for a, f in chart.actions.items() if a != "fold" and any(v > 0 for v in f)]
    return ["fold", *present]


# ------------------------------------------------------------------ card rebuild


def _other_combo(rng: random.Random, hand: str) -> str:
    cls = hand_class(hand)
    new = hand
    for _ in range(5):
        new = random_combo(rng, cls)
        if new != hand:
            break
    return new


def spot_from_card(session: Session, rng: random.Random, card: TrainerCard) -> ServedSpot | None:
    """Rebuild a reviewed card's spot (new combo of the same class).

    Raises CardGone when its chart is missing or unusable; returns None when the spot
    just cannot be built right now (the card is kept).
    """
    payload = card.scenario
    if card.source == "range":
        chart = session.get(PreflopChart, payload["chart_id"])
        action = payload["action"]
        if chart is None or not any(v > 0 for v in chart.actions.get(action, [])):
            raise CardGone
        return _range_spot(chart, action, payload["title"], card.key, card, True)
    scenario = Scenario(**payload["scenario"])
    scenario = scenario.model_copy(update={"hero_hand": _other_combo(rng, scenario.hero_hand)})
    offered = payload["offered"]
    chart_id = payload.get("chart_id")
    if card.source == "chart":
        chart = session.get(PreflopChart, chart_id) if chart_id else None
        if chart is None or chart_usable(chart) is None:
            raise CardGone
        offered = _chart_offered(chart)
    spot = TrainerSpot(card.source, scenario, offered, card.key, chart_id)
    return _hand_spot(session, spot, card, True)


def _passes(allowed: list | None, value) -> bool:
    return not allowed or value in allowed


def _matches(
    filters: dict, fmt: str, position: str, situation: str, stack: float, table: int | None
) -> bool:
    pushfold = GameFormat(fmt) in TOURNAMENT_FORMATS and stack <= get_settings().pushfold_max_bb
    return (
        _passes(filters.get("formats"), fmt)
        and _passes(filters.get("positions"), position)
        and _passes(filters.get("situations"), situation)
        and _passes(filters.get("stack_buckets"), stack_bucket(stack, pushfold))
        and (table is None or _passes(filters.get("table_sizes"), table))
    )


def card_matches(session: Session, card: TrainerCard, filters: dict) -> bool:
    payload = card.scenario
    if card.source == "range":
        chart = session.get(PreflopChart, payload["chart_id"])
        if chart is None:
            return True  # a missing chart archives the card when it is rebuilt
        return _matches(
            filters, chart.game_format, chart.position, chart.situation, chart.stack_bb, None
        )
    sc = payload["scenario"]
    table = sc["num_players"] if card.source == "pushfold" else None
    return _matches(
        filters, sc["format"], sc["hero_position"], sc["situation"], sc["effective_stack_bb"], table
    )


# -------------------------------------------------------------------- selection


def _new_spot(session: Session, rng: random.Random, ts: TrainerSession) -> ServedSpot | None:
    f = ts.filters
    payouts: list[float] = []
    if f.get("payout_id"):
        row = session.get(PayoutStructure, f["payout_id"])
        payouts = list(row.payouts) if row else []
    difficulty = f.get("difficulty", 50)
    sources = list(f.get("sources", []))
    rng.shuffle(sources)
    for source in sources:
        for _ in range(ATTEMPTS):
            if source == "range":
                drill = generate_range_drill(session, rng, f)
                if drill is None:
                    break
                chart = session.get(PreflopChart, drill.chart_id)
                return _range_spot(chart, drill.action, drill.title, drill.card_key, None, False)
            if source == "pushfold":
                spot = generate_pushfold(session, rng, f, payouts, difficulty)
            else:
                spot = generate_chart(session, rng, f, difficulty)
            if spot is None:
                break
            served = _hand_spot(session, spot, None, False)
            if served is not None:
                return served
    return None


def _first_usable(
    session: Session, rng: random.Random, cards: list[TrainerCard]
) -> ServedSpot | None:
    for card in cards:
        try:
            served = spot_from_card(session, rng, card)
        except CardGone:
            card.archived = True  # its chart is gone: retire it and try the next
            continue
        if served is not None:
            return served
    return None


def choose_spot(
    session: Session,
    rng: random.Random,
    ts: TrainerSession,
    now: datetime,
    last_card_id: int | None = None,
) -> ServedSpot:
    f = ts.filters
    mode = f.get("mode", "normal")
    cards = {
        c.id: c for c in session.scalars(select(TrainerCard).where(TrainerCard.archived.is_(False)))
    }
    if mode == "frequent":
        wanted = [cards[i] for i in f.get("card_ids") or [] if i in cards]
        wanted.sort(key=lambda c: (c.id == last_card_id, aware(c.due_at) or now, c.id))
        served = _first_usable(session, rng, wanted)
        if served is None:
            raise NoSpots("No hay spots para estos filtros")
        return served

    due_relearn = [
        e for e in ts.relearn if e["due_after"] <= ts.spots_served and e["card_id"] in cards
    ]
    waiting = {e["card_id"] for e in ts.relearn}  # failed cards wait their 3-5 spots
    due = [
        c
        for c in cards.values()
        if c.id not in waiting
        and c.source in f.get("sources", [])
        and c.due_at is not None
        and aware(c.due_at) <= now
        and card_matches(session, c, f)
    ]
    due.sort(key=lambda c: (aware(c.due_at), c.id))
    kind = pick_kind(rng, bool(due), bool(due_relearn))
    if f.get("prefer_due") and kind == "new" and due:
        kind = "due"  # the leaks bridge asks for overdue cards before new spots
    if mode == "review" and kind == "new":
        kind = "due"
    if kind == "relearn":
        served = _first_usable(session, rng, [cards[e["card_id"]] for e in due_relearn])
        if served is not None:
            return served
        kind = "due"
    if kind == "due":
        served = _first_usable(session, rng, due)
        if served is not None:
            return served
        if mode == "review":
            raise NoSpots("No hay repasos pendientes")
    served = _new_spot(session, rng, ts)
    if served is None:
        raise NoSpots("No hay spots para estos filtros")
    return served
