"""Hero's preflop decisions in a hand (up to two), for the leak finder and the trainer."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AppMeta, Hand, HandDecision
from app.domain.hand import AGGRESSIVE, POSTS, ActionType, HandRecord
from app.domain.preflop import preflop_situation
from app.domain.scenario import TOURNAMENT_FORMATS, Situation, Street
from app.recommend.preflop_equity import hand_class

DECISIONS_VERSION = 1
VERSION_KEY = "decisions_version"
RAISE_LABEL = {0: "raise", 1: "3bet", 2: "4bet"}


@dataclass
class Decision:
    idx: int
    game_format: str
    table_size: int
    position: str
    situation: str
    vs_position: str | None
    hand_class: str
    stack_bb: float
    action: str
    spot: dict | None


def _label(a, raises_before: int) -> str:
    if a.type == ActionType.FOLD:
        return "fold"
    if a.type == ActionType.CALL:
        return "call" if raises_before else "limp"
    if a.all_in:
        return "allin"
    return RAISE_LABEL.get(raises_before, "5bet")


def extract_decisions(record: HandRecord) -> list[Decision]:
    hero = record.hero
    if not hero or not record.hero_cards:
        return []
    try:
        positions = record.positions()
        cls = hand_class(record.hero_cards)
    except (ValueError, KeyError):
        return []
    if hero not in positions:
        return []
    bb = record.bb
    preflop = [a for a in record.actions if a.street == Street.PREFLOP and a.type not in POSTS]
    others = [p for p in positions if p != hero]
    hero_stack = record.stack_of(hero)
    eff = min(hero_stack, max((record.stack_of(p) for p in others), default=0.0))
    stack_bb = round(eff / bb, 2)
    settings = get_settings()
    out: list[Decision] = []
    folded: set[str] = set()
    first_index: int | None = None
    for i, a in enumerate(preflop):
        if a.player != hero:
            if a.type == ActionType.FOLD:
                folded.add(a.player)
            continue
        if a.type == ActionType.CHECK:
            continue
        before = preflop[:i]
        raises = [b for b in before if b.type in AGGRESSIVE]
        if first_index is not None:
            # A second decision only when hero was aggressive and got re-raised.
            first_aggressive = out[0].action not in ("fold", "call", "limp")
            reraised = any(
                b.type in AGGRESSIVE and b.player != hero for b in preflop[first_index + 1 : i]
            )
            if not (first_aggressive and reraised):
                break
        situation = preflop_situation(positions, hero, before, folded)
        vs = next((positions[b.player] for b in reversed(raises)), None)
        spot = None
        if (
            record.game_type in TOURNAMENT_FORMATS
            and stack_bb <= settings.pushfold_max_bb
            and situation in (Situation.RFI, Situation.VS_ALLIN)
        ):
            spot = {
                "stacks_bb": {
                    positions[s.name]: round(s.stack / bb, 4) for s in record.dealt_seats
                },
                "ante_bb": round(record.ante / bb, 4),
            }
        out.append(
            Decision(
                idx=len(out) + 1,
                game_format=record.game_type.value,
                table_size=record.table_size,
                position=positions[hero],
                situation=situation.value,
                vs_position=vs,
                hand_class=cls,
                stack_bb=stack_bb,
                action=_label(a, len(raises)),
                spot=spot,
            )
        )
        if first_index is None:
            first_index = i
        if len(out) == 2 or out[-1].action == "fold":
            break
    return out


def decision_rows(record: HandRecord) -> list[HandDecision]:
    return [HandDecision(**asdict(d)) for d in extract_decisions(record)]


def backfill_decisions(session: Session) -> int:
    meta = session.get(AppMeta, VERSION_KEY)
    if meta is not None and meta.value == str(DECISIONS_VERSION):
        return 0
    count = 0
    for hand in session.scalars(select(Hand)):
        hand.decisions = decision_rows(HandRecord.model_validate(hand.record))
        count += 1
    session.merge(AppMeta(key=VERSION_KEY, value=str(DECISIONS_VERSION)))
    session.commit()
    return count
