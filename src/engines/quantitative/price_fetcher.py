"""OHLCV ingestion via yfinance. Install the `quant` dependency group for Phase 2."""

from __future__ import annotations

from datetime import date


def fetch_ohlcv(ticker: str, end_date: date, days: int = 200) -> list[dict]:
    """Return daily OHLCV rows for `ticker` ending `end_date`, last `days` sessions."""
    raise NotImplementedError
