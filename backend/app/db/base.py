from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# Import models so Alembic autogenerate can see them.
from app.db import models  # noqa: E402,F401
