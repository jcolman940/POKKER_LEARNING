"""Trainer sessions: serving spots, scoring answers, scheduling cards, summaries."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    PayoutStructure,
    PreflopChart,
    TrainerAttempt,
    TrainerCard,
    TrainerSession,
)
from app.domain.positions import preflop_order
from app.domain.scenario import Scenario, Situation
from app.recommend.engine import solve_spot
from app.recommend.preflop_equity import class_index, hand_class
from app.recommend.schemas import RecommendationOut
from app.trainer.ranges import score_range
from app.trainer.scoring import score_hand
from app.trainer.selection import NoSpots, ServedSpot, aware, choose_spot
from app.trainer.spots import _chart_usable
from app.trainer.srs import INITIAL_EASE, CardState, relearn_offset, schedule

SOURCES = ("pushfold", "chart", "range")
MODES = ("normal", "review", "frequent")
CHART_HINT = "Cargá rangos en la sección Rangos preflop para entrenar con tus tablas."
RANGE_HINT = "Cargá rangos en la sección Rangos preflop para practicar pintando."


class SpotNotFound(LookupError):
    pass


class SessionNotFound(LookupError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


# -------------------------------------------------------------------- sources


def source_status(session: Session) -> dict[str, dict]:
    charts = list(session.scalars(select(PreflopChart)))
    chart_ok = any(_chart_usable(c) is not None for c in charts)
    range_ok = any(any(any(v > 0 for v in f) for f in c.actions.values()) for c in charts)
    return {
        "pushfold": {"available": True, "reason": None},
        "chart": {"available": chart_ok, "reason": None if chart_ok else CHART_HINT},
        "range": {"available": range_ok, "reason": None if range_ok else RANGE_HINT},
    }


# ------------------------------------------------------------------- payouts


def create_payout(session: Session, name: str, payouts: list[float]) -> PayoutStructure:
    name = name.strip()
    if not name:
        raise ValueError("Poné un nombre para la estructura de premios")
    if not payouts or any(p < 0 for p in payouts) or sum(payouts) <= 0:
        raise ValueError("Los premios deben ser positivos y sumar más de cero")
    row = PayoutStructure(name=name, payouts=[float(p) for p in payouts], builtin=False)
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ValueError("Ya existe una estructura con ese nombre") from None
    return row


def delete_payout(session: Session, payout_id: int) -> bool:
    row = session.get(PayoutStructure, payout_id)
    if row is None:
        return False
    if row.builtin:
        raise ValueError("Las estructuras incluidas no se pueden borrar")
    session.delete(row)
    session.commit()
    return True


# ------------------------------------------------------------------- sessions


def create_session(session: Session, filters: dict) -> TrainerSession:
    status = source_status(session)
    requested = [s for s in filters.get("sources", []) if s in SOURCES]
    usable = [s for s in requested if status[s]["available"]]
    if not usable:
        reasons = [status[s]["reason"] for s in requested if status[s]["reason"]]
        raise ValueError(" ".join(dict.fromkeys(reasons)) or "Elegí al menos una fuente")
    if filters.get("mode", "normal") not in MODES:
        raise ValueError("Modo de entrenamiento desconocido")
    if filters.get("payout_id") and session.get(PayoutStructure, filters["payout_id"]) is None:
        raise ValueError("La estructura de premios elegida no existe")
    if filters.get("mode") == "frequent" and not filters.get("card_ids"):
        raise ValueError("Elegí las tarjetas a entrenar")
    ts = TrainerSession(filters={**filters, "sources": usable}, relearn=[], spots_served=0)
    session.add(ts)
    session.commit()
    return ts


def _session(session: Session, session_id: int) -> TrainerSession:
    ts = session.get(TrainerSession, session_id)
    if ts is None:
        raise SessionNotFound("La sesión no existe")
    return ts


def next_spot(
    session: Session, session_id: int, rng: random.Random, now: datetime | None = None
) -> tuple[TrainerAttempt, ServedSpot]:
    ts = _session(session, session_id)
    now = now or _now()
    last = session.scalar(
        select(TrainerAttempt.card_id)
        .where(TrainerAttempt.session_id == ts.id)
        .order_by(TrainerAttempt.id.desc())
        .limit(1)
    )
    try:
        served = choose_spot(session, rng, ts, now, last)
    except NoSpots:
        session.commit()  # keep cards archived while looking
        raise
    key = served.reference["card_key"]
    card = served.card or session.scalar(select(TrainerCard).where(TrainerCard.key == key))
    attempt = TrainerAttempt(
        spot_id=str(uuid.uuid4()),
        session_id=ts.id,
        card_id=card.id if card else None,
        source=served.source,
        scenario=served.scenario.model_dump(mode="json") if served.scenario else {},
        offered=served.offered,
        reference={**served.reference, "card_payload": served.card_payload},
    )
    ts.spots_served += 1
    session.add(attempt)
    session.commit()
    return attempt, served


# --------------------------------------------------------------------- answer


def _scale(scenario: Scenario) -> float:
    return sum(scenario.payouts) / 100 if scenario.payouts else 1.0


def _layers(session: Session, scenario: Scenario, chart_id: int | None) -> list[dict]:
    if chart_id is not None:
        chart = session.get(PreflopChart, chart_id)
        if chart is None:
            return []
        return [
            {"action": a, "grid": [float(v) for v in g]}
            for a, g in chart.actions.items()
            if any(v > 0 for v in g)
        ]
    order = preflop_order(scenario.num_players)
    stacks = [scenario.stacks_bb.get(p, scenario.effective_stack_bb) for p in order]
    result = solve_spot(stacks, scenario.ante_bb, scenario.bb_ante_bb, scenario.payouts)
    hero = scenario.hero_position
    if scenario.situation == Situation.RFI:
        return [{"action": "allin", "grid": [float(v) for v in result.push[hero]]}]
    pusher = scenario.villains[0].position
    return [{"action": "call", "grid": [float(v) for v in result.call[(pusher, hero)]]}]


def _update_card(
    session: Session, attempt: TrainerAttempt, verdict: str, now: datetime
) -> TrainerCard:
    ref = attempt.reference
    key = ref["card_key"]
    card = session.scalar(select(TrainerCard).where(TrainerCard.key == key))
    if card is None:
        card = TrainerCard(
            key=key,
            source=attempt.source,
            scenario=ref["card_payload"],
            ease=INITIAL_EASE,
            interval_days=0,
            due_at=None,
            reps=0,
            lapses=0,
        )
        session.add(card)
    else:
        card.scenario = ref["card_payload"]
    state = CardState(card.ease, card.interval_days, aware(card.due_at), card.reps, card.lapses)
    new = schedule(state, verdict, now)  # type: ignore[arg-type]
    card.ease, card.interval_days, card.due_at = new.ease, new.interval_days, new.due_at
    card.reps, card.lapses = new.reps, new.lapses
    session.flush()
    return card


def answer_spot(
    session: Session,
    spot_id: str,
    answer: dict,
    rng: random.Random,
    now: datetime | None = None,
) -> dict:
    attempt = session.scalar(select(TrainerAttempt).where(TrainerAttempt.spot_id == spot_id))
    if attempt is None:
        raise SpotNotFound("El spot no existe")
    if attempt.answered_at is not None:
        return attempt.reference["feedback"]  # idempotent: same feedback, no rescheduling
    now = now or _now()
    ref = dict(attempt.reference)
    feedback = _score(session, attempt, ref, answer)
    ts = _session(session, attempt.session_id)
    card = _update_card(session, attempt, feedback["verdict"], now)

    queue = [e for e in ts.relearn if e["card_id"] != card.id]
    if feedback["verdict"] == "error":
        queue.append({"card_id": card.id, "due_after": ts.spots_served + relearn_offset(rng)})
    ts.relearn = queue

    feedback["card"] = {
        "interval_days": card.interval_days,
        "due_at": aware(card.due_at).isoformat() if card.due_at else None,
        "ease": card.ease,
    }
    ref["feedback"] = feedback
    attempt.reference = ref
    attempt.card_id = card.id
    attempt.answer = answer
    attempt.loss = feedback["loss"]
    attempt.loss_unit = feedback["loss_unit"]
    attempt.verdict = feedback["verdict"]
    attempt.approximate = feedback["approximate"]
    attempt.answered_at = now
    session.commit()
    return feedback


def _score(session: Session, attempt: TrainerAttempt, ref: dict, answer: dict) -> dict:
    base = {"recommendation": None, "reference_layers": [], "hand_index": None, "range": None}
    if ref["kind"] == "range":
        painted = answer.get("painted")
        if painted is None:
            raise ValueError("Pintá el rango antes de responder")
        score = score_range(ref["target"], painted)
        return {
            **base,
            "verdict": score.verdict,
            "loss": score.error,
            "loss_unit": "freq",
            "approximate": True,
            "chosen": None,
            "best": ref["action"],
            "range": {
                "target": ref["target"],
                "diff_grid": score.diff_grid,
                "top_classes": score.top_classes,
                "precision": score.precision,
            },
        }
    chosen = answer.get("action")
    if chosen is None:
        raise ValueError("Elegí una acción antes de responder")
    if chosen not in attempt.offered:
        raise ValueError("Acción no disponible en este spot")
    scenario = Scenario(**attempt.scenario)
    rec = RecommendationOut(**ref["recommendation"])
    score = score_hand(rec, chosen, _scale(scenario))
    return {
        **base,
        "verdict": score.verdict,
        "loss": score.loss,
        "loss_unit": score.loss_unit,
        "approximate": score.approximate,
        "chosen": chosen,
        "best": score.best,
        "recommendation": rec.model_dump(mode="json"),
        "reference_layers": _layers(session, scenario, ref.get("chart_id")),
        "hand_index": class_index()[hand_class(scenario.hero_hand)],
    }


# ------------------------------------------------------------------ summaries


def session_summary(session: Session, session_id: int) -> dict:
    _session(session, session_id)
    rows = list(
        session.scalars(
            select(TrainerAttempt).where(
                TrainerAttempt.session_id == session_id, TrainerAttempt.answered_at.is_not(None)
            )
        )
    )

    def count(verdict: str) -> int:
        return sum(r.verdict == verdict for r in rows)

    freq = [r.loss for r in rows if r.source == "chart" and r.loss is not None]
    prec = [1 - r.loss for r in rows if r.source == "range" and r.loss is not None]
    return {
        "spots": len(rows),
        "correct": count("correct"),
        "acceptable": count("acceptable"),
        "error": count("error"),
        "ev_loss_bb": sum(
            r.loss for r in rows if r.source == "pushfold" and r.loss_unit == "bb" and r.loss
        ),
        "avg_freq_error": float(np.mean(freq)) if freq else None,
        "avg_precision": float(np.mean(prec)) if prec else None,
    }


def frequent_errors(session: Session, limit: int = 10) -> list[dict]:
    cards = session.scalars(
        select(TrainerCard)
        .where(TrainerCard.archived.is_(False), TrainerCard.lapses > 0)
        .order_by(TrainerCard.lapses.desc(), TrainerCard.id)
        .limit(limit)
    )
    return [
        {
            "card_id": c.id,
            "key": c.key,
            "source": c.source,
            "label": c.scenario.get("title") or c.key,
            "lapses": c.lapses,
            "reps": c.reps,
        }
        for c in cards
    ]
