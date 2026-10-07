"""Scoring of a trainer answer against the engine's recommendation."""

from __future__ import annotations

from dataclasses import dataclass

from app.recommend.engine import INDIFFERENT_EV
from app.recommend.schemas import RecommendationOut
from app.trainer.srs import Verdict

CHART_CORRECT_AT = 0.5
CHART_ACCEPTABLE_AT = 0.1


@dataclass(frozen=True)
class Score:
    loss: float
    loss_unit: str
    verdict: Verdict
    approximate: bool
    best: str
    freq_chosen: float


def score_hand(rec: RecommendationOut, chosen: str, payouts_scale: float) -> Score:
    if not rec.available or not rec.actions:
        raise ValueError("No hay recomendación para puntuar")
    freqs = {a.action: a.frequency for a in rec.actions}
    if rec.source == "nash":
        evs = {a.action: a.ev for a in rec.actions if a.ev is not None}
        if chosen not in evs:
            raise ValueError(f"La acción {chosen} no está entre las ofrecidas")
        best = max(evs, key=lambda k: evs[k])
        loss = max(0.0, evs[best] - evs[chosen])
        verdict: Verdict = "correct" if loss <= INDIFFERENT_EV * payouts_scale else "error"
        return Score(
            loss=loss,
            loss_unit=rec.ev_unit or "bb",
            verdict=verdict,
            approximate=rec.confidence == "approximate",
            best=best,
            freq_chosen=freqs.get(chosen, 0.0),
        )

    freq = freqs.get(chosen, 0.0)
    best = max(freqs, key=lambda k: freqs[k])
    if freq >= CHART_CORRECT_AT or (freq > 0 and chosen == best):
        verdict = "correct"
    elif freq >= CHART_ACCEPTABLE_AT:
        verdict = "acceptable"
    else:
        verdict = "error"
    return Score(
        loss=1.0 - freq,
        loss_unit="freq",
        verdict=verdict,
        approximate=True,
        best=best,
        freq_chosen=freq,
    )
