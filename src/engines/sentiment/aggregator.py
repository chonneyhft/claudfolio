"""Weighted daily sentiment aggregation across sources."""

from __future__ import annotations

from datetime import date


def aggregate(ticker: str, on_date: date) -> dict:
    """Roll up per-source scores into the daily sentiment schema from the planning doc."""
    raise NotImplementedError
