"""Solved spots in SQLite, keyed by the spot hash. Results never expire: any change in
the solver version, preset or inputs changes the hash."""

from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import SolverResult
from app.solver.output_parser import StrategyNode
from app.solver.runner import Progress
from app.solver.spot import SOLVER_VERSION, SolverSpot


@dataclass
class CachedResult:
    spot: SolverSpot
    tree: StrategyNode
    exploitability: float | None
    iterations: int
    solve_seconds: float
    created_at: datetime


def _pack(tree: StrategyNode) -> bytes:
    return zlib.compress(json.dumps(tree.to_dict(), separators=(",", ":")).encode(), 6)


def _unpack(blob: bytes) -> StrategyNode:
    return StrategyNode.from_dict(json.loads(zlib.decompress(blob)))


def get_result(session: Session, spot_hash: str) -> CachedResult | None:
    row = session.get(SolverResult, spot_hash)
    if row is None:
        return None
    return CachedResult(
        spot=SolverSpot.from_json(row.spot),
        tree=_unpack(row.tree),
        exploitability=row.exploitability,
        iterations=row.iterations,
        solve_seconds=row.solve_seconds,
        created_at=row.created_at,
    )


def store_result(
    session: Session,
    spot: SolverSpot,
    tree: StrategyNode,
    progress: Progress,
    solve_seconds: float,
    library_key: str | None = None,
) -> None:
    row = session.get(SolverResult, spot.spot_hash()) or SolverResult(hash=spot.spot_hash())
    row.spot = spot.to_json()
    row.tree = _pack(tree)
    row.exploitability = progress.exploitability
    row.iterations = progress.iteration
    row.solve_seconds = solve_seconds
    row.solver_version = SOLVER_VERSION
    row.preset = spot.preset.name
    row.library_key = library_key or row.library_key
    session.add(row)
    session.commit()


def delete_result(session: Session, spot_hash: str) -> bool:
    deleted = session.execute(delete(SolverResult).where(SolverResult.hash == spot_hash)).rowcount
    session.commit()
    return deleted > 0


def clear_cache(session: Session) -> int:
    deleted = session.execute(delete(SolverResult)).rowcount
    session.commit()
    return deleted


def cache_stats(session: Session) -> tuple[int, int]:
    entries, size = session.execute(
        select(
            func.count(SolverResult.hash),
            func.coalesce(func.sum(func.length(SolverResult.tree)), 0),
        )
    ).one()
    return int(entries), int(size)


def result_hashes_for_library(session: Session, library_key: str) -> set[str]:
    return set(
        session.scalars(select(SolverResult.hash).where(SolverResult.library_key == library_key))
    )
