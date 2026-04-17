"""Smoke tests for the sentiment engine package."""


def test_sentiment_package_imports() -> None:
    from src.engines.sentiment import (  # noqa: F401
        aggregator,
        news_fetcher,
        scorer,
        sec_fetcher,
        social_fetcher,
    )
