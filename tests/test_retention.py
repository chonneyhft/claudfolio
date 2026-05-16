"""Tests for src/storage/retention.py."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.storage.models import (
    BriefingDaily,
    EnrichmentDaily,
    QuantDaily,
    SentimentDaily,
)
from src.storage.retention import RETENTION_DAYS, prune

TODAY = date(2026, 5, 16)


def _mk_sentiment(session: Session, as_of: date, ticker: str = "AAPL") -> None:
    session.add(
        SentimentDaily(
            ticker=ticker,
            as_of=as_of,
            sentiment_score=0.0,
            sentiment_direction="stable",
        )
    )


def _mk_quant(session: Session, as_of: date, ticker: str = "AAPL") -> None:
    session.add(QuantDaily(ticker=ticker, as_of=as_of, health_score="ok"))


def _mk_enrichment(session: Session, as_of: date, ticker: str = "AAPL") -> None:
    session.add(EnrichmentDaily(ticker=ticker, as_of=as_of))


def _mk_briefing(session: Session, as_of: date) -> None:
    session.add(
        BriefingDaily(
            as_of=as_of,
            tickers=["AAPL"],
            payload={},
            briefing_markdown="x",
            model="m",
        )
    )


def test_prune_deletes_engine_rows_past_window(session: Session) -> None:
    cutoff = RETENTION_DAYS[SentimentDaily]
    old = TODAY - timedelta(days=cutoff + 1)
    fresh = TODAY - timedelta(days=cutoff - 1)
    _mk_sentiment(session, old, ticker="OLD")
    _mk_sentiment(session, fresh, ticker="NEW")
    _mk_quant(session, old, ticker="OLD")
    _mk_quant(session, fresh, ticker="NEW")
    _mk_enrichment(session, old, ticker="OLD")
    _mk_enrichment(session, fresh, ticker="NEW")
    session.commit()

    counts = prune(session, today=TODAY, vacuum=False)

    assert counts["sentiment_daily"] == 1
    assert counts["quant_daily"] == 1
    assert counts["enrichment_daily"] == 1
    assert counts["briefing_daily"] == 0

    remaining = session.execute(select(SentimentDaily.ticker)).scalars().all()
    assert remaining == ["NEW"]


def test_prune_uses_longer_window_for_briefings(session: Session) -> None:
    engine_cutoff = RETENTION_DAYS[SentimentDaily]
    briefing_cutoff = RETENTION_DAYS[BriefingDaily]
    assert briefing_cutoff > engine_cutoff

    between = TODAY - timedelta(days=engine_cutoff + 1)
    very_old = TODAY - timedelta(days=briefing_cutoff + 1)
    _mk_briefing(session, between)
    _mk_briefing(session, very_old)
    session.commit()

    counts = prune(session, today=TODAY, vacuum=False)
    assert counts["briefing_daily"] == 1
    survivors = session.execute(select(BriefingDaily.as_of)).scalars().all()
    assert survivors == [between]


def test_dry_run_reports_without_deleting(session: Session) -> None:
    old = TODAY - timedelta(days=RETENTION_DAYS[SentimentDaily] + 5)
    _mk_sentiment(session, old)
    session.commit()

    counts = prune(session, today=TODAY, dry_run=True, vacuum=False)
    assert counts["sentiment_daily"] == 1

    remaining = session.execute(select(SentimentDaily)).scalars().all()
    assert len(remaining) == 1


def test_prune_leaves_recent_rows_alone(session: Session) -> None:
    for offset in (0, 1, 30, 89):
        _mk_sentiment(session, TODAY - timedelta(days=offset), ticker=f"T{offset}")
    session.commit()

    counts = prune(session, today=TODAY, vacuum=False)
    assert counts["sentiment_daily"] == 0
    assert session.execute(select(SentimentDaily)).scalars().all().__len__() == 4
