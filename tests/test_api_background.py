"""Tests for FastAPI pipeline endpoints — background tasks, ?wait=, errors.

Complements test_api.py (which covers the GET endpoints). Uses TestClient,
which executes BackgroundTasks synchronously after the response, so we can
assert on the DB state once the request returns.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api import main as api_main
from src.storage.models import (
    Base,
    BriefingDaily,
    EnrichmentDaily,
    QuantDaily,
    SentimentDaily,
)


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    monkeypatch.setattr(api_main, "_session_factory", lambda: Factory)
    monkeypatch.setattr(
        api_main, "load_watchlist",
        lambda: [{"ticker": "NVDA", "sector": "Tech"}, {"ticker": "AAPL", "sector": "Tech"}],
    )
    return TestClient(api_main.app)


# ─────────────────────────── _resolve_tickers ─────────────────────────── #


class TestResolveTickers:
    def test_explicit_ticker_returns_single(self, monkeypatch):
        out = api_main._resolve_tickers("nvda")
        assert out == ["NVDA"]

    def test_no_ticker_uses_watchlist(self, monkeypatch):
        monkeypatch.setattr(
            api_main, "load_watchlist",
            lambda: [{"ticker": "AAA"}, {"ticker": "BBB"}],
        )
        assert api_main._resolve_tickers(None) == ["AAA", "BBB"]

    def test_no_ticker_empty_watchlist_raises_400(self, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.setattr(api_main, "load_watchlist", lambda: [])
        with pytest.raises(HTTPException) as exc:
            api_main._resolve_tickers(None)
        assert exc.value.status_code == 400


# ─────────────────────────── POST /pipeline/{engine} ─────────────────────────── #


class TestPipelineEndpoint:
    def test_unknown_engine_returns_404(self, client):
        r = client.post("/pipeline/bogus", params={"ticker": "NVDA"})
        assert r.status_code == 404

    def test_scheduled_response_when_not_waiting(self, client, monkeypatch):
        # Stub the actual job so the background task is a no-op.
        called = {}

        def stub(tickers, on_date):
            called["args"] = (tickers, on_date)

        monkeypatch.setitem(api_main._JOBS, "sentiment", stub)

        r = client.post("/pipeline/sentiment", params={"ticker": "NVDA", "date": "2026-04-17"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "scheduled"
        assert body["tickers"] == ["NVDA"]
        # TestClient runs the background task before returning — verify it ran.
        assert called["args"] == (["NVDA"], date(2026, 4, 17))

    def test_wait_runs_synchronously_and_returns_completed(self, client, monkeypatch):
        from src.engines.sentiment import aggregator as sent_agg
        from src.storage import sentiment_repo

        monkeypatch.setattr(sent_agg, "aggregate", lambda t, d: {
            "ticker": t, "date": d.isoformat(),
            "sentiment_score": 0.6, "sentiment_direction": "improving",
            "source_breakdown": {}, "key_topics": [], "notable_headlines": [],
        })
        monkeypatch.setattr(sentiment_repo, "get_score_near", lambda *a, **k: None)

        r = client.post(
            "/pipeline/sentiment",
            params={"ticker": "NVDA", "date": "2026-04-17", "wait": "true"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_quant_job_writes_via_aggregator(self, client, monkeypatch):
        from src.engines.quantitative import aggregator as q_agg

        captured: dict = {}

        def fake_aggregate(ticker, on_date, sector=None):
            captured["sector"] = sector
            return {
                "ticker": ticker, "date": on_date.isoformat(),
                "close": 100.0, "change_1d": 0.5, "change_5d": 1.0, "change_20d": 2.0,
                "rsi_14": 55.0, "above_50sma": True, "above_200sma": True,
                "macd_signal": "neutral", "volume_vs_20d_avg": 1.1,
                "sector_etf": "XLK", "relative_return_5d": 0.1,
                "health_score": "strong",
            }

        monkeypatch.setattr(q_agg, "aggregate", fake_aggregate)

        r = client.post(
            "/pipeline/quant",
            params={"ticker": "NVDA", "date": "2026-04-17", "wait": "true"},
        )
        assert r.status_code == 200
        # Sector pulled from the watchlist stub.
        assert captured["sector"] == "Tech"

    def test_enrichment_job_writes_via_aggregator(self, client, monkeypatch):
        from src.engines.enrichment import aggregator as e_agg

        monkeypatch.setattr(e_agg, "aggregate", lambda t, d: {
            "ticker": t, "date": d.isoformat(),
            "insider_trades": {"net_insider_sentiment": "bullish"},
            "next_earnings": None, "upcoming_events": [],
            "analyst_activity": {"trend": "stable"},
        })

        r = client.post(
            "/pipeline/enrichment",
            params={"ticker": "NVDA", "date": "2026-04-17", "wait": "true"},
        )
        assert r.status_code == 200


class TestMetaEndpoint:
    def test_meta_inserts_briefing_when_missing(self, client, monkeypatch):
        from src.meta import llm_client, payload_builder

        monkeypatch.setattr(payload_builder, "build_payload", lambda s, d, tickers=None: {
            "as_of": d.isoformat(), "tickers": [{"ticker": "NVDA"}],
        })
        monkeypatch.setattr(llm_client, "generate_briefing", lambda payload: "## Briefing")

        r = client.post(
            "/pipeline/meta",
            params={"ticker": "NVDA", "date": "2026-04-17", "wait": "true"},
        )
        assert r.status_code == 200

        # Verify the briefing landed in the DB via the GET endpoint.
        check = client.get("/briefing/2026-04-17")
        assert check.status_code == 200
        assert check.json()["markdown"] == "## Briefing"

    def test_meta_updates_existing_briefing(self, client, monkeypatch):
        from src.meta import llm_client, payload_builder

        monkeypatch.setattr(payload_builder, "build_payload", lambda s, d, tickers=None: {
            "as_of": d.isoformat(), "tickers": [{"ticker": "NVDA"}],
        })
        # First call writes one body, second writes a different body.
        bodies = iter(["## First", "## Second"])
        monkeypatch.setattr(llm_client, "generate_briefing", lambda payload: next(bodies))

        r1 = client.post("/pipeline/meta", params={"ticker": "NVDA", "date": "2026-04-17", "wait": "true"})
        r2 = client.post("/pipeline/meta", params={"ticker": "NVDA", "date": "2026-04-17", "wait": "true"})
        assert r1.status_code == r2.status_code == 200

        check = client.get("/briefing/2026-04-17")
        assert check.json()["markdown"] == "## Second"

    def test_meta_scheduled_default(self, client, monkeypatch):
        from src.meta import llm_client, payload_builder

        monkeypatch.setattr(payload_builder, "build_payload", lambda s, d, tickers=None: {
            "as_of": d.isoformat(), "tickers": [{"ticker": "NVDA"}],
        })
        monkeypatch.setattr(llm_client, "generate_briefing", lambda payload: "## Bg")

        r = client.post("/pipeline/meta", params={"ticker": "NVDA", "date": "2026-04-17"})
        assert r.json()["status"] == "scheduled"
        # TestClient runs the background task synchronously after responding.
        check = client.get("/briefing/2026-04-17")
        assert check.status_code == 200


# ─────────────────────────── lifespan + CORS ─────────────────────────── #


class TestAppConfig:
    def test_cors_preflight_allowed(self, client):
        r = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code == 200
        assert "access-control-allow-origin" in {k.lower() for k in r.headers}

    def test_health_response(self, client):
        r = client.get("/health")
        assert r.json() == {"status": "ok"}

    def test_get_db_yields_session(self):
        # get_db is a generator dependency — exhaust it manually to prove
        # the close-on-exit path runs without raising.
        gen = api_main.get_db()
        sess = next(gen)
        assert sess is not None
        with pytest.raises(StopIteration):
            next(gen)
