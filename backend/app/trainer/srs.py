"""Simplified SM-2 scheduling for trainer cards."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

INITIAL_EASE = 2.5
MIN_EASE = 1.3
REVIEW_SHARE = 0.7
Verdict = Literal["correct", "acceptable", "error"]


@dataclass(frozen=True)
class CardState:
    ease: float
    interval_days: int
    due_at: datetime | None
    reps: int
    lapses: int


def schedule(s: CardState, verdict: Verdict, now: datetime) -> CardState:
    if verdict == "error":
        ease = max(MIN_EASE, round(s.ease - 0.2, 2))
        return CardState(ease, 0, now, s.reps + 1, s.lapses + 1)
    if verdict == "acceptable":
        ease = max(MIN_EASE, round(s.ease - 0.05, 2))
        interval = s.interval_days
    else:
        ease = s.ease
        interval = (
            1
            if s.interval_days == 0
            else 3
            if s.interval_days == 1
            else round(s.interval_days * s.ease)
        )
    return CardState(ease, interval, now + timedelta(days=interval), s.reps + 1, s.lapses)


def relearn_offset(rng: random.Random) -> int:
    return rng.randint(3, 5)


def pick_kind(
    rng: random.Random, has_due: bool, has_relearn_due: bool
) -> Literal["relearn", "due", "new"]:
    if has_relearn_due:
        return "relearn"
    if has_due and rng.random() < REVIEW_SHARE:
        return "due"
    return "new"
