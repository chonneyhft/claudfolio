"""Tests for the Streamlit agent dashboard.

Two layers:

1. Unit tests for ``_fetch_current_prices`` (the only pure helper).
2. App-level smoke tests via ``streamlit.testing.v1.AppTest`` against a
   temp SQLite DB seeded with fixtures.
"""

from __future__ import annotations

import builtins
import importlib
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from src.storage import db as db_module
from src.storage.models import (
    AgentSession,
    Base,
    Portfolio,
    Position,
    Trade,
)


DASHBOARD_PATH = str(
    Path(__file__).resolve().parent.parent / "src" / "agent" / "dashboard.py"
)


# ---------------------------------------------------------------------------
# Fixture: isolated temp DB wired through SFE_DB_URL
# ---------------------------------------------------------------------------


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Point the storage layer at a fresh sqlite file for the duration of the test."""
    db_file = tmp_path / "sfe_test.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("SFE_DB_URL", url)

    # Clear cached engine / session factory so they pick up the new URL.
    db_module.get_engine.cache_clear()
    db_module._session_factory.cache_clear()

    # Also clear Streamlit's resource cache so the dashboard's @st.cache_resource
    # _init_db doesn't hold a stale engine across tests.
    import streamlit as st
    st.cache_resource.clear()

    engine = db_module.get_engine()
    Base.metadata.create_all(engine)

    session = db_module.get_session()
    try:
        yield session
    finally:
        session.close()
        db_module.get_engine.cache_clear()
        db_module._session_factory.cache_clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _make_portfolio(session: Session, name: str = "default") -> Portfolio:
    p = Portfolio(
        name=name,
        starting_equity=100_000.0,
        cash=100_000.0,
        inception_date=date(2026, 1, 1),
        active=True,
    )
    session.add(p)
    session.commit()
    return p


def _add_position(
    session: Session,
    portfolio: Portfolio,
    ticker: str,
    *,
    direction: str = "long",
    shares: float = 10.0,
    entry_price: float = 100.0,
    cash_delta: float | None = None,
) -> Position:
    """Add a position and adjust portfolio cash to keep equity sane."""
    if cash_delta is None:
        cash_delta = -shares * entry_price if direction == "long" else shares * entry_price
    portfolio.cash += cash_delta
    pos = Position(
        portfolio_id=portfolio.id,
        ticker=ticker,
        direction=direction,
        shares=shares,
        entry_price=entry_price,
        entry_date=date(2026, 2, 1),
        current_price=entry_price,
    )
    session.add(pos)
    session.commit()
    return pos


def _add_session(
    session: Session,
    portfolio: Portfolio,
    *,
    run_date: date,
    decisions: int = 1,
    equity_before: float = 100_000.0,
    equity_after: float = 101_000.0,
    trace: list[dict] | None = None,
) -> AgentSession:
    row = AgentSession(
        portfolio_id=portfolio.id,
        run_date=run_date,
        decisions_made=decisions,
        reasoning_trace=trace if trace is not None else [],
        portfolio_snapshot_before={"equity": equity_before},
        portfolio_snapshot_after={"equity": equity_after},
        model="claude-opus-4-6",
    )
    session.add(row)
    session.commit()
    return row


# ---------------------------------------------------------------------------
# 1. Unit tests for _fetch_current_prices
# ---------------------------------------------------------------------------


def _import_dashboard_module():
    """Import dashboard.py as a module so we can call its helpers directly.

    We can't simply ``import src.agent.dashboard`` because importing it runs
    the Streamlit script. The helper lives above the Streamlit entrypoints,
    but ``st.set_page_config`` runs at import time. AppTest handles that for
    the integration tests; for unit tests we read the helper out of the
    already-loaded module if present, otherwise import inside a patched
    Streamlit context.
    """
    if "src.agent.dashboard" in sys.modules:
        return sys.modules["src.agent.dashboard"]
    # Import under a no-op streamlit page-config; AppTest may not be active.
    import streamlit as st
    with patch.object(st, "set_page_config", lambda **_: None):
        # Other top-level st.* calls will still execute against a real
        # session-less runtime and may raise. For the helper-only tests we
        # bail out and read the function via exec from source.
        try:
            return importlib.import_module("src.agent.dashboard")
        except Exception:
            pass
    return None


def _load_fetch_helper():
    """Pull ``_fetch_current_prices`` out of dashboard.py without running the script."""
    src = Path(DASHBOARD_PATH).read_text()
    # Extract just the function definition. It's self-contained and only
    # depends on ``yfinance`` (imported lazily inside it).
    start = src.index("def _fetch_current_prices")
    # End at the next top-level def/comment block.
    end = src.index("\n# ---", start)
    snippet = src[start:end]
    namespace: dict = {}
    exec(snippet, namespace)
    return namespace["_fetch_current_prices"]


class TestFetchCurrentPrices:
    def setup_method(self) -> None:
        self.fetch = _load_fetch_helper()

    def test_returns_empty_when_yfinance_missing(self) -> None:
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "yfinance":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", fake_import):
            assert self.fetch(["AAPL"]) == {}

    def test_returns_empty_for_empty_ticker_list(self) -> None:
        # No tickers means no yfinance calls; result is just {}.
        fake_yf = MagicMock()
        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            assert self.fetch([]) == {}
        fake_yf.Ticker.assert_not_called()

    def test_returns_last_price_when_available(self) -> None:
        fake_yf = MagicMock()
        info = MagicMock(last_price=150.5, previous_close=149.0)
        fake_yf.Ticker.return_value.fast_info = info

        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            assert self.fetch(["AAPL"]) == {"AAPL": 150.5}

    def test_falls_back_to_previous_close(self) -> None:
        fake_yf = MagicMock()
        info = MagicMock(spec=["last_price", "previous_close"])
        info.last_price = None
        info.previous_close = 149.0
        fake_yf.Ticker.return_value.fast_info = info

        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            assert self.fetch(["AAPL"]) == {"AAPL": 149.0}

    def test_skips_ticker_when_both_prices_none(self) -> None:
        fake_yf = MagicMock()
        info = MagicMock(spec=["last_price", "previous_close"])
        info.last_price = None
        info.previous_close = None
        fake_yf.Ticker.return_value.fast_info = info

        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            assert self.fetch(["AAPL"]) == {}

    def test_skips_ticker_that_raises(self) -> None:
        fake_yf = MagicMock()
        good_info = MagicMock(last_price=200.0, previous_close=199.0)

        def ticker_side_effect(sym):
            if sym == "BAD":
                raise RuntimeError("network")
            t = MagicMock()
            t.fast_info = good_info
            return t

        fake_yf.Ticker.side_effect = ticker_side_effect
        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            assert self.fetch(["BAD", "AAPL"]) == {"AAPL": 200.0}


# ---------------------------------------------------------------------------
# 2. App-level smoke tests via AppTest
# ---------------------------------------------------------------------------


def _run_app() -> AppTest:
    """Run dashboard.py fresh and return the AppTest harness.

    Patches plotly's Figure methods used by the dashboard to no-ops — when
    AppTest re-runs scripts in the same process, plotly's validators see
    Shape instances from a "different" plotly module identity and raise
    spurious 'Invalid Shape' errors. The chart logic isn't what we test
    here; widget tree and data flow are.
    """
    import streamlit as st
    import plotly.graph_objects as go

    with patch.object(st, "plotly_chart", lambda *a, **k: None), \
         patch.object(go.Figure, "add_hline", lambda self, *a, **k: self), \
         patch.object(go.Figure, "add_trace", lambda self, *a, **k: self), \
         patch.object(go.Figure, "update_layout", lambda self, *a, **k: self):
        at = AppTest.from_file(DASHBOARD_PATH, default_timeout=15)
        at.run()
    return at


class TestEmptyDB:
    def test_warns_and_stops_when_no_portfolios(self, temp_db: Session) -> None:
        at = _run_app()
        # Page renders the title, then warns and stops before metrics.
        assert any("No portfolios found" in w.value for w in at.warning)
        # Metrics should not have rendered (st.stop ran).
        assert len(at.metric) == 0


class TestPortfolioWithoutActivity:
    def test_renders_metrics_and_empty_state_messages(self, temp_db: Session) -> None:
        _make_portfolio(temp_db)
        at = _run_app()

        # Top-level metrics rendered (5 of them).
        assert len(at.metric) == 5
        equity_metric = at.metric[0]
        assert "100,000" in equity_metric.value

        info_messages = [i.value for i in at.info]
        assert any("No open positions" in m for m in info_messages)
        assert any("No agent sessions yet" in m for m in info_messages)


class TestPortfolioWithPositions:
    def test_positions_render_without_error(self, temp_db: Session) -> None:
        portfolio = _make_portfolio(temp_db)
        _add_position(temp_db, portfolio, "AAPL", shares=10, entry_price=150.0)
        _add_position(temp_db, portfolio, "MSFT", shares=5, entry_price=300.0)

        with patch.dict(sys.modules, {"yfinance": MagicMock()}):
            at = _run_app()

        assert not at.exception
        # Positions section should render a dataframe (positions table).
        assert len(at.dataframe) >= 1
        # No "No open positions" info should appear.
        assert not any("No open positions" in i.value for i in at.info)


class TestRefreshPricesButton:
    def test_refresh_button_is_present(self, temp_db: Session) -> None:
        """Verify the Refresh Prices button renders in the sidebar.

        We don't assert click-then-rerun behavior here — re-running an
        AppTest script in the same process triggers numpy reload errors
        from streamlit's pandas/pyarrow path. The behavior under test is
        that the button exists and is wired into the sidebar.
        """
        portfolio = _make_portfolio(temp_db)
        _add_position(temp_db, portfolio, "AAPL", shares=10, entry_price=150.0)

        with patch.dict(sys.modules, {"yfinance": MagicMock()}):
            at = _run_app()

        labels = [b.label for b in at.sidebar.button]
        assert "Refresh Prices" in labels


class TestAgentSessions:
    def test_equity_curve_and_session_selector(self, temp_db: Session) -> None:
        portfolio = _make_portfolio(temp_db)
        _add_session(
            temp_db,
            portfolio,
            run_date=date(2026, 4, 1),
            equity_before=100_000.0,
            equity_after=101_000.0,
        )
        _add_session(
            temp_db,
            portfolio,
            run_date=date(2026, 4, 2),
            equity_before=101_000.0,
            equity_after=102_500.0,
        )

        with patch.dict(sys.modules, {"yfinance": MagicMock()}):
            at = _run_app()

        assert not at.exception
        session_select = next(
            s for s in at.selectbox if s.label == "Select session"
        )
        assert len(session_select.options) == 2

        # 5 top-level metrics + 3 session metrics (decisions / before / after).
        assert len(at.metric) == 8

    def test_reasoning_trace_renders_expected_entries(self, temp_db: Session) -> None:
        portfolio = _make_portfolio(temp_db)
        trace = [
            {
                "type": "tool_call",
                "tool": "open_position",
                "input": {
                    "ticker": "AAPL",
                    "direction": "long",
                    "allocation_pct": 10,
                    "reasoning": "strong sentiment",
                },
                "result": {"status": "opened"},
            },
            {
                "type": "tool_call",
                "tool": "get_signals",
                "input": {"ticker": "AAPL"},
                "result": {"direction": "long"},
            },
            {
                "type": "final_message",
                "content": "Done for the day.",
            },
        ]
        _add_session(
            temp_db,
            portfolio,
            run_date=date(2026, 4, 1),
            trace=trace,
        )

        with patch.dict(sys.modules, {"yfinance": MagicMock()}):
            at = _run_app()

        # The final_message expander writes markdown with the content.
        markdowns = [m.value for m in at.markdown]
        assert any("Done for the day." in m for m in markdowns)
