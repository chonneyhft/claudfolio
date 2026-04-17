"""Unusual options activity flagging (Unusual Whales or CBOE DataShop)."""

from __future__ import annotations

from datetime import date


def fetch_options_flow(ticker: str, on_date: date) -> dict:
    """Return unusual options activity summary for `ticker` on `on_date`."""
    raise NotImplementedError
