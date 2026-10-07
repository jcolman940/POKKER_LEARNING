"""ORM models."""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class AppMeta(Base):
    """Key/value store for app-level metadata (e.g. last seen version)."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(1024))


class PreflopChart(Base):
    """A preflop strategy for one spot: per-action weights over the 169 hand classes.

    Fold is implicit (1 - sum of the actions for each hand).
    """

    __tablename__ = "preflop_charts"
    __table_args__ = (Index("ix_preflop_charts_spot", "situation", "position", "game_format"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(32))  # pokalab / preflopranges / custom / computed
    game_format: Mapped[str] = mapped_column(String(16))  # cash / mtt / sng / spin
    players: Mapped[int] = mapped_column(Integer)  # table size
    position: Mapped[str] = mapped_column(String(8))
    vs_position: Mapped[str | None] = mapped_column(String(8), nullable=True)
    stack_bb: Mapped[float] = mapped_column(Float)
    situation: Mapped[str] = mapped_column(String(16))
    open_size_bb: Mapped[float | None] = mapped_column(Float, nullable=True)
    rake: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ante_bb: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str] = mapped_column(Text, default="")
    actions: Mapped[dict[str, list[float]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class ImportBatch(Base):
    """One import run (files uploaded together) and its report."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    files: Mapped[int] = mapped_column(Integer, default=0)
    hands_found: Mapped[int] = mapped_column(Integer, default=0)
    imported: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    report: Mapped[dict] = mapped_column(JSON, default=dict)


class Hand(Base):
    """A stored hand: the normalized record, its raw text and the hero facts used
    by the stats engine (one column per counter so SQL can aggregate them)."""

    __tablename__ = "hands"
    __table_args__ = (
        UniqueConstraint("site", "hand_id", name="uq_hands_site_hand_id"),
        Index("ix_hands_played_at", "played_at"),
        Index("ix_hands_filters", "game_type", "position", "table_size"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site: Mapped[str] = mapped_column(String(32))
    hand_id: Mapped[str] = mapped_column(String(64))
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    game_type: Mapped[str] = mapped_column(String(16))
    tournament_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bb: Mapped[float] = mapped_column(Float)
    import_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True
    )
    record: Mapped[dict] = mapped_column(JSON)
    raw_text: Mapped[str] = mapped_column(Text, default="")

    # Hero facts (see app.stats.facts.HeroFacts). Null-free: hands without a hero
    # are stored but excluded from stats with has_hero = 0.
    has_hero: Mapped[int] = mapped_column(Integer, default=0)
    hero: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hero_cards: Mapped[str | None] = mapped_column(String(4), nullable=True)
    hand_class: Mapped[str | None] = mapped_column(String(3), nullable=True)
    position: Mapped[str | None] = mapped_column(String(8), nullable=True)
    table_size: Mapped[int] = mapped_column(Integer, default=0)
    stack_bb: Mapped[float] = mapped_column(Float, default=0.0)
    net_chips: Mapped[float] = mapped_column(Float, default=0.0)
    net_bb: Mapped[float] = mapped_column(Float, default=0.0)
    allin_adj_bb: Mapped[float] = mapped_column(Float, default=0.0)
    allin_adjusted: Mapped[int] = mapped_column(Integer, default=0)
    showdown_bb: Mapped[float] = mapped_column(Float, default=0.0)
    non_showdown_bb: Mapped[float] = mapped_column(Float, default=0.0)
    vpip: Mapped[int] = mapped_column(Integer, default=0)
    pfr: Mapped[int] = mapped_column(Integer, default=0)
    threebet_opp: Mapped[int] = mapped_column(Integer, default=0)
    threebet: Mapped[int] = mapped_column(Integer, default=0)
    fold3b_opp: Mapped[int] = mapped_column(Integer, default=0)
    fold3b: Mapped[int] = mapped_column(Integer, default=0)
    cbet_flop_opp: Mapped[int] = mapped_column(Integer, default=0)
    cbet_flop: Mapped[int] = mapped_column(Integer, default=0)
    cbet_turn_opp: Mapped[int] = mapped_column(Integer, default=0)
    cbet_turn: Mapped[int] = mapped_column(Integer, default=0)
    fold_cbet_opp: Mapped[int] = mapped_column(Integer, default=0)
    fold_cbet: Mapped[int] = mapped_column(Integer, default=0)
    saw_flop: Mapped[int] = mapped_column(Integer, default=0)
    wtsd: Mapped[int] = mapped_column(Integer, default=0)
    wsd: Mapped[int] = mapped_column(Integer, default=0)
    agg_bets: Mapped[int] = mapped_column(Integer, default=0)
    agg_calls: Mapped[int] = mapped_column(Integer, default=0)
    agg_folds: Mapped[int] = mapped_column(Integer, default=0)

    decisions: Mapped[list["HandDecision"]] = relationship(
        "HandDecision", cascade="all, delete-orphan"
    )


class HandDecision(Base):
    """One of hero's preflop decisions in a hand (up to two per hand)."""

    __tablename__ = "hand_decisions"
    __table_args__ = (Index("ix_hand_decisions_spot", "game_format", "position", "situation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hand_id: Mapped[int] = mapped_column(ForeignKey("hands.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    game_format: Mapped[str] = mapped_column(String(16))
    table_size: Mapped[int] = mapped_column(Integer)
    position: Mapped[str] = mapped_column(String(8))
    situation: Mapped[str] = mapped_column(String(16))
    vs_position: Mapped[str | None] = mapped_column(String(8), nullable=True)
    hand_class: Mapped[str] = mapped_column(String(3))
    stack_bb: Mapped[float] = mapped_column(Float)
    action: Mapped[str] = mapped_column(String(8))
    spot: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class TournamentResult(Base):
    """Hero's result in one tournament (from summaries or the last hand played)."""

    __tablename__ = "tournament_results"
    __table_args__ = (UniqueConstraint("site", "tournament_id", name="uq_tournament_results"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site: Mapped[str] = mapped_column(String(32))
    tournament_id: Mapped[str] = mapped_column(String(64))
    game_type: Mapped[str] = mapped_column(String(16))  # mtt / sng / spin
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    buy_in: Mapped[float] = mapped_column(Float)  # prize pool part
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    prize: Mapped[float] = mapped_column(Float, default=0.0)
    finish: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entrants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)


class SolverResult(Base):
    """A solved postflop spot (current street only), keyed by the spot hash."""

    __tablename__ = "solver_results"

    hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    spot: Mapped[dict] = mapped_column(JSON)
    tree: Mapped[bytes] = mapped_column(LargeBinary)  # zlib-compressed StrategyNode JSON
    exploitability: Mapped[float | None] = mapped_column(Float, nullable=True)
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    solve_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    solver_version: Mapped[str] = mapped_column(String(32))
    preset: Mapped[str] = mapped_column(String(32))
    library_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SolverJob(Base):
    """A queued/running/finished solve. Survives restarts (running -> queued on startup)."""

    __tablename__ = "solver_jobs"
    __table_args__ = (Index("ix_solver_jobs_pick", "status", "priority", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    spot_hash: Mapped[str] = mapped_column(String(64), index=True)
    spot: Mapped[dict] = mapped_column(JSON)
    label: Mapped[str] = mapped_column(String(200))
    origin: Mapped[str] = mapped_column(String(16))  # simulator / batch / library
    priority: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))  # queued/running/done/failed/cancelled
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    exploitability: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    library_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
