"""OHLCV ingestion via yfinance."""

from __future__ import annotations

from datetime import date, timedelta

import yfinance as yf

DEFAULT_LOOKBACK_DAYS = 300


def fetch_ohlcv(ticker: str, as_of: date, days: int = DEFAULT_LOOKBACK_DAYS) -> list[dict]:
    """Return daily OHLCV bars through ``as_of`` inclusive.

    After the market close, the ``as_of`` bar is the final close for that
    session. During market hours, yfinance returns a partial bar whose
    ``Close`` reflects the latest available print, so signals built mid-session
    use live data rather than the prior close.

    Pulls ``days`` calendar days back so a 200-session SMA has enough history
    after weekends and holidays are removed. yfinance's ``end`` is exclusive,
    so we pass ``as_of + 1 day`` to include the ``as_of`` bar itself.
    """
    start = as_of - timedelta(days=days)
    end = as_of + timedelta(days=1)
    df = yf.download(
        ticker,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        progress=False,
    )
    if df is None or df.empty:
        return []

    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df = df.droplevel(1, axis=1)

    rows: list[dict] = []
    for idx, row in df.iterrows():
        rows.append(
            {
                "date": idx.date() if hasattr(idx, "date") else idx,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            }
        )
    return rows
