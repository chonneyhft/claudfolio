"""Earnings dates, FOMC, CPI, jobs reports — ticker-relevant upcoming events."""

from __future__ import annotations

from datetime import date


def fetch_events(ticker: str, on_date: date) -> list[dict]:
    """Return upcoming events relevant to `ticker` as of `on_date`."""
    raise NotImplementedError
