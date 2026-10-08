"""Push/fold Nash equilibrium for a full table, with ICM (Malmuth-Harville).

Model
-----
- Everyone except the big blind either shoves or folds when the action folds to
  them; players behind a shove either call or fold.
- Only one caller is modelled: once someone calls, the players behind fold
  (no overcalls). This is the usual simplification of push/fold charts.
- Hands are the 169 classes. Card removal is applied between the hand being
  decided and each opponent's range, not between opponents.
- Payoffs are ICM equity when payouts are given, otherwise chips (chip EV).

The equilibrium is found with fictitious play: every iteration each decision
node plays a best response against the opponents' average strategies, and the
reported strategy is the average of those best responses. `exploitability` is
the largest gain (in payoff units) any single node could still get by deviating.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pokercore

from app.domain.positions import preflop_order
from app.recommend.preflop_equity import PreflopEquity, combos_per_class, preflop_equity

TOTAL_COMBOS = 1326.0


@dataclass(frozen=True)
class PushFoldSpot:
    stacks: list[float]  # starting stacks (bb) in preflop order (UTG ... SB, BB)
    sb: float = 0.5
    bb: float = 1.0
    ante: float = 0.0  # per player
    bb_ante: float = 0.0  # extra dead money posted by the big blind (BB ante formats)
    payouts: list[float] = field(default_factory=list)  # empty = chip EV

    @property
    def num_players(self) -> int:
        return len(self.stacks)


@dataclass
class PushFoldResult:
    positions: list[str]
    push: dict[str, np.ndarray]  # pusher position -> 169 push frequencies
    call: dict[tuple[str, str], np.ndarray]  # (pusher, caller) -> 169 call frequencies
    push_ev: dict[str, tuple[np.ndarray, float]]  # EV(push) per class, EV(fold)
    call_ev: dict[tuple[str, str], tuple[np.ndarray, float]]  # EV(call) per class, EV(fold)
    unit: str  # "bb" or "$"
    iterations: int
    exploitability: float
    converged: bool


class _Table:
    """Posting and terminal stack arithmetic for one spot."""

    def __init__(self, spot: PushFoldSpot):
        n = spot.num_players
        if not 2 <= n <= 10:
            raise ValueError("Push/fold admite entre 2 y 10 jugadores")
        if any(s <= 0 for s in spot.stacks):
            raise ValueError("Todos los stacks deben ser positivos")
        self.n = n
        self.stacks = np.asarray(spot.stacks, dtype=float)
        sb_seat = 0 if n == 2 else n - 2  # heads-up: the button posts the small blind
        bb_seat = n - 1
        dead = np.full(n, spot.ante)
        dead[bb_seat] += spot.bb_ante
        live = np.zeros(n)
        live[sb_seat] = spot.sb
        live[bb_seat] = spot.bb
        # Short stacks post what they can: dead money first, then the blind.
        self.dead = np.minimum(dead, self.stacks)
        self.live = np.minimum(live, self.stacks - self.dead)
        self.payouts = list(spot.payouts)

    def utility(self, final: np.ndarray) -> np.ndarray:
        if self.payouts:
            return np.asarray(pokercore.icm_equity(final.tolist(), self.payouts))
        return final

    def steal(self, i: int) -> np.ndarray:
        """Player i wins the blinds and antes uncontested."""
        final = self.stacks - self.dead - self.live
        final[i] += self.dead.sum() + self.live.sum()
        return self.utility(final)

    def showdown(self, i: int, j: int, winner: int) -> np.ndarray:
        """i shoves, j calls, everybody else folds; `winner` takes the pot."""
        matched = min(self.stacks[i] - self.dead[i], self.stacks[j] - self.dead[j])
        folded_live = self.live.sum() - self.live[i] - self.live[j]
        pot = self.dead.sum() + folded_live + 2 * matched
        final = self.stacks - self.dead - self.live
        final[i] = self.stacks[i] - self.dead[i] - matched
        final[j] = self.stacks[j] - self.dead[j] - matched
        final[winner] += pot
        return self.utility(final)


def _best_response(ev_act: np.ndarray, ev_fold: float) -> np.ndarray:
    return (ev_act > ev_fold).astype(float)


def solve_push_fold(
    spot: PushFoldSpot,
    max_iterations: int = 3000,
    tolerance: float | None = None,
    pe: PreflopEquity | None = None,
) -> PushFoldResult:
    pe = pe or preflop_equity()
    table = _Table(spot)
    n = table.n
    combos = combos_per_class()
    hand_weight = combos / TOTAL_COMBOS  # prior probability of each class

    # Terminal payoffs never change: compute them once.
    steal = [table.steal(i) for i in range(n)]
    sd_win = {(i, j): table.showdown(i, j, i) for i in range(n) for j in range(i + 1, n)}
    sd_lose = {(i, j): table.showdown(i, j, j) for i in range(n) for j in range(i + 1, n)}
    unit = "$" if spot.payouts else "bb"
    if tolerance is None:
        # Chip EV: 0.01 bb per hand; ICM: 0.01% of the prize pool.
        tolerance = 1e-4 * sum(spot.payouts) if spot.payouts else 0.01

    pushers = list(range(n - 1))
    nodes = [(i, j) for i in pushers for j in range(i + 1, n)]
    col = {k: c for c, k in enumerate(nodes)}
    push_m = np.full((169, len(pushers)), 0.5)  # column i: pusher i
    call_m = np.full((169, len(nodes)), 0.5)  # column col[(i, j)]
    row_sums = pe.compat.sum(axis=1)

    def evaluate():
        """EVs of every node against the current average strategies."""
        # Batched range products for every strategy at once.
        call_compat = pe.compat @ call_m
        call_weighted = pe.weighted @ call_m
        push_compat = pe.compat @ push_m
        push_weighted = pe.weighted @ push_m
        with np.errstate(invalid="ignore", divide="ignore"):
            call_eq = np.nan_to_num(call_weighted / call_compat)  # class vs caller range
            push_eq = np.nan_to_num(push_weighted / push_compat)  # class vs pusher range
        call_prob = call_compat / row_sums[:, None]  # P(caller has a calling hand | class)
        # Range vs range: P(caller calls | pusher range) and pusher's equity when called.
        pr_compat = push_m.T @ call_compat  # (pushers, nodes)
        pr_weighted = push_m.T @ call_weighted
        pr_total = push_m.T @ row_sums  # (pushers,)

        # V[k]: payoff vector when the action is on pusher k and everyone before folded.
        v = [None] * n
        v[n - 1] = steal[n - 1]  # folded to the big blind
        push_ev, push_fold = {}, {}
        call_ev, call_fold = {}, {}
        for i in reversed(pushers):
            callers = list(range(i + 1, n))
            # Caller nodes: W = payoff vector when i shoved and callers before k folded.
            w = steal[i]
            eq_vs_push = push_eq[:, i]
            for j in reversed(callers):
                c = col[(i, j)]
                call_ev[(i, j)] = (
                    eq_vs_push * sd_lose[(i, j)][j] + (1 - eq_vs_push) * sd_win[(i, j)][j]
                )
                call_fold[(i, j)] = float(w[j])
                r = pr_compat[i, c] / pr_total[i] if pr_total[i] > 0 else 0.0
                theta = pr_weighted[i, c] / pr_compat[i, c] if pr_compat[i, c] > 0 else 0.5
                w = r * (theta * sd_win[(i, j)] + (1 - theta) * sd_lose[(i, j)]) + (1 - r) * w
            # Pusher node: EV of shoving each class, callers acting in order.
            ev = np.zeros(169)
            reach = np.ones(169)  # P(no one called yet | hero class)
            for j in callers:
                c = col[(i, j)]
                q = call_prob[:, c]
                eq = call_eq[:, c]
                ev += reach * q * (eq * sd_win[(i, j)][i] + (1 - eq) * sd_lose[(i, j)][i])
                reach = reach * (1 - q)
            ev += reach * steal[i][i]
            push_ev[i] = ev
            push_fold[i] = float(v[i + 1][i])
            # Value when i acts with a random hand.
            pi = float(hand_weight @ push_m[:, i])
            v[i] = pi * w + (1 - pi) * v[i + 1] if pi > 0 else v[i + 1]
        return push_ev, push_fold, call_ev, call_fold

    def gap(ev: np.ndarray, fold: float, strategy: np.ndarray) -> float:
        best = np.maximum(ev, fold)
        current = strategy * ev + (1 - strategy) * fold
        return float(hand_weight @ (best - current))

    iterations = 0
    exploitability = float("inf")
    for t in range(1, max_iterations + 1):
        push_ev, push_fold, call_ev, call_fold = evaluate()
        exploitability = max(
            [gap(push_ev[i], push_fold[i], push_m[:, i]) for i in pushers]
            + [gap(call_ev[k], call_fold[k], call_m[:, col[k]]) for k in nodes]
        )
        iterations = t
        if exploitability <= tolerance:
            break
        step = 1.0 / t  # the first best response replaces the uniform start
        for i in pushers:
            push_m[:, i] += step * (_best_response(push_ev[i], push_fold[i]) - push_m[:, i])
        for k in nodes:
            c = col[k]
            call_m[:, c] += step * (_best_response(call_ev[k], call_fold[k]) - call_m[:, c])

    push_ev, push_fold, call_ev, call_fold = evaluate()
    names = preflop_order(n)
    return PushFoldResult(
        positions=names,
        push={names[i]: push_m[:, i].copy() for i in pushers},
        call={(names[i], names[j]): call_m[:, col[(i, j)]].copy() for (i, j) in nodes},
        push_ev={names[i]: (push_ev[i], push_fold[i]) for i in pushers},
        call_ev={(names[i], names[j]): (call_ev[(i, j)], call_fold[(i, j)]) for (i, j) in nodes},
        unit=unit,
        iterations=iterations,
        exploitability=exploitability,
        converged=exploitability <= tolerance,
    )
