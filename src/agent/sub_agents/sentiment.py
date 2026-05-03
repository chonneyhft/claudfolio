"""Sentiment sub-agent: domain-specific investigation of news and filing sentiment."""

from __future__ import annotations

from datetime import date as Date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agent.sub_agents.base import BaseSubAgent
from src.storage.models import SentimentDaily

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "sentiment_agent.txt"

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_cached_sentiment",
        "description": (
            "Returns the most recent pre-computed daily sentiment row for a ticker. "
            "Includes score, direction, 7-day delta, source breakdown, and notable headlines."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Ticker symbol"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "fetch_live_news",
        "description": (
            "Fetches fresh news articles from Finnhub for a ticker. "
            "Returns raw article dicts with headline, summary, url, source."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "lookback_days": {
                    "type": "integer",
                    "description": "Days of history to fetch (default 3)",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "fetch_live_finlight",
        "description": (
            "Fetches fresh news articles from finlight for a ticker. "
            "Returns article dicts with title, summary, link, source."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "lookback_days": {
                    "type": "integer",
                    "description": "Days of history to fetch (default 3)",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "fetch_sec_filings",
        "description": (
            "Fetches recent SEC EDGAR filings (10-K, 10-Q, 8-K) for a ticker. "
            "Returns filing dicts with form type, filing date, items, and document URL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "lookback_days": {
                    "type": "integer",
                    "description": "Days of filing history (default 30)",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "score_texts",
        "description": (
            "Runs FinBERT sentiment scoring on a list of text snippets. "
            "Returns a score in [-1.0, 1.0] for each text. "
            "Positive = bullish, negative = bearish, 0 = neutral."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "texts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of text snippets to score",
                },
            },
            "required": ["texts"],
        },
    },
    {
        "name": "get_sentiment_history",
        "description": (
            "Returns a time series of daily sentiment scores for a ticker. "
            "Useful for trend analysis and identifying regime changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "days": {
                    "type": "integer",
                    "description": "Number of days of history (default 14)",
                },
            },
            "required": ["ticker"],
        },
    },
]


def _build_handlers(
    session: Session, on_date: Date
) -> dict[str, Any]:
    from src.engines.sentiment import finlight_fetcher, news_fetcher, scorer, sec_fetcher
    from src.meta.payload_builder import _latest, _sentiment_view

    def handle_get_cached(inp: dict) -> dict:
        ticker = inp["ticker"].upper()
        row = _latest(session, SentimentDaily, ticker, on_date)
        view = _sentiment_view(row)
        if view is None:
            return {"error": f"No cached sentiment data for {ticker} as of {on_date}"}
        return {"ticker": ticker, **view}

    def handle_fetch_news(inp: dict) -> dict:
        ticker = inp["ticker"].upper()
        lookback = inp.get("lookback_days", 3)
        articles = news_fetcher.fetch_news(ticker, on_date, lookback_days=lookback)
        return {
            "ticker": ticker,
            "source": "finnhub",
            "count": len(articles),
            "articles": [
                {
                    "headline": a.get("headline", ""),
                    "summary": a.get("summary", ""),
                    "source": a.get("source", ""),
                    "url": a.get("url", ""),
                }
                for a in articles[:20]
            ],
        }

    def handle_fetch_finlight(inp: dict) -> dict:
        ticker = inp["ticker"].upper()
        lookback = inp.get("lookback_days", 3)
        articles = finlight_fetcher.fetch_news(ticker, on_date, lookback_days=lookback)
        return {
            "ticker": ticker,
            "source": "finlight",
            "count": len(articles),
            "articles": [
                {
                    "title": a.get("title", ""),
                    "summary": a.get("summary", ""),
                    "source": a.get("source", ""),
                    "url": a.get("link", ""),
                }
                for a in articles[:20]
            ],
        }

    def handle_fetch_sec(inp: dict) -> dict:
        ticker = inp["ticker"].upper()
        lookback = inp.get("lookback_days", 30)
        filings = sec_fetcher.fetch_filings(ticker, on_date, lookback_days=lookback)
        return {
            "ticker": ticker,
            "count": len(filings),
            "filings": filings,
        }

    def handle_score_texts(inp: dict) -> dict:
        texts = inp["texts"]
        scores = scorer.score_texts(texts)
        return {
            "results": [
                {"text": t[:200], "score": round(s, 4)}
                for t, s in zip(texts, scores)
            ]
        }

    def handle_sentiment_history(inp: dict) -> dict:
        ticker = inp["ticker"].upper()
        days = inp.get("days", 14)
        stmt = (
            select(SentimentDaily)
            .where(SentimentDaily.ticker == ticker, SentimentDaily.as_of <= on_date)
            .order_by(SentimentDaily.as_of.desc())
            .limit(days)
        )
        rows = session.execute(stmt).scalars().all()
        return {
            "ticker": ticker,
            "history": [
                {
                    "date": r.as_of.isoformat(),
                    "score": r.sentiment_score,
                    "direction": r.sentiment_direction,
                }
                for r in reversed(rows)
            ],
        }

    return {
        "get_cached_sentiment": handle_get_cached,
        "fetch_live_news": handle_fetch_news,
        "fetch_live_finlight": handle_fetch_finlight,
        "fetch_sec_filings": handle_fetch_sec,
        "score_texts": handle_score_texts,
        "get_sentiment_history": handle_sentiment_history,
    }


class SentimentSubAgent(BaseSubAgent):
    def __init__(self, session: Session, on_date: Date, **kwargs):
        handlers = _build_handlers(session, on_date)
        super().__init__(
            system_prompt_path=PROMPT_PATH,
            tool_schemas=TOOL_SCHEMAS,
            tool_handlers=handlers,
            **kwargs,
        )
