"""SEC Form 4 insider trade parser."""

from __future__ import annotations

from datetime import date


def fetch_insider_trades(ticker: str, on_date: date) -> list[dict]:
    """Return insider transactions filed on or around `on_date`."""
    raise NotImplementedError
