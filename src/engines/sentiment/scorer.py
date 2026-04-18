"""Sentiment scoring. Phase 1: TextBlob. Upgrade path: FinBERT (sentiment-ml group)."""

from __future__ import annotations

from textblob import TextBlob


def score_text(text: str) -> float:
    """Return a sentiment score in [-1.0, 1.0] for ``text``.

    Empty or whitespace-only input returns 0.0 (neutral) so upstream fetchers
    can pass article snippets without pre-filtering.
    """
    if not text or not text.strip():
        return 0.0
    return float(TextBlob(text).sentiment.polarity)
