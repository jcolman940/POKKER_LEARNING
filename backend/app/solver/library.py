"""Library of common spots, solved from the user's own preflop charts.

Pot at the flop = both players' preflop investment + dead blinds + antes.
Stack at the flop = starting stack - investment. Lines without charts are reported
("falta tabla …") and never enqueued: no ranges are made up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import SolverJob, SolverResult
from app.domain.positions import postflop_order
from app.domain.scenario import GameFormat
from app.recommend.ranges_prefill import PotType, PrefillQuery, prefill_ranges
from app.solver.flops import representative_flops
from app.solver.queue import ACTIVE, Origin, enqueue
from app.solver.spot import SolverSpot, to_solver_range
from app.solver.trees import get_preset

BLINDS = {"SB": 0.5, "BB": 1.0}


class LineSpec(BaseModel):
    id: str
    label: str
    aggressor: str
    caller: str
    pot_type: PotType
    stack_bb: float = Field(gt=0)
    open_size_bb: float = Field(gt=0)
    threebet_size_bb: float | None = Field(default=None, gt=0)


class Family(BaseModel):
    id: str
    label: str
    game_format: GameFormat
    players: int
    ante_total_bb: float = 0.0
    preset: str = "chico"
    lines: list[LineSpec]


def load_library(path: Path | None = None) -> list[Family]:
    data = json.loads((path or get_settings().solver_library_file).read_text(encoding="utf-8"))
    return [Family(**f) for f in data["families"]]


def library_key(family_id: str, line_id: str, flop: str) -> str:
    return f"{family_id}/{line_id}/{flop}"


@dataclass
class LineSpots:
    spots: dict[str, SolverSpot]
    missing: list[str]
    approximate: bool


def _pot_and_stack(family: Family, line: LineSpec) -> tuple[float, float]:
    invested = line.open_size_bb if line.pot_type == PotType.SRP else line.threebet_size_bb
    if invested is None:
        raise ValueError(f"La línea {line.id} necesita threebet_size_bb")
    dead_blinds = sum(v for p, v in BLINDS.items() if p not in (line.aggressor, line.caller))
    return round(2 * invested + dead_blinds + family.ante_total_bb, 2), line.stack_bb - invested


def build_line_spots(
    session: Session, family: Family, line: LineSpec, flops: list[str]
) -> LineSpots:
    ante = family.ante_total_bb / family.players
    result = prefill_ranges(
        session,
        PrefillQuery(
            game_format=family.game_format,
            players=family.players,
            aggressor=line.aggressor,
            caller=line.caller,
            pot_type=line.pot_type,
            stack_bb=line.stack_bb,
            ante_bb=ante,
        ),
    )
    where = f"({family.game_format}, {line.stack_bb:g}bb)"
    missing = [
        f"falta tabla: {r.missing} {where}" for r in (result.aggressor, result.caller) if r.missing
    ]
    if missing:
        return LineSpots({}, missing, False)
    aggr = to_solver_range(result.aggressor.text)
    call = to_solver_range(result.caller.text)
    order = postflop_order(family.players)
    aggressor_is_oop = order.index(line.aggressor) < order.index(line.caller)
    pot, stack = _pot_and_stack(family, line)
    preset = get_preset(family.preset)
    spots = {
        flop: SolverSpot(
            board=(flop[0:2], flop[2:4], flop[4:6]),
            pot_bb=pot,
            stack_bb=stack,
            range_oop=aggr.text if aggressor_is_oop else call.text,
            range_ip=call.text if aggressor_is_oop else aggr.text,
            preset=preset,
        )
        for flop in flops
    }
    approximate = (
        result.aggressor.approximate
        or result.caller.approximate
        or aggr.approximated
        or call.approximated
    )
    return LineSpots(spots, [], approximate)


def enqueue_line(
    session: Session,
    family: Family,
    line: LineSpec,
    flops: list[str] | None = None,
    origin: Origin = Origin.LIBRARY,
) -> int:
    built = build_line_spots(session, family, line, flops or representative_flops())
    count = 0
    for flop, spot in built.spots.items():
        h = spot.spot_hash()
        if session.get(SolverResult, h) is not None:
            continue  # already solved: no DONE row that would flood the job list
        already_active = (
            session.scalars(
                select(SolverJob.id).where(SolverJob.spot_hash == h, SolverJob.status.in_(ACTIVE))
            ).first()
            is not None
        )
        enqueue(session, spot, origin, library_key(family.id, line.id, flop))
        count += not already_active
    return count


def library_status(session: Session, families: list[Family]) -> list[dict]:
    flops = representative_flops()
    out = []
    for family in families:
        lines = []
        for line in family.lines:
            built = build_line_spots(session, family, line, flops)
            entries = []
            for flop in flops:
                key = library_key(family.id, line.id, flop)
                spot = built.spots.get(flop)
                entries.append(_entry_status(session, key, flop, spot))
            lines.append(
                {
                    "id": line.id,
                    "label": line.label,
                    "missing": built.missing,
                    "approximate": built.approximate,
                    "entries": entries,
                }
            )
        out.append(
            {"id": family.id, "label": family.label, "preset": family.preset, "lines": lines}
        )
    return out


def _entry_status(session: Session, key: str, flop: str, spot: SolverSpot | None) -> dict:
    if spot is None:
        return {"flop": flop, "status": "missing_chart", "spot_hash": None, "job_id": None}
    h = spot.spot_hash()
    if session.get(SolverResult, h) is not None:
        return {"flop": flop, "status": "solved", "spot_hash": h, "job_id": None}
    job = session.scalars(
        select(SolverJob).where(SolverJob.spot_hash == h, SolverJob.status.in_(ACTIVE))
    ).first()
    if job is not None:
        return {"flop": flop, "status": job.status, "spot_hash": h, "job_id": job.id}
    old = session.scalars(select(SolverResult.hash).where(SolverResult.library_key == key)).first()
    status = "outdated" if old is not None else "pending"
    return {"flop": flop, "status": status, "spot_hash": old, "job_id": None}
