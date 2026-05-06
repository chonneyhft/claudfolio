"""Tests for the agentic portfolio harness.

The Anthropic SDK is mocked so the tool-use loop is exercised end-to-end
without any real API calls. yfinance is mocked at the seam in
``_fetch_current_prices``.
"""

from __future__ import annotations

from datetime import date as Date
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select

from src.agent import harness
from src.storage.models import AgentSession, Position


ON_DATE = Date(2026, 5, 1)


# ─────────────────────────── Anthropic SDK fakes ─────────────────────────── #


class FakeBlock(SimpleNamespace):
    """Stand-in for an anthropic content block (text or tool_use)."""


class FakeResponse(SimpleNamespace):
    pass


class FakeAnthropic:
    """Drop-in for anthropic.Anthropic that replays a scripted sequence of
    responses turn-by-turn. Each scripted item is one ``messages.create`` reply."""

    def __init__(self, scripted: list[FakeResponse]):
        self._scripted = list(scripted)
        self.calls: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._scripted:
            # Fail loudly rather than hang — tests should script enough turns.
            raise AssertionError("FakeAnthropic ran out of scripted responses")
        return self._scripted.pop(0)


def _text_response(text: str) -> FakeResponse:
    return FakeResponse(
        stop_reason="end_turn",
        content=[FakeBlock(type="text", text=text)],
    )


def _tool_response(tool_name: str, tool_input: dict, tool_id: str = "tool_1") -> FakeResponse:
    return FakeResponse(
        stop_reason="tool_use",
        content=[FakeBlock(type="tool_use", name=tool_name, input=tool_input, id=tool_id)],
    )


# ─────────────────────────── Shared fixtures ─────────────────────────── #


@pytest.fixture()
def env(monkeypatch):
    """Standard env setup: API key present, prompt file stubbed."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(harness, "_load_system_prompt", lambda: "system prompt")
    monkeypatch.setattr(harness, "_fetch_current_prices", lambda tickers: {t: 100.0 for t in tickers})

    from src.meta import payload_builder

    monkeypatch.setattr(payload_builder, "build_payload", lambda s, d: {
        "as_of": d.isoformat(),
        "tickers": [{"ticker": "NVDA", "sentiment": {"score": 0.7}}],
    })


def _install_fake_sdk(monkeypatch, scripted: list[FakeResponse]) -> FakeAnthropic:
    """Install a fake anthropic module so ``import anthropic`` inside harness
    returns our scripted client."""
    fake_client = FakeAnthropic(scripted)
    fake_module = SimpleNamespace(Anthropic=lambda: fake_client)

    import sys

    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    return fake_client


# ─────────────────────────── Pre-flight checks ─────────────────────────── #


class TestPreflight:
    def test_missing_api_key_raises(self, session, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # Stub anthropic so the missing-import branch isn't what fails.
        import sys

        monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda: None))

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            harness.run_agent(session, ON_DATE)

    def test_missing_anthropic_sdk_raises(self, session, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        # Force `import anthropic` inside the function to fail.
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        with pytest.raises(RuntimeError, match="anthropic SDK not installed"):
            harness.run_agent(session, ON_DATE)


# ─────────────────────────── Tool-use loop ─────────────────────────── #


class TestToolLoop:
    def test_immediate_end_turn_records_final_message(self, session, env, monkeypatch):
        client = _install_fake_sdk(monkeypatch, [_text_response("No trades today.")])

        result = harness.run_agent(session, ON_DATE)

        assert result["decisions_made"] == 0
        assert result["reasoning_trace"][-1]["type"] == "final_message"
        assert "No trades today." in result["reasoning_trace"][-1]["content"]
        # One messages.create call total.
        assert len(client.calls) == 1

    def test_tool_call_then_end_turn(self, session, env, monkeypatch):
        scripted = [
            _tool_response("get_portfolio_state", {}),
            _text_response("Done."),
        ]
        _install_fake_sdk(monkeypatch, scripted)

        result = harness.run_agent(session, ON_DATE)

        # Exactly one tool_call entry plus the final message.
        types = [t["type"] for t in result["reasoning_trace"]]
        assert types.count("tool_call") == 1
        assert types[-1] == "final_message"

    def test_open_position_increments_decisions_and_persists(self, session, env, monkeypatch):
        scripted = [
            _tool_response("open_position", {
                "ticker": "NVDA",
                "direction": "long",
                "allocation_pct": 5.0,
                "reasoning": "strong sentiment",
            }),
            _text_response("Opened NVDA."),
        ]
        _install_fake_sdk(monkeypatch, scripted)

        result = harness.run_agent(session, ON_DATE)

        assert result["decisions_made"] == 1
        positions = session.execute(select(Position)).scalars().all()
        assert len(positions) == 1
        assert positions[0].ticker == "NVDA"

    def test_failed_trade_does_not_increment_decisions(self, session, env, monkeypatch):
        # Open a position with a ticker we have no price for — the tool returns
        # an error dict, which must NOT count as a decision.
        scripted = [
            _tool_response("open_position", {
                "ticker": "ZZZZ",  # no price returned by stub
                "direction": "long",
                "allocation_pct": 5.0,
                "reasoning": "test",
            }),
            _text_response("Done."),
        ]
        _install_fake_sdk(monkeypatch, scripted)

        result = harness.run_agent(session, ON_DATE)

        assert result["decisions_made"] == 0
        # Last tool_call result block should contain an error.
        tool_call = [t for t in result["reasoning_trace"] if t["type"] == "tool_call"][0]
        assert "error" in tool_call["result"]

    def test_max_turns_logged_warning(self, session, env, monkeypatch):
        # Always return a tool call — never end_turn — so we hit MAX_TURNS.
        always_tool = [
            _tool_response("get_portfolio_state", {}, tool_id=f"t{i}")
            for i in range(harness.MAX_TURNS)
        ]
        _install_fake_sdk(monkeypatch, always_tool)

        result = harness.run_agent(session, ON_DATE)

        # Loop exited via the for/else — no final_message recorded.
        assert all(t["type"] != "final_message" for t in result["reasoning_trace"])
        # But every turn is captured as a tool_call.
        assert sum(1 for t in result["reasoning_trace"] if t["type"] == "tool_call") == harness.MAX_TURNS

    def test_no_tool_calls_no_text_breaks_loop(self, session, env, monkeypatch):
        # Anthropic returns a non-end_turn response with neither text nor
        # tool_use — harness should break silently rather than loop.
        weird = FakeResponse(stop_reason="other", content=[])
        _install_fake_sdk(monkeypatch, [weird])

        # Should not raise.
        result = harness.run_agent(session, ON_DATE)
        assert result["decisions_made"] == 0

    def test_session_logged_to_db(self, session, env, monkeypatch):
        _install_fake_sdk(monkeypatch, [_text_response("Done.")])

        result = harness.run_agent(session, ON_DATE)

        rows = session.execute(select(AgentSession)).scalars().all()
        assert len(rows) == 1
        assert rows[0].run_date == ON_DATE
        assert rows[0].decisions_made == result["decisions_made"]


# ─────────────────────────── Helpers ─────────────────────────── #


class TestFetchPrices:
    def test_returns_empty_when_yfinance_missing(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "yfinance":
                raise ImportError
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        assert harness._fetch_current_prices(["NVDA"]) == {}

    def test_skips_tickers_with_no_price(self, monkeypatch):
        import sys

        class FakeFastInfo:
            def __init__(self, price):
                self.last_price = price
                self.previous_close = price

        class FakeTicker:
            def __init__(self, sym):
                self.fast_info = FakeFastInfo(150.0) if sym == "OK" else FakeFastInfo(None)

        fake_yf = SimpleNamespace(Ticker=FakeTicker)
        monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

        prices = harness._fetch_current_prices(["OK", "BAD"])
        assert prices == {"OK": 150.0}

    def test_per_ticker_failure_is_logged_not_raised(self, monkeypatch):
        import sys

        class Boom:
            @property
            def fast_info(self):
                raise RuntimeError("network")

        fake_yf = SimpleNamespace(Ticker=lambda _t: Boom())
        monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

        # Must not raise — failures are absorbed per-ticker.
        assert harness._fetch_current_prices(["BAD"]) == {}
