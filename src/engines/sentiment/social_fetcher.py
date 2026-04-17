"""Social media ingestion (Reddit via PRAW, Twitter/X) for cashtag mentions."""

from __future__ import annotations

from datetime import date


def fetch_social(ticker: str, on_date: date) -> list[dict]:
    """Return raw social posts mentioning `ticker` on `on_date`."""
    raise NotImplementedError
