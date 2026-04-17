"""Feature engineering for the GBT technical-health model."""

from __future__ import annotations


def build_features(ticker: str, ohlcv: list[dict]) -> dict:
    """Return engineered features for the ML health-score model."""
    raise NotImplementedError
