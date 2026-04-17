"""Congressional trading disclosures via Quiver Quant (45-day reporting lag)."""

from __future__ import annotations

from datetime import date


def fetch_congressional_trades(ticker: str, on_date: date) -> list[dict]:
    """Return disclosed congressional trades involving `ticker`."""
    raise NotImplementedError
