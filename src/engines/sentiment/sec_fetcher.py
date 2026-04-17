"""SEC EDGAR full-text fetcher (10-K, 10-Q, 8-K)."""

from __future__ import annotations

from datetime import date


def fetch_filings(ticker: str, on_date: date) -> list[dict]:
    """Return SEC filings for `ticker` filed on or before `on_date`."""
    raise NotImplementedError
