"""Reference strategies for Hero's decisions: user charts and push/fold Nash."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import HandDecision
from app.domain.positions import preflop_order
from app.domain.scenario import GameFormat, Situation
from app.recommend.charts import ChartMatch, ChartQuery, find_chart
from app.recommend.engine import solve_spot
from app.recommend.preflop_equity import class_index


@dataclass
class Reference:
    """Expected action frequencies per hand class for one spot."""

    by_class: dict[str, dict[str, float]]
    exact: bool = True
    notes: list[str] = field(default_factory=list)
    nash: bool = False
    ev: dict[str, tuple[float, float]] = field(default_factory=dict)  # class -> (EV act, EV fold)
    act_name: str = ""  # Nash's non-fold action ("allin" for RFI, "call" vs all-in)

    def expected(self, hand_class: str) -> dict[str, float]:
        return self.by_class[hand_class]

    def map_action(self, action: str) -> str:
        """Hero's real action in the reference's vocabulary (Nash has fold / one action)."""
        if not self.nash or action in ("fold", "limp"):
            return action
        return self.act_name

    def loss(self, hand_class: str, done: str) -> float:
        """EV given up against the best Nash action (0 for charts). Limps count as folds."""
        if not self.nash:
            return 0.0
        ev_act, ev_fold = self.ev[hand_class]
        taken = ev_act if done == self.act_name else ev_fold
        return max(0.0, max(ev_act, ev_fold) - taken)


def _spot_key(d: HandDecision) -> tuple:
    spot = d.spot or {}
    stacks = tuple(sorted((spot.get("stacks_bb") or {}).items()))
    return (stacks, spot.get("ante_bb", 0.0), d.situation, d.position, d.vs_position)


class ReferenceBuilder:
    """Resolves (and caches) the reference for each decision."""

    def __init__(self, session: Session):
        self.session = session
        self._matches: dict[tuple, ChartMatch | None] = {}
        self._chart_refs: dict[int, Reference] = {}
        self._nash_refs: dict[tuple, Reference | None] = {}

    def resolve(self, d: HandDecision) -> tuple[Reference, str] | None:
        """(reference, source) or None when there is nothing to compare against."""
        if d.spot is not None:
            ref = self._nash(d)
            return (ref, "nash") if ref else None
        ref = self._chart(d)
        return (ref, "chart") if ref else None

    def _chart(self, d: HandDecision) -> Reference | None:
        q = ChartQuery(
            game_format=GameFormat(d.game_format),
            players=d.table_size,
            position=d.position,
            situation=Situation(d.situation),
            stack_bb=d.stack_bb,
            vs_position=d.vs_position,
            ante_bb=0.0,
        )
        qkey = (q.game_format, q.players, q.position, q.situation, q.stack_bb, q.vs_position)
        if qkey not in self._matches:
            self._matches[qkey] = find_chart(self.session, q)
        match = self._matches[qkey]
        if match is None:
            return None
        chart = match.chart
        ref = self._chart_refs.get(chart.id)
        if ref is None:
            by_class: dict[str, dict[str, float]] = {}
            for i, name in enumerate(class_index()):
                freqs = {a: float(g[i]) for a, g in chart.actions.items() if g[i] > 0}
                freqs["fold"] = max(0.0, 1.0 - sum(freqs.values()))
                by_class[name] = freqs
            ref = Reference(by_class=by_class, exact=match.exact, notes=list(match.mismatches))
            self._chart_refs[chart.id] = ref
        return ref

    def _nash(self, d: HandDecision) -> Reference | None:
        key = _spot_key(d)
        if key not in self._nash_refs:
            self._nash_refs[key] = self._solve(d)
        return self._nash_refs[key]

    @staticmethod
    def _solve(d: HandDecision) -> Reference | None:
        spot = d.spot or {}
        stacks = spot.get("stacks_bb") or {}
        order = [p for p in preflop_order(len(stacks)) if p in stacks] if len(stacks) >= 2 else []
        if len(order) != len(stacks) or not order:
            return None
        result = solve_spot([stacks[p] for p in order], spot.get("ante_bb", 0.0), 0.0, [])
        if d.situation == Situation.RFI.value:
            if d.position not in result.push:
                return None
            freq, (ev_act, ev_fold), act = (
                result.push[d.position],
                result.push_ev[d.position],
                "allin",
            )
        else:
            pair = (d.vs_position, d.position)
            if pair not in result.call:
                return None
            freq, (ev_act, ev_fold), act = result.call[pair], result.call_ev[pair], "call"
        names = list(class_index())
        return Reference(
            by_class={
                n: {act: float(freq[i]), "fold": 1.0 - float(freq[i])} for i, n in enumerate(names)
            },
            nash=True,
            ev={n: (float(ev_act[i]), float(ev_fold)) for i, n in enumerate(names)},
            act_name=act,
        )
