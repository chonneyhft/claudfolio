"""Sentiment scoring. Phase 1: TextBlob. Upgrade path: FinBERT (sentiment-ml group)."""

from __future__ import annotations


def score_text(text: str) -> float:
    """Return a sentiment score in [-1.0, 1.0] for `text`."""
    raise NotImplementedError
