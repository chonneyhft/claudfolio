"""Tests for the quantitative engine."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import pandas as pd

from src.engines.quantitative import aggregator, model, price_fetcher, technicals
from src.storage.models import Base, QuantDaily
from src.storage.quant_repo import upsert_quant_daily


def test_quant_package_imports() -> None:
    from src.engines.quantitative import (  # noqa: F401
        features,
        model,
        price_fetcher,
        technicals,
    )


def _series(closes: list[float], volumes: list[int] | None = None) -> list[dict]:
    start = date(2025, 1, 1)
    vols = volumes or [1_000_000] * len(closes)
    return [
        {
            "date": start + timedelta(days=i),
            "open": c,
            "high": c,
            "low": c,
            "close": c,
            "volume": vols[i],
        }
        for i, c in enumerate(closes)
    ]


class TestFetchOhlcvAsOfContract:
    def test_fetch_ohlcv_excludes_as_of_bar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """as_of contract: the as_of bar itself must NOT be returned."""
        captured: dict = {}

        def fake_download(ticker: str, **kwargs) -> pd.DataFrame:
            captured.update(kwargs)
            idx = pd.to_datetime(
                ["2024-06-12", "2024-06-13", "2024-06-14"]
            )
            return pd.DataFrame(
                {
                    "Open": [1.0, 1.0, 1.0],
                    "High": [1.0, 1.0, 1.0],
                    "Low": [1.0, 1.0, 1.0],
                    "Close": [1.0, 1.0, 1.0],
                    "Volume": [1, 1, 1],
                },
                index=idx,
            )

        monkeypatch.setattr(price_fetcher.yf, "download", fake_download)
        rows = price_fetcher.fetch_ohlcv("AAPL", date(2024, 6, 17))

        # end argument passed to yfinance must equal as_of itself (exclusive),
        # not as_of + 1 day.
        assert captured["end"] == "2024-06-17"
        assert rows, "expected non-empty OHLCV history"
        last_bar = rows[-1]["date"]
        assert last_bar < date(2024, 6, 17), (
            f"look-ahead bias: latest bar {last_bar} should be < as_of"
        )
        assert last_bar == date(2024, 6, 14)


class TestComputeIndicators:
    def test_empty_series_returns_nones(self) -> None:
        out = technicals.compute_indicators([])
        assert out["close"] is None
        assert out["rsi_14"] is None
        assert out["macd_signal"] == "insufficient_data"

    def test_short_series_still_returns_close(self) -> None:
        out = technicals.compute_indicators(_series([100.0, 101.0, 102.0]))
        assert out["close"] == 102.0
        assert out["change_1d"] == pytest.approx(0.99, abs=0.01)
        assert out["rsi_14"] is None  # not enough history
        assert out["above_50sma"] is None

    def test_rising_series_produces_high_rsi(self) -> None:
        # Mostly-up series with occasional small dips so avg_loss isn't zero.
        closes = [100.0 + i * 0.5 - (1.0 if i % 5 == 0 else 0) for i in range(60)]
        out = technicals.compute_indicators(_series(closes))
        assert out["rsi_14"] is not None and out["rsi_14"] > 70
        assert out["above_50sma"] is True
        assert "bullish" in out["macd_signal"]

    def test_falling_series_produces_low_rsi(self) -> None:
        closes = [100.0 - i * 0.5 + (1.0 if i % 5 == 0 else 0) for i in range(60)]
        out = technicals.compute_indicators(_series(closes))
        assert out["rsi_14"] is not None and out["rsi_14"] < 30
        assert out["above_50sma"] is False
        assert "bearish" in out["macd_signal"]

    def test_volume_ratio_uses_20d_window(self) -> None:
        # Under the as-of contract, iloc[-1] is the most recent legitimate bar
        # (yesterday). The ratio compares that bar's volume to the 20-day
        # rolling mean through that same bar.
        closes = [100.0] * 25
        volumes = [1_000_000] * 24 + [2_000_000]  # last bar doubles
        out = technicals.compute_indicators(_series(closes, volumes))
        # rolling(20).mean over the last 20 bars = (19 * 1M + 2M) / 20 = 1.05M
        # ratio = 2.0M / 1.05M ≈ 1.9047
        assert out["volume_vs_20d_avg"] == pytest.approx(1.9, abs=0.01)

    def test_unsorted_input_is_sorted(self) -> None:
        rows = _series([i * 1.0 for i in range(60)])
        reversed_rows = list(reversed(rows))
        out = technicals.compute_indicators(reversed_rows)
        assert out["close"] == 59.0


class TestPredictHealth:
    def test_all_bullish_is_strong(self) -> None:
        assert model.predict_health({
            "above_50sma": True, "above_200sma": True,
            "rsi_14": 55, "macd_signal": "bullish_crossover",
            "volume_vs_20d_avg": 1.5, "change_5d": 3.0,
        }) == "strong"

    def test_mixed_signals_neutral(self) -> None:
        assert model.predict_health({
            "above_50sma": True, "above_200sma": False,
            "rsi_14": 50, "macd_signal": "bearish",
            "volume_vs_20d_avg": 1.0, "change_5d": 0.0,
        }) == "neutral"

    def test_bearish_is_weak(self) -> None:
        assert model.predict_health({
            "above_50sma": False, "above_200sma": False,
            "rsi_14": 22, "macd_signal": "bearish_crossover",
            "volume_vs_20d_avg": 1.3, "change_5d": -2.0,
        }) == "weak"

    def test_missing_fields_tolerated(self) -> None:
        assert model.predict_health({}) == "neutral"


class TestAggregate:
    def test_happy_path_with_sector(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ticker_rows = _series([100.0 + i * 0.3 for i in range(60)])
        etf_rows = _series([50.0 + i * 0.05 for i in range(30)])

        def fake_fetch(sym: str, as_of: date, days: int = 300) -> list[dict]:
            return etf_rows if sym == "XLK" else ticker_rows

        monkeypatch.setattr(aggregator.price_fetcher, "fetch_ohlcv", fake_fetch)
        payload = aggregator.aggregate("NVDA", date(2026, 4, 18), sector="technology")

        assert payload["ticker"] == "NVDA"
        assert payload["date"] == "2026-04-18"
        assert payload["sector_etf"] == "XLK"
        assert payload["relative_return_5d"] is not None
        assert payload["health_score"] in ("strong", "neutral", "weak")

    def test_no_data_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(aggregator.price_fetcher, "fetch_ohlcv", lambda *a, **k: [])
        with pytest.raises(RuntimeError, match="no OHLCV"):
            aggregator.aggregate("NVDA", date(2026, 4, 18))

    def test_unknown_sector_still_produces_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            aggregator.price_fetcher,
            "fetch_ohlcv",
            lambda *a, **k: _series([100.0 + i for i in range(30)]),
        )
        payload = aggregator.aggregate("NVDA", date(2026, 4, 18), sector="unknown")
        assert payload["sector_etf"] is None
        assert payload["relative_return_5d"] is None

    def test_sector_fetch_failure_degrades_gracefully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ticker_rows = _series([100.0 + i for i in range(30)])

        def fake_fetch(sym: str, as_of: date, days: int = 300) -> list[dict]:
            if sym == "XLK":
                raise RuntimeError("ETF fetch down")
            return ticker_rows

        monkeypatch.setattr(aggregator.price_fetcher, "fetch_ohlcv", fake_fetch)
        payload = aggregator.aggregate("NVDA", date(2026, 4, 18), sector="technology")
        assert payload["sector_etf"] == "XLK"
        assert payload["relative_return_5d"] is None


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, future=True) as s:
        yield s


def _payload(**overrides) -> dict:
    base = {
        "ticker": "NVDA",
        "date": "2026-04-18",
        "close": 950.25,
        "change_1d": 1.2,
        "change_5d": 3.4,
        "change_20d": 5.6,
        "rsi_14": 62.5,
        "above_50sma": True,
        "above_200sma": True,
        "macd_signal": "bullish",
        "volume_vs_20d_avg": 1.4,
        "sector_etf": "XLK",
        "relative_return_5d": 0.8,
        "health_score": "strong",
    }
    base.update(overrides)
    return base


class TestUpsertQuantDaily:
    def test_insert_creates_row(self, session: Session) -> None:
        row = upsert_quant_daily(session, _payload())
        assert row.id is not None
        assert row.ticker == "NVDA"
        assert row.as_of == date(2026, 4, 18)
        assert row.health_score == "strong"

    def test_upsert_updates_existing(self, session: Session) -> None:
        first = upsert_quant_daily(session, _payload(close=900.0))
        second = upsert_quant_daily(session, _payload(close=955.0, health_score="neutral"))
        assert second.id == first.id
        rows = session.execute(select(QuantDaily)).scalars().all()
        assert len(rows) == 1
        assert rows[0].close == 955.0
        assert rows[0].health_score == "neutral"
