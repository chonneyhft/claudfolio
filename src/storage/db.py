"""SQLAlchemy engine and session management. SQLite by default, Postgres-ready."""

from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB_URL = "sqlite:///./data/sfe.db"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, built from SFE_DB_URL."""
    url = os.environ.get("SFE_DB_URL", DEFAULT_DB_URL)
    return create_engine(url, future=True)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def get_session() -> Session:
    """Return a new SQLAlchemy session. Caller is responsible for closing."""
    return _session_factory()()
