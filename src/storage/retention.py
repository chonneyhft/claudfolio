"""Retention policy for engine outputs.

Engine tables (sentiment/quant/enrichment/briefing) are regenerable from APIs
and only retained for trend-detection windows. Decision tables (signals,
trades, positions, outcomes, agent sessions) are kept forever as the
experiment's audit trail and are never touched by prune().
"""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta

from loguru import logger
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from src.storage.models import (
    BriefingDaily,
    EnrichmentDaily,
    QuantDaily,
    SentimentDaily,
)

RETENTION_DAYS: dict[type, int] = {
    SentimentDaily: 90,
    QuantDaily: 90,
    EnrichmentDaily: 90,
    BriefingDaily: 180,
}


def prune(
    session: Session,
    *,
    today: Date | None = None,
    dry_run: bool = False,
    vacuum: bool = True,
) -> dict[str, int]:
    """Delete engine rows past their retention window.

    Returns a mapping of ``tablename → rows deleted`` (or rows that would be
    deleted, when ``dry_run=True``). VACUUM runs after the deletes to reclaim
    file space on SQLite; pass ``vacuum=False`` to skip it.
    """
    today = today or Date.today()
    counts: dict[str, int] = {}

    for model, days in RETENTION_DAYS.items():
        cutoff = today - timedelta(days=days)
        if dry_run:
            n = session.execute(
                select(model).where(model.as_of < cutoff)
            ).scalars().all()
            counts[model.__tablename__] = len(n)
        else:
            result = session.execute(delete(model).where(model.as_of < cutoff))
            counts[model.__tablename__] = result.rowcount or 0

    if dry_run:
        return counts

    session.commit()

    if vacuum and any(counts.values()):
        bind = session.get_bind()
        if bind.dialect.name == "sqlite":
            try:
                with bind.connect().execution_options(
                    isolation_level="AUTOCOMMIT"
                ) as conn:
                    conn.execute(text("VACUUM"))
            except Exception as exc:
                logger.warning("VACUUM failed (non-fatal): {exc}", exc=exc)

    return counts
