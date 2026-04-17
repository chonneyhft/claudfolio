"""SQLAlchemy declarative models. Per-phase schemas are filled in as engines land."""

from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all SFE tables."""


class SentimentDaily(Base):
    """Per-ticker daily sentiment rollup. Columns filled in Phase 1."""

    __tablename__ = "sentiment_daily"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class QuantDaily(Base):
    """Per-ticker daily quantitative scorecard. Columns filled in Phase 2."""

    __tablename__ = "quant_daily"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class EnrichmentDaily(Base):
    """Per-ticker daily enrichment signals. Columns filled in Phase 3."""

    __tablename__ = "enrichment_daily"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
