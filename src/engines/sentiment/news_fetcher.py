"""News ingestion. Phase 1: Finnhub. finlight wires in once a key is set."""

from __future__ import annotations

import os
from datetime import date, timedelta

import httpx

FINNHUB_BASE = "https://finnhub.io/api/v1"
FINNHUB_TIMEOUT = 20.0
DEFAULT_LOOKBACK_DAYS = 3


def fetch_news(
    ticker: str,
    on_date: date,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[dict]:
    """Return raw Finnhub company-news dicts for ``ticker`` ending at ``on_date``.

    The default 3-day lookback captures Friday/weekend news for a Monday
    pre-market briefing. Each returned dict is Finnhub's raw shape
    (``headline``, ``summary``, ``url``, ``source``, ``datetime``, ...).
    """
    key = os.environ.get("FINNHUB_KEY")
    if not key:
        raise RuntimeError("FINNHUB_KEY not set in environment")

    start = on_date - timedelta(days=max(lookback_days - 1, 0))
    params = {
        "symbol": ticker,
        "from": start.isoformat(),
        "to": on_date.isoformat(),
        "token": key,
    }
    response = httpx.get(
        f"{FINNHUB_BASE}/company-news", params=params, timeout=FINNHUB_TIMEOUT
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []
