"""OHLCV ingestion via yfinance."""

from __future__ import annotations

from datetime import date, timedelta

import yfinance as yf

DEFAULT_LOOKBACK_DAYS = 300


def fetch_ohlcv(ticker: str, as_of: date, days: int = DEFAULT_LOOKBACK_DAYS) -> list[dict]:
    """Return daily OHLCV bars strictly before ``as_of``.

    ``as_of`` means "the morning of ``as_of``, before any trading on that
    date." The latest bar returned will be the most recent trading day
    strictly before ``as_of`` — the ``as_of`` bar itself is never included.

    Pulls ``days`` calendar days back so a 200-session SMA has enough history
    after weekends and holidays are removed. yfinance's ``end`` is exclusive,
    so passing ``as_of`` directly naturally excludes the ``as_of`` bar.
    """
    start = as_of - timedelta(days=days)
    df = yf.download(
        ticker,
        start=start.isoformat(),
        end=as_of.isoformat(),
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
