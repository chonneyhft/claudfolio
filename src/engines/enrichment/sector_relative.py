"""Ticker return minus sector ETF return — isolates idiosyncratic moves."""

from __future__ import annotations

from datetime import date


def compute_sector_relative(ticker: str, on_date: date) -> dict:
    """Return relative-performance metrics vs the ticker's sector SPDR ETF."""
    raise NotImplementedError
