"""SolverSpot -> TexasSolver console command file."""

from __future__ import annotations

from app.solver.spot import (
    ACCURACY,
    ALLIN_THRESHOLD,
    CHIP_SCALE,
    MAX_ITERATION,
    RAISE_LIMIT,
    Side,
    SolverSpot,
)
from app.solver.trees import STREETS

RESULT_FILE = "result.json"
PRINT_INTERVAL = 10


def chips(bb: float) -> int:
    return round(bb * CHIP_SCALE)


def _fmt(sizes: tuple[float, ...]) -> str:
    return ",".join(f"{s:g}" for s in sizes)


def _bets(spot: SolverSpot, side: Side, street: str) -> tuple[float, ...]:
    sizes = spot.preset.streets[street].bet
    if street == spot.street and side == spot.bettor and spot.facing_bet_pct:
        sizes = tuple(sorted({*sizes, spot.facing_bet_pct}))
    return sizes


def generate_config(spot: SolverSpot, threads: int) -> str:
    streets = STREETS[STREETS.index(spot.street) :]
    lines = [
        f"set_pot {chips(spot.pot_bb)}",
        f"set_effective_stack {chips(spot.stack_bb)}",
        f"set_board {','.join(spot.board)}",
        f"set_range_oop {spot.range_oop}",
        f"set_range_ip {spot.range_ip}",
    ]
    for side in ("oop", "ip"):
        for street in streets:
            lines.append(f"set_bet_sizes {side},{street},bet,{_fmt(_bets(spot, side, street))}")
            lines.append(
                f"set_bet_sizes {side},{street},raise,{_fmt(spot.preset.streets[street].raise_)}"
            )
            lines.append(f"set_bet_sizes {side},{street},allin")
    lines += [
        f"set_allin_threshold {ALLIN_THRESHOLD:g}",
        f"set_raise_limit {RAISE_LIMIT}",
        "build_tree",
        f"set_thread_num {threads}",
        f"set_accuracy {ACCURACY:g}",
        f"set_max_iteration {MAX_ITERATION}",
        f"set_print_interval {PRINT_INTERVAL}",
        "set_use_isomorphism 1",
        "start_solve",
        "set_dump_rounds 1",
        f"dump_result {RESULT_FILE}",
    ]
    return "\n".join(lines) + "\n"
