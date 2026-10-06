"""ORM models."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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
