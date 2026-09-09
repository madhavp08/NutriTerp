"""Database engine and session helpers.

One SQLAlchemy engine for the whole app. Neon is a normal Postgres, so the
only special part is that the URL must use the psycopg3 driver prefix.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from .config import settings


def _to_psycopg_url(url: str) -> str:
    """SQLAlchemy needs postgresql+psycopg:// to pick the psycopg3 driver."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_to_psycopg_url(settings.database_url), pool_pre_ping=True)


class Base(DeclarativeBase):
    """Parent class for all ORM table models."""


def get_session():
    """FastAPI dependency: one DB session per request, always closed."""
    with Session(engine) as session:
        yield session
