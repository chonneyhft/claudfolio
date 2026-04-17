"""Analyst price-target changes and rating revisions."""

from __future__ import annotations

from datetime import date


def fetch_analyst_revisions(ticker: str, on_date: date) -> list[dict]:
    """Return recent analyst rating / target revisions for `ticker`."""
    raise NotImplementedError
