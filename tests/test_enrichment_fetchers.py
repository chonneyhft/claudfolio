"""Tests for the enrichment HTTP fetchers.

The aggregator + summarize logic is covered in test_enrichment.py; this module
focuses on the HTTP-call layer: missing API key, request shape, response
parsing, and HTTP errors.
"""

from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest

from src.engines.enrichment import (
    analyst_revisions,
    event_calendar,
    insider_trades,
)


ON = date(2026, 4, 18)


# ─────────────────────────── shared httpx mock ─────────────────────────── #


class FakeResponse:
    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=None, response=None  # type: ignore[arg-type]
            )

    def json(self):
        return self._payload


def _capturing_get(payload, status: int = 200):
    """Return a (recorder dict, callable) pair. Use the dict to assert on URL/params."""
    captured: dict = {}

    def fake_get(url: str, *, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return FakeResponse(payload, status)

    return captured, fake_get


# ─────────────────────────── insider_trades.fetch_transactions ───── #


class TestInsiderFetch:
    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("FINNHUB_KEY", raising=False)
        with pytest.raises(RuntimeError, match="FINNHUB_KEY"):
            insider_trades.fetch_transactions("NVDA", ON)

    def test_request_shape(self, monkeypatch):
        monkeypatch.setenv("FINNHUB_KEY", "key123")
        captured, fake = _capturing_get({"data": []})
        monkeypatch.setattr(insider_trades.httpx, "get", fake)

        insider_trades.fetch_transactions("NVDA", ON, lookback_days=10)

        assert "/stock/insider-transactions" in captured["url"]
        assert captured["params"]["symbol"] == "NVDA"
        assert captured["params"]["token"] == "key123"
        assert captured["params"]["to"] == ON.isoformat()
        # lookback_days=10 → window of (10-1)=9 days back per impl.
        assert captured["params"]["from"] == (ON - timedelta(days=9)).isoformat()

    def test_returns_data_array(self, monkeypatch):
        monkeypatch.setenv("FINNHUB_KEY", "k")
        rows = [{"transactionCode": "P", "change": 100, "transactionPrice": 50.0}]
        _, fake = _capturing_get({"data": rows})
        monkeypatch.setattr(insider_trades.httpx, "get", fake)

        out = insider_trades.fetch_transactions("NVDA", ON)
        assert out == rows

    def test_empty_payload_returns_empty_list(self, monkeypatch):
        monkeypatch.setenv("FINNHUB_KEY", "k")
        _, fake = _capturing_get({})
        monkeypatch.setattr(insider_trades.httpx, "get", fake)

        assert insider_trades.fetch_transactions("NVDA", ON) == []

    def test_null_data_field_returns_empty_list(self, monkeypatch):
        monkeypatch.setenv("FINNHUB_KEY", "k")
        _, fake = _capturing_get({"data": None})
        monkeypatch.setattr(insider_trades.httpx, "get", fake)

        assert insider_trades.fetch_transactions("NVDA", ON) == []

    def test_http_error_propagates(self, monkeypatch):
        monkeypatch.setenv("FINNHUB_KEY", "k")
        _, fake = _capturing_get({}, status=500)
        monkeypatch.setattr(insider_trades.httpx, "get", fake)

        with pytest.raises(httpx.HTTPStatusError):
            insider_trades.fetch_transactions("NVDA", ON)


# ─────────────────────────── event_calendar.fetch_earnings ───── #


class TestEarningsFetch:
    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("FINNHUB_KEY", raising=False)
        with pytest.raises(RuntimeError, match="FINNHUB_KEY"):
            event_calendar.fetch_earnings("NVDA", ON)

    def test_lookahead_window_in_request(self, monkeypatch):
        monkeypatch.setenv("FINNHUB_KEY", "k")
        captured, fake = _capturing_get({"earningsCalendar": []})
        monkeypatch.setattr(event_calendar.httpx, "get", fake)

        event_calendar.fetch_earnings("NVDA", ON, lookahead_days=14)
        assert captured["params"]["from"] == ON.isoformat()
        assert captured["params"]["to"] == (ON + timedelta(days=14)).isoformat()

    def test_returns_calendar_array(self, monkeypatch):
        monkeypatch.setenv("FINNHUB_KEY", "k")
        cal = [{"date": "2026-04-22", "epsEstimate": 1.5}]
        _, fake = _capturing_get({"earningsCalendar": cal})
        monkeypatch.setattr(event_calendar.httpx, "get", fake)

        out = event_calendar.fetch_earnings("NVDA", ON)
        assert out == cal

    def test_missing_calendar_key(self, monkeypatch):
        monkeypatch.setenv("FINNHUB_KEY", "k")
        _, fake = _capturing_get({})
        monkeypatch.setattr(event_calendar.httpx, "get", fake)

        assert event_calendar.fetch_earnings("NVDA", ON) == []


# ─────────────────────────── analyst_revisions.fetch_recommendations ─── #


class TestAnalystFetch:
    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("FINNHUB_KEY", raising=False)
        with pytest.raises(RuntimeError, match="FINNHUB_KEY"):
            analyst_revisions.fetch_recommendations("NVDA")

    def test_sorts_periods_descending(self, monkeypatch):
        monkeypatch.setenv("FINNHUB_KEY", "k")
        # Returned out-of-order — fetcher must reorder so latest is index 0.
        unsorted = [
            {"period": "2026-02-01", "strongBuy": 1},
            {"period": "2026-04-01", "strongBuy": 5},
            {"period": "2026-03-01", "strongBuy": 3},
        ]
        _, fake = _capturing_get(unsorted)
        monkeypatch.setattr(analyst_revisions.httpx, "get", fake)

        out = analyst_revisions.fetch_recommendations("NVDA")
        assert [r["period"] for r in out] == ["2026-04-01", "2026-03-01", "2026-02-01"]

    def test_non_list_payload_returns_empty(self, monkeypatch):
        monkeypatch.setenv("FINNHUB_KEY", "k")
        _, fake = _capturing_get({"error": "nope"})  # dict, not list
        monkeypatch.setattr(analyst_revisions.httpx, "get", fake)

        assert analyst_revisions.fetch_recommendations("NVDA") == []
