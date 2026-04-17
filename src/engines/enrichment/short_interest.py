"""FINRA bimonthly short interest data."""

from __future__ import annotations

from datetime import date


def fetch_short_interest(ticker: str, on_date: date) -> dict:
    """Return latest short interest figures for `ticker` as of `on_date`."""
    raise NotImplementedError
