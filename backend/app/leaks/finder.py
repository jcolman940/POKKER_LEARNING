"""Preflop leak finder: Hero's real decisions against charts and push/fold Nash."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Hand, HandDecision
from app.domain.scenario import TOURNAMENT_FORMATS, GameFormat, Situation
from app.leaks.reference import Reference, ReferenceBuilder
from app.recommend.preflop_equity import class_index
from app.stats.engine import StatsFilter, wilson

MIN_DIFF = 0.05
INF = float("inf")
PUSHFOLD_BUCKETS = ((5, "3-5"), (8, "6-8"), (11, "9-11"), (INF, "12-15"))
DEEP_BUCKETS = ((15, "≤15"), (30, "16-30"), (60, "31-60"), (120, "61-120"), (INF, "120+"))
SITUATION_LABEL = {
    Situation.RFI: "RFI",
    Situation.VS_OPEN: "vs open",
    Situation.VS_3BET: "vs 3-bet",
    Situation.VS_4BET: "vs 4-bet",
    Situation.SQUEEZE: "squeeze",
    Situation.BVB: "blind vs blind",
    Situation.VS_ALLIN: "vs all-in",
}
MAPPED_NOTE = "Algunas acciones se asimilaron a push/fold: EV aproximado"
NO_DECISIONS = (
    "Importá historiales para ver tus leaks (los parsers de GG/PS llegan con tus archivos)."
)


def stack_bucket(stack_bb: float, pushfold: bool) -> str:
    for limit, name in PUSHFOLD_BUCKETS if pushfold else DEEP_BUCKETS:
        if stack_bb <= limit:
            return name
    raise AssertionError("unreachable")


class ActionLeak(BaseModel):
    action: str
    observed: float
    expected: float
    ci_low: float
    ci_high: float
    diff: float
    significant: bool


class LeakGroup(BaseModel):
    key: str
    label: str
    game_format: str
    table_size: int
    position: str
    situation: str
    vs_position: str | None
    stack_bucket: str
    source: str  # "chart" | "nash"
    approximate: bool
    notes: list[str]
    n: int
    insufficient: bool
    actions: list[ActionLeak]
    impact: float
    impact_unit: str  # "bb/100" | "pts/100"
    ev_loss_bb: float | None


class TopClass(BaseModel):
    hand_class: str
    n: int
    observed: float
    expected: float
    diff: float


class LeakDetail(BaseModel):
    group: LeakGroup
    action: str
    top_classes: list[TopClass]
    grid: list[float | None]


class LeakReport(BaseModel):
    total_hands: int
    min_sample: int
    leaks: list[LeakGroup]
    insufficient: list[LeakGroup]
    other: list[LeakGroup]
    warnings: list[str]


@dataclass
class _Item:
    hand_class: str
    done: str
    ref: Reference
    loss: float
    mapped: bool = False

    def expected(self, action: str) -> float:
        return self.ref.expected(self.hand_class).get(action, 0.0)


@dataclass
class _Acc:
    d: HandDecision
    bucket: str
    source: str
    items: list[_Item] = field(default_factory=list)


def _key(d: HandDecision, bucket: str, source: str) -> str:
    vs = d.vs_position or "-"
    return f"{d.game_format}|{d.table_size}|{d.position}|{d.situation}|{vs}|{bucket}|{source}"


def _label(d: HandDecision, bucket: str) -> str:
    vs = f" vs {d.vs_position}" if d.vs_position else ""
    sit = SITUATION_LABEL.get(Situation(d.situation), d.situation)
    return f"{d.game_format.upper()} {d.table_size}-max · {d.position} {sit}{vs} · {bucket} bb"


def _action_leaks(items: list[_Item], min_sample: int) -> list[ActionLeak]:
    n = len(items)
    names = {i.done for i in items} | {a for i in items for a in i.ref.expected(i.hand_class)}
    out = []
    for name in sorted(names):
        k = sum(1 for i in items if i.done == name)
        observed, lo, hi = wilson(k, n)
        expected = sum(i.expected(name) for i in items) / n
        diff = observed - expected
        significant = n >= min_sample and not (lo <= expected <= hi) and abs(diff) >= MIN_DIFF
        out.append(
            ActionLeak(
                action=name,
                observed=observed,
                expected=expected,
                ci_low=lo,
                ci_high=hi,
                diff=diff,
                significant=significant,
            )
        )
    return out


def _build_group(key: str, acc: _Acc, total_hands: int, min_sample: int) -> LeakGroup:
    d, n = acc.d, len(acc.items)
    actions = _action_leaks(acc.items, min_sample)
    notes = list(dict.fromkeys(note for i in acc.items for note in i.ref.notes))
    scale = 100 / total_hands if total_hands else 0.0
    if acc.source == "nash":
        ev_loss: float | None = sum(i.loss for i in acc.items)
        impact, unit, approximate = ev_loss * scale, "bb/100", False
    else:
        ev_loss = None
        impact = max((abs(a.diff) for a in actions), default=0.0) * n * scale
        unit, approximate = "pts/100", True
    approximate = approximate or any(not i.ref.exact for i in acc.items)
    if any(i.mapped for i in acc.items):
        approximate = True
        notes.append(MAPPED_NOTE)
    return LeakGroup(
        key=key,
        label=_label(d, acc.bucket),
        game_format=d.game_format,
        table_size=d.table_size,
        position=d.position,
        situation=d.situation,
        vs_position=d.vs_position,
        stack_bucket=acc.bucket,
        source=acc.source,
        approximate=approximate,
        notes=notes,
        n=n,
        insufficient=n < min_sample,
        actions=actions,
        impact=impact,
        impact_unit=unit,
        ev_loss_bb=ev_loss,
    )


def _analyze(session: Session, filters: StatsFilter):
    total_hands = session.scalar(filters.apply(select(func.count(Hand.id)))) or 0
    stmt = filters.apply(select(HandDecision).join(Hand, Hand.id == HandDecision.hand_id))
    decisions = session.scalars(stmt.order_by(HandDecision.id)).all()
    refs = ReferenceBuilder(session)
    accs: dict[str, _Acc] = {}
    skipped = unresolved = 0
    for d in decisions:
        resolved = refs.resolve(d)
        if resolved is None:
            if d.spot is None:
                skipped += 1
            else:
                unresolved += 1
            continue
        ref, source = resolved
        pushfold = (
            GameFormat(d.game_format) in TOURNAMENT_FORMATS
            and d.stack_bb <= get_settings().pushfold_max_bb
        )
        bucket = stack_bucket(d.stack_bb, pushfold)
        acc = accs.setdefault(_key(d, bucket, source), _Acc(d=d, bucket=bucket, source=source))
        done = ref.map_action(d.action)
        acc.items.append(
            _Item(d.hand_class, done, ref, ref.loss(d.hand_class, done), ref.is_mapped(d.action))
        )
    warnings = []
    if not decisions:
        warnings.append(NO_DECISIONS)
    if skipped:
        warnings.append(
            f"Hay {skipped} decisiones sin tabla de referencia: cargalas en Rangos preflop."
        )
    if unresolved:
        warnings.append(f"{unresolved} decisiones de push/fold no se pudieron evaluar.")
    return accs, total_hands, get_settings().leaks_min_sample, warnings


def find_leaks(session: Session, filters: StatsFilter) -> LeakReport:
    accs, total_hands, min_sample, warnings = _analyze(session, filters)
    groups = [_build_group(k, a, total_hands, min_sample) for k, a in accs.items()]
    leaks = [g for g in groups if not g.insufficient and any(a.significant for a in g.actions)]
    insufficient = [g for g in groups if g.insufficient]
    other = [g for g in groups if not g.insufficient and g not in leaks]
    return LeakReport(
        total_hands=total_hands,
        min_sample=min_sample,
        leaks=sorted(leaks, key=lambda g: -g.impact),
        insufficient=sorted(insufficient, key=lambda g: -g.n),
        other=sorted(other, key=lambda g: -g.n),
        warnings=warnings,
    )


def leak_detail(session: Session, filters: StatsFilter, key: str) -> LeakDetail | None:
    accs, total_hands, min_sample, _ = _analyze(session, filters)
    acc = accs.get(key)
    if acc is None:
        return None
    group = _build_group(key, acc, total_hands, min_sample)
    # On |diff| ties (raise/fold are mirror images) prefer the non-fold action.
    worst = max(group.actions, key=lambda a: (round(abs(a.diff), 9), a.action != "fold")).action
    per_class: dict[str, list[_Item]] = defaultdict(list)
    for item in acc.items:
        per_class[item.hand_class].append(item)
    rows = []
    for cls, items in per_class.items():
        n = len(items)
        observed = sum(1 for i in items if i.done == worst) / n
        expected = sum(i.expected(worst) for i in items) / n
        rows.append(
            TopClass(
                hand_class=cls, n=n, observed=observed, expected=expected, diff=observed - expected
            )
        )
    rows.sort(key=lambda r: -abs(r.diff) * r.n)
    grid: list[float | None] = [None] * 169
    index = class_index()
    for r in rows:
        grid[index[r.hand_class]] = r.diff
    return LeakDetail(group=group, action=worst, top_classes=rows[:10], grid=grid)
