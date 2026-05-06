"""Integration tests for src.core orchestration.

These exercise each ``run_*`` function with the engines monkeypatched so the
DB writes, error-bucket logic, and cross-engine wiring are tested without
hitting any external service.
"""

from __future__ import annotations

from datetime import date as Date

import pytest
from sqlalchemy import select

from src import core
from src.storage.models import (
    BriefingDaily,
    EnrichmentDaily,
    QuantDaily,
    SentimentDaily,
    SignalDaily,
)


ON_DATE = Date(2026, 5, 1)


# ─────────────────────────── run_sentiment ─────────────────────────── #


def _sentiment_payload(ticker: str, score: float = 0.5) -> dict:
    return {
        "ticker": ticker,
        "date": ON_DATE.isoformat(),
        "sentiment_score": score,
        "sentiment_direction": "improving",
        "source_breakdown": {"news_finnhub": {"score": score, "count": 3}},
        "key_topics": ["earnings"],
        "notable_headlines": [{"headline": "Beat estimates", "score": score}],
    }


class TestRunSentiment:
    def test_writes_one_row_per_ticker(self, session, monkeypatch):
        from src.engines.sentiment import aggregator as agg

        monkeypatch.setattr(agg, "aggregate", lambda t, d: _sentiment_payload(t))

        out = core.run_sentiment(["NVDA", "AAPL"], ON_DATE, session)

        assert len(out) == 2
        rows = session.execute(select(SentimentDaily)).scalars().all()
        assert {r.ticker for r in rows} == {"NVDA", "AAPL"}

    def test_aggregator_failure_appends_error_and_continues(self, session, monkeypatch):
        from src.engines.sentiment import aggregator as agg

        def fake_aggregate(ticker, _date):
            if ticker == "BAD":
                raise RuntimeError("boom")
            return _sentiment_payload(ticker)

        monkeypatch.setattr(agg, "aggregate", fake_aggregate)

        out = core.run_sentiment(["NVDA", "BAD", "AAPL"], ON_DATE, session)

        statuses = [("error" in r) for r in out]
        assert statuses == [False, True, False]
        # Only the two successful tickers landed in the DB.
        rows = session.execute(select(SentimentDaily)).scalars().all()
        assert {r.ticker for r in rows} == {"NVDA", "AAPL"}

    def test_applies_history_for_delta(self, session, monkeypatch):
        """Verify a prior row is read and apply_history sets sentiment_delta_7d."""
        from src.engines.sentiment import aggregator as agg

        # Seed a 7-days-prior row at 0.30 — the delta should be score-0.30.
        session.add(SentimentDaily(
            ticker="NVDA",
            as_of=ON_DATE - __import__("datetime").timedelta(days=7),
            sentiment_score=0.30,
            sentiment_direction="neutral",
        ))
        session.commit()

        monkeypatch.setattr(agg, "aggregate", lambda t, d: _sentiment_payload(t, score=0.70))

        out = core.run_sentiment(["NVDA"], ON_DATE, session)
        assert out[0]["sentiment_delta_7d"] == pytest.approx(0.40, abs=1e-6)


# ─────────────────────────── run_quant ─────────────────────────── #


def _quant_payload(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "date": ON_DATE.isoformat(),
        "close": 100.0,
        "change_1d": 1.0,
        "change_5d": 2.0,
        "change_20d": 5.0,
        "rsi_14": 55.0,
        "above_50sma": True,
        "above_200sma": True,
        "macd_signal": "bullish_crossover",
        "volume_vs_20d_avg": 1.2,
        "sector_etf": "XLI",
        "relative_return_5d": 0.5,
        "health_score": "strong",
    }


class TestRunQuant:
    def test_passes_sector_through_to_aggregator(self, session, monkeypatch):
        from src.engines.quantitative import aggregator as agg

        captured = {}

        def fake(ticker, _as_of, sector=None):
            captured["sector"] = sector
            return _quant_payload(ticker)

        monkeypatch.setattr(agg, "aggregate", fake)

        core.run_quant(
            [{"ticker": "LMT", "sector": "Industrials"}], ON_DATE, session
        )

        assert captured["sector"] == "Industrials"
        rows = session.execute(select(QuantDaily)).scalars().all()
        assert len(rows) == 1
        assert rows[0].sector_etf == "XLI"

    def test_partial_failure_continues(self, session, monkeypatch):
        from src.engines.quantitative import aggregator as agg

        def fake(ticker, _as_of, sector=None):
            if ticker == "BAD":
                raise ValueError("no price data")
            return _quant_payload(ticker)

        monkeypatch.setattr(agg, "aggregate", fake)

        out = core.run_quant(
            [{"ticker": "GOOD"}, {"ticker": "BAD"}], ON_DATE, session
        )
        assert "error" not in out[0]
        assert "error" in out[1]


# ─────────────────────────── run_enrichment ─────────────────────────── #


def _enrichment_payload(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "date": ON_DATE.isoformat(),
        "insider_trades": {"net_insider_sentiment": "bullish"},
        "next_earnings": {"date": "2026-05-15", "days_until": 14},
        "upcoming_events": [],
        "analyst_activity": {"trend": "upgrade"},
    }


class TestRunEnrichment:
    def test_writes_rows(self, session, monkeypatch):
        from src.engines.enrichment import aggregator as agg

        monkeypatch.setattr(agg, "aggregate", lambda t, d: _enrichment_payload(t))

        core.run_enrichment(["NVDA"], ON_DATE, session)

        rows = session.execute(select(EnrichmentDaily)).scalars().all()
        assert len(rows) == 1
        assert rows[0].insider_trades["net_insider_sentiment"] == "bullish"

    def test_handles_aggregator_exception(self, session, monkeypatch):
        from src.engines.enrichment import aggregator as agg

        monkeypatch.setattr(agg, "aggregate", lambda t, d: (_ for _ in ()).throw(RuntimeError("api down")))

        out = core.run_enrichment(["NVDA"], ON_DATE, session)
        assert "error" in out[0]


# ─────────────────────────── run_signals ─────────────────────────── #


class TestRunSignals:
    def test_empty_watchlist_returns_empty_results(self, session, monkeypatch):
        monkeypatch.setattr(core, "load_watchlist", lambda: [], raising=False)
        # core.run_signals imports load_watchlist locally — patch the source.
        from src import config as cfg
        monkeypatch.setattr(cfg, "load_watchlist", lambda: [])

        out = core.run_signals(ON_DATE, session)
        assert out == {"sentiment": [], "quant": [], "enrichment": []}

    def test_runs_all_three_engines(self, session, monkeypatch):
        from src import config as cfg
        from src.engines.enrichment import aggregator as enr_agg
        from src.engines.quantitative import aggregator as quant_agg
        from src.engines.sentiment import aggregator as sent_agg

        monkeypatch.setattr(cfg, "load_watchlist", lambda: [{"ticker": "NVDA", "sector": "Tech"}])
        monkeypatch.setattr(sent_agg, "aggregate", lambda t, d: _sentiment_payload(t))
        monkeypatch.setattr(quant_agg, "aggregate", lambda t, d, sector=None: _quant_payload(t))
        monkeypatch.setattr(enr_agg, "aggregate", lambda t, d: _enrichment_payload(t))

        out = core.run_signals(ON_DATE, session)
        assert len(out["sentiment"]) == 1
        assert len(out["quant"]) == 1
        assert len(out["enrichment"]) == 1


# ─────────────────────────── run_meta ─────────────────────────── #


class TestRunMeta:
    def test_calls_llm_with_payload_and_formats(self, session, monkeypatch):
        from src.meta import llm_client, payload_builder

        monkeypatch.setattr(payload_builder, "build_payload", lambda s, d, tickers=None: {"as_of": d.isoformat(), "tickers": [{"ticker": "NVDA"}]})
        monkeypatch.setattr(llm_client, "generate_briefing", lambda payload: "## Briefing for NVDA\n\nLooks strong.")

        out = core.run_meta(["NVDA"], ON_DATE, session)

        assert "Briefing" in out
        assert "NVDA" in out


# ─────────────────────────── earnings_calendar ─────────────────────────── #


class TestEarningsCalendar:
    def test_skips_tickers_with_no_upcoming_event(self, monkeypatch):
        from src import config as cfg
        from src.engines.earnings import consensus
        from src.engines.enrichment import event_calendar

        monkeypatch.setattr(cfg, "load_watchlist", lambda: [
            {"ticker": "AAA"}, {"ticker": "BBB"},
        ])

        def fake_fetch(ticker, _on_date, lookahead_days=14):
            return [{"date": "2026-05-10", "epsEstimate": 1.5}] if ticker == "AAA" else []

        monkeypatch.setattr(event_calendar, "fetch_earnings", fake_fetch)
        # summarize is the real one — exercises that path too.
        monkeypatch.setattr(consensus, "fetch_estimates", lambda t: {"eps_estimate": 1.5})

        rows = core.earnings_calendar(ON_DATE)
        assert [r["ticker"] for r in rows] == ["AAA"]

    def test_consensus_failure_does_not_drop_the_row(self, monkeypatch):
        from src import config as cfg
        from src.engines.earnings import consensus
        from src.engines.enrichment import event_calendar

        monkeypatch.setattr(cfg, "load_watchlist", lambda: [{"ticker": "AAA"}])
        monkeypatch.setattr(event_calendar, "fetch_earnings", lambda t, d, lookahead_days=14: [{"date": "2026-05-10", "epsEstimate": None}])

        def boom(_t):
            raise RuntimeError("rate limited")

        monkeypatch.setattr(consensus, "fetch_estimates", boom)

        rows = core.earnings_calendar(ON_DATE)
        assert len(rows) == 1
        assert rows[0]["consensus_eps"] is None


# ─────────────────────────── log_outcome / log_signal ─────────────────────── #


class TestLogHelpers:
    def test_log_outcome_persists(self, session):
        core.log_outcome({
            "ticker": "NVDA",
            "earnings_date": Date(2026, 5, 22),
            "brief_date": ON_DATE,
            "predicted_dir": "bullish",
            "conviction": 0.75,
            "actual_eps_surp": None,
            "actual_rev_surp": None,
            "stock_move_1d": None,
            "outcome": "pending",
            "notes": None,
        }, session)
        from src.storage.earnings_repo import get_latest_outcome

        row = get_latest_outcome(session, "NVDA")
        assert row is not None
        assert row.predicted_dir == "bullish"

    def test_log_signal_persists(self, session):
        core.log_signal({
            "ticker": "NVDA",
            "as_of": ON_DATE,
            "direction": "bullish",
            "conviction": 0.6,
            "dominant_component": "convergence",
            "reasoning": "test",
            "entry_price": 950.0,
            "signal_components": {},
        }, session)
        rows = session.execute(select(SignalDaily)).scalars().all()
        assert len(rows) == 1
        assert rows[0].direction == "bullish"


# ─────────────────────────── generate_signals ─────────────────────────── #


class TestGenerateSignals:
    def test_no_engine_data_returns_empty(self, session, monkeypatch):
        from src.meta import payload_builder

        monkeypatch.setattr(payload_builder, "build_payload", lambda s, d: {"as_of": d.isoformat(), "tickers": [{"ticker": "NVDA"}]})

        out = core.generate_signals(ON_DATE, session)
        assert out == []

    def test_logs_signals_from_llm_response(self, session, monkeypatch):
        from src.meta import llm_client, payload_builder

        monkeypatch.setattr(payload_builder, "build_payload", lambda s, d: {
            "as_of": d.isoformat(),
            "tickers": [
                {"ticker": "NVDA", "sentiment": {"score": 0.7}, "quant": None, "enrichment": None},
            ],
        })

        json_response = '[{"ticker": "NVDA", "direction": "bullish", "conviction": 0.8, "dominant_component": "sentiment", "reasoning": "Earnings beat", "entry_price": 950.0}]'
        monkeypatch.setattr(llm_client, "generate_briefing", lambda payload, system_prompt=None, model=None: json_response)

        out = core.generate_signals(ON_DATE, session)
        assert len(out) == 1
        assert out[0]["ticker"] == "NVDA"
        assert out[0]["conviction"] == 0.8

        rows = session.execute(select(SignalDaily)).scalars().all()
        assert len(rows) == 1

    def test_strips_markdown_code_fences(self, session, monkeypatch):
        from src.meta import llm_client, payload_builder

        monkeypatch.setattr(payload_builder, "build_payload", lambda s, d: {
            "as_of": d.isoformat(),
            "tickers": [{"ticker": "NVDA", "quant": {"close": 950}}],
        })

        wrapped = '```json\n[{"ticker": "NVDA", "direction": "bearish", "conviction": 0.4, "dominant_component": "quant", "reasoning": "RSI overbought"}]\n```'
        monkeypatch.setattr(llm_client, "generate_briefing", lambda payload, system_prompt=None, model=None: wrapped)

        out = core.generate_signals(ON_DATE, session)
        assert out[0]["direction"] == "bearish"

    def test_clamps_invalid_direction_and_dominant_to_safe_defaults(self, session, monkeypatch):
        from src.meta import llm_client, payload_builder

        monkeypatch.setattr(payload_builder, "build_payload", lambda s, d: {
            "as_of": d.isoformat(),
            "tickers": [{"ticker": "NVDA", "sentiment": {"score": 0.5}}],
        })

        rogue = '[{"ticker": "nvda", "direction": "moonshot", "conviction": 5.0, "dominant_component": "vibes", "reasoning": "yolo"}]'
        monkeypatch.setattr(llm_client, "generate_briefing", lambda payload, system_prompt=None, model=None: rogue)

        out = core.generate_signals(ON_DATE, session)
        assert out[0]["direction"] == "neutral"          # invalid → neutral
        assert out[0]["dominant_component"] == "convergence"  # invalid → convergence
        assert out[0]["conviction"] == 1.0               # clamped to [0, 1]
        assert out[0]["ticker"] == "NVDA"                # uppercased


# ─────────────────────────── get_ticker_summary ─────────────────────────── #


class TestGetTickerSummary:
    def test_returns_none_blocks_when_no_data(self, session):
        out = core.get_ticker_summary("ZZZZ", ON_DATE, session)
        assert out["ticker"] == "ZZZZ"
        assert out["sentiment"] is None
        assert out["quant"] is None
        assert out["enrichment"] is None
        assert out["latest_outcome"] is None

    def test_returns_data_when_present(self, session):
        session.add(SentimentDaily(
            ticker="NVDA",
            as_of=ON_DATE,
            sentiment_score=0.7,
            sentiment_direction="improving",
        ))
        session.commit()
        out = core.get_ticker_summary("NVDA", ON_DATE, session)
        assert out["sentiment"]["score"] == 0.7
