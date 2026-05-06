"""Shared pytest fixtures for the SFE test suite."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.storage.models import Base


@pytest.fixture()
def session() -> Session:
    """In-memory SQLite session shared by a single test (StaticPool keeps the
    same connection across sessionmakers so threaded code in FastAPI sees it)."""
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()
