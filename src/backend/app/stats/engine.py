"""Aggregated statistics over the hero's hands.

Every metric reports its sample size and a 95% confidence interval:
- proportions (VPIP, PFR, 3-bet...): Wilson score interval;
- AF (bets+raises / calls): Wilson interval on p = agg / (agg + calls), mapped
  through AF = p / (1 - p);
- win rates (bb/100): normal interval from the per-hand mean and variance.
A metric whose sample is below the configured minimum is flagged `insufficient`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy import Select, case, func, literal, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Hand, TournamentResult

Z = 1.96
Interval = tuple[float | None, float | None, float | None]
WINRATE_SAMPLE_FACTOR = 10  # win rates need ~10x more hands than frequencies


class GroupBy(StrEnum):
    NONE = "none"
    POSITION = "position"
    TABLE_SIZE = "table_size"
    GAME_TYPE = "game_type"
    STACK = "stack"
    MONTH = "month"
    HAND = "hand"


STACK_BUCKETS = [(0, 20, "<20bb"), (20, 40, "20-40bb"), (40, 60, "40-60bb"), (60, 100, "60-100bb")]


@dataclass
class StatsFilter:
    sites: list[str] = field(default_factory=list)
    game_types: list[str] = field(default_factory=list)
    positions: list[str] = field(default_factory=list)
    table_sizes: list[int] = field(default_factory=list)
    hand_classes: list[str] = field(default_factory=list)
    stack_min: float | None = None
    stack_max: float | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None

    def apply(self, stmt: Select) -> Select:
        stmt = stmt.where(Hand.has_hero == 1)
        if self.sites:
            stmt = stmt.where(Hand.site.in_(self.sites))
        if self.game_types:
            stmt = stmt.where(Hand.game_type.in_(self.game_types))
        if self.positions:
            stmt = stmt.where(Hand.position.in_(self.positions))
        if self.table_sizes:
            stmt = stmt.where(Hand.table_size.in_(self.table_sizes))
        if self.hand_classes:
            stmt = stmt.where(Hand.hand_class.in_(self.hand_classes))
        if self.stack_min is not None:
            stmt = stmt.where(Hand.stack_bb >= self.stack_min)
        if self.stack_max is not None:
            stmt = stmt.where(Hand.stack_bb < self.stack_max)
        if self.date_from is not None:
            stmt = stmt.where(Hand.played_at >= self.date_from)
        if self.date_to is not None:
            stmt = stmt.where(Hand.played_at < self.date_to)
        return stmt


class Metric(BaseModel):
    key: str
    label: str
    value: float | None
    n: int  # sample: hands or opportunities
    ci_low: float | None
    ci_high: float | None
    unit: str  # "%", "bb/100", "x"
    insufficient: bool


class StatsGroup(BaseModel):
    group: str
    hands: int
    metrics: list[Metric]


class TournamentStats(BaseModel):
    tournaments: int
    cost: float
    prizes: float
    profit: float
    roi: Metric
    itm: Metric
    chips_per_tournament: Metric  # chip EV: average chips won per tournament played


def wilson(successes: float, n: float) -> Interval:
    if n <= 0:
        return None, None, None
    p = successes / n
    denom = 1 + Z * Z / n
    center = (p + Z * Z / (2 * n)) / denom
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def mean_ci(
    total: float, total_sq: float, n: int
) -> tuple[float | None, float | None, float | None]:
    if n <= 0:
        return None, None, None
    mean = total / n
    if n == 1:
        return mean, None, None
    variance = max(0.0, (total_sq - n * mean * mean) / (n - 1))
    half = Z * math.sqrt(variance / n)
    return mean, mean - half, mean + half


def _rate(key: str, label: str, num: float, den: float, minimum: int) -> Metric:
    p, lo, hi = wilson(num, den)
    return Metric(
        key=key,
        label=label,
        value=None if p is None else p * 100,
        n=int(den),
        ci_low=None if lo is None else lo * 100,
        ci_high=None if hi is None else hi * 100,
        unit="%",
        insufficient=den < minimum,
    )


def _winrate(key: str, label: str, total: float, total_sq: float, n: int, minimum: int) -> Metric:
    mean, lo, hi = mean_ci(total, total_sq, n)
    scale = lambda v: None if v is None else v * 100  # noqa: E731
    return Metric(
        key=key,
        label=label,
        value=scale(mean),
        n=n,
        ci_low=scale(lo),
        ci_high=scale(hi),
        unit="bb/100",
        insufficient=n < minimum * WINRATE_SAMPLE_FACTOR,
    )


def _aggression_factor(bets: float, calls: float, minimum: int) -> Metric:
    n = bets + calls
    if calls == 0:
        return Metric(
            key="af",
            label="AF",
            value=None,
            n=int(n),
            ci_low=None,
            ci_high=None,
            unit="x",
            insufficient=True,
        )
    _, lo, hi = wilson(bets, n)
    to_af = lambda p: None if p is None else (p / (1 - p) if p < 1 else None)  # noqa: E731
    return Metric(
        key="af",
        label="AF",
        value=bets / calls,
        n=int(n),
        ci_low=to_af(lo),
        ci_high=to_af(hi),
        unit="x",
        insufficient=n < minimum,
    )


def _group_column(group_by: GroupBy):
    if group_by == GroupBy.POSITION:
        return Hand.position
    if group_by == GroupBy.TABLE_SIZE:
        return Hand.table_size
    if group_by == GroupBy.GAME_TYPE:
        return Hand.game_type
    if group_by == GroupBy.HAND:
        return Hand.hand_class
    if group_by == GroupBy.MONTH:
        return func.strftime("%Y-%m", Hand.played_at)
    if group_by == GroupBy.STACK:
        return case(
            *[(Hand.stack_bb < hi, label) for _, hi, label in STACK_BUCKETS],
            else_=literal(">=100bb"),
        )
    return literal("Total")


SUMS = {
    name: func.sum(getattr(Hand, name))
    for name in [
        "vpip",
        "pfr",
        "threebet_opp",
        "threebet",
        "fold3b_opp",
        "fold3b",
        "cbet_flop_opp",
        "cbet_flop",
        "cbet_turn_opp",
        "cbet_turn",
        "fold_cbet_opp",
        "fold_cbet",
        "saw_flop",
        "wtsd",
        "wsd",
        "agg_bets",
        "agg_calls",
        "agg_folds",
        "net_bb",
        "allin_adj_bb",
        "showdown_bb",
        "non_showdown_bb",
    ]
}
SQUARES = {
    "net_bb_sq": func.sum(Hand.net_bb * Hand.net_bb),
    "allin_adj_bb_sq": func.sum(Hand.allin_adj_bb * Hand.allin_adj_bb),
}


def compute_stats(
    session: Session, filters: StatsFilter, group_by: GroupBy = GroupBy.NONE
) -> list[StatsGroup]:
    minimum = get_settings().stats_min_sample
    group_col = _group_column(group_by).label("grp")
    stmt = select(
        group_col,
        func.count(Hand.id).label("hands"),
        *[c.label(k) for k, c in SUMS.items()],
        *[c.label(k) for k, c in SQUARES.items()],
    ).group_by(group_col)
    rows = session.execute(filters.apply(stmt)).mappings().all()

    groups = []
    for r in sorted(rows, key=lambda r: str(r["grp"])):
        n = int(r["hands"])
        g = {k: float(r[k] or 0) for k in [*SUMS, *SQUARES]}
        metrics = [
            _rate("vpip", "VPIP", g["vpip"], n, minimum),
            _rate("pfr", "PFR", g["pfr"], n, minimum),
            _rate("threebet", "3-bet", g["threebet"], g["threebet_opp"], minimum),
            _rate("fold3b", "Fold to 3-bet", g["fold3b"], g["fold3b_opp"], minimum),
            _rate("cbet_flop", "C-bet flop", g["cbet_flop"], g["cbet_flop_opp"], minimum),
            _rate("cbet_turn", "C-bet turn", g["cbet_turn"], g["cbet_turn_opp"], minimum),
            _rate("fold_cbet", "Fold to c-bet", g["fold_cbet"], g["fold_cbet_opp"], minimum),
            _rate("wtsd", "WTSD", g["wtsd"], g["saw_flop"], minimum),
            _rate("wsd", "W$SD", g["wsd"], g["wtsd"], minimum),
            _aggression_factor(g["agg_bets"], g["agg_calls"], minimum),
            _rate(
                "afq",
                "AFq",
                g["agg_bets"],
                g["agg_bets"] + g["agg_calls"] + g["agg_folds"],
                minimum,
            ),
            _winrate("winrate", "Winrate", g["net_bb"], g["net_bb_sq"], n, minimum),
            _winrate(
                "allin_adj",
                "Winrate all-in EV",
                g["allin_adj_bb"],
                g["allin_adj_bb_sq"],
                n,
                minimum,
            ),
        ]
        groups.append(StatsGroup(group=str(r["grp"]), hands=n, metrics=metrics))
    return groups


class GraphPoint(BaseModel):
    hand: int
    net: float
    showdown: float
    non_showdown: float
    allin_adj: float


def winnings_graph(
    session: Session, filters: StatsFilter, max_points: int = 1000
) -> list[GraphPoint]:
    """Cumulative bb: total (green), showdown (blue), non-showdown (red), all-in EV."""
    stmt = filters.apply(
        select(Hand.net_bb, Hand.showdown_bb, Hand.non_showdown_bb, Hand.allin_adj_bb).order_by(
            Hand.played_at, Hand.id
        )
    )
    rows = session.execute(stmt).all()
    if not rows:
        return []
    step = max(1, math.ceil(len(rows) / max_points))
    points = [GraphPoint(hand=0, net=0, showdown=0, non_showdown=0, allin_adj=0)]
    net = sd = nsd = adj = 0.0
    for i, (n, s, ns, a) in enumerate(rows, start=1):
        net += n
        sd += s
        nsd += ns
        adj += a
        if i % step == 0 or i == len(rows):
            points.append(GraphPoint(hand=i, net=net, showdown=sd, non_showdown=nsd, allin_adj=adj))
    return points


def tournament_stats(session: Session, filters: StatsFilter) -> TournamentStats | None:
    minimum = get_settings().stats_min_sample
    stmt = select(TournamentResult)
    if filters.sites:
        stmt = stmt.where(TournamentResult.site.in_(filters.sites))
    if filters.game_types:
        stmt = stmt.where(TournamentResult.game_type.in_(filters.game_types))
    if filters.date_from is not None:
        stmt = stmt.where(TournamentResult.played_at >= filters.date_from)
    if filters.date_to is not None:
        stmt = stmt.where(TournamentResult.played_at < filters.date_to)
    results = session.scalars(stmt).all()

    chips = filters.apply(
        select(Hand.tournament_id, func.sum(Hand.net_chips))
        .where(Hand.tournament_id.is_not(None))
        .group_by(Hand.tournament_id)
    )
    per_tournament = [float(v) for _, v in session.execute(chips).all()]
    if not results and not per_tournament:
        return None

    costs = [r.buy_in + r.fee for r in results]
    profits = [r.prize - c for r, c in zip(results, costs, strict=True)]
    n = len(results)
    cost = sum(costs)
    mean_cost = cost / n if n else 0.0
    mean_profit, lo, hi = mean_ci(sum(profits), sum(p * p for p in profits), n)
    roi = Metric(
        key="roi",
        label="ROI",
        value=None if mean_profit is None or mean_cost == 0 else mean_profit / mean_cost * 100,
        n=n,
        ci_low=None if lo is None or mean_cost == 0 else lo / mean_cost * 100,
        ci_high=None if hi is None or mean_cost == 0 else hi / mean_cost * 100,
        unit="%",
        insufficient=n < minimum,
    )
    itm = _rate("itm", "ITM", sum(1 for r in results if r.prize > 0), n, minimum)
    c_mean, c_lo, c_hi = mean_ci(
        sum(per_tournament), sum(v * v for v in per_tournament), len(per_tournament)
    )
    chip_ev = Metric(
        key="chip_ev",
        label="Chip EV por torneo",
        value=c_mean,
        n=len(per_tournament),
        ci_low=c_lo,
        ci_high=c_hi,
        unit="fichas",
        insufficient=len(per_tournament) < minimum,
    )
    return TournamentStats(
        tournaments=n,
        cost=cost,
        prizes=sum(r.prize for r in results),
        profit=sum(profits),
        roi=roi,
        itm=itm,
        chips_per_tournament=chip_ev,
    )
