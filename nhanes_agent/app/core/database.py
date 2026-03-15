from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nhanes_agent.app.core.config import database_dsn


def build_engine(base_dir: str | None = None):
    """Create the SQLAlchemy engine used by the backend package."""
    return create_engine(database_dsn(base_dir), future=True)


def build_session_factory(base_dir: str | None = None):
    """Create a reusable SQLAlchemy session factory."""
    return sessionmaker(bind=build_engine(base_dir), autoflush=False, autocommit=False, future=True)


def get_db_session(base_dir: str | None = None) -> Generator[Session, None, None]:
    """Yield a scoped SQLAlchemy session for route handlers."""
    session_factory = build_session_factory(base_dir)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
