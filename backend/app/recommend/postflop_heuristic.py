"""Multiway postflop heuristic (provisional placeholder until the real one lands)."""

from __future__ import annotations

from app.domain.scenario import Scenario
from app.recommend.schemas import RecommendationOut


def recommend_heuristic(scenario: Scenario) -> RecommendationOut:
    return RecommendationOut(
        available=False, message="Postflop multiway: heurística en construcción."
    )
