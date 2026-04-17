"""News ingestion (NewsAPI, Finnhub). Returns raw articles per ticker per day."""

from __future__ import annotations

from datetime import date


def fetch_news(ticker: str, on_date: date) -> list[dict]:
    """Return a list of raw news article dicts for `ticker` on `on_date`."""
    raise NotImplementedError
