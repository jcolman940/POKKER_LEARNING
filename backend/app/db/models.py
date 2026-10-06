"""ORM models. Domain tables (hands, ranges, solved spots...) arrive in later phases."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppMeta(Base):
    """Key/value store for app-level metadata (e.g. last seen version)."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(1024))
