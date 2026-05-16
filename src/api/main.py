"""FastAPI application for SFE.

Read endpoints serve the latest engine outputs from the SQLite store;
write endpoints trigger pipeline runs (sync for single-ticker,
background tasks for full-watchlist) that reuse the same aggregators
and repositories as the ``sfe`` CLI.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date as Date
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api import schemas
from src.config import load_watchlist
from src.storage.db import _session_factory, get_engine
from src.storage.models import (
    Base,
    BriefingDaily,
    EnrichmentDaily,
    QuantDaily,
    SentimentDaily,
)

DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _init_db() -> None:
    engine = get_engine()
    db_path = engine.url.database
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.bootstrap import load_env

    load_env()
    _init_db()
    yield


app = FastAPI(title="SFE API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("SFE_CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


# ─────────────────────────── Read helpers ─────────────────────────── #


def _latest(session: Session, model, ticker: str, on_date: Date):
    stmt = (
        select(model)
        .where(model.ticker == ticker, model.as_of <= on_date)
        .order_by(model.as_of.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def _sentiment_view(row: SentimentDaily | None) -> schemas.SentimentView | None:
    if row is None:
        return None
    return schemas.SentimentView(
        as_of=row.as_of,
        sentiment_score=row.sentiment_score,
        sentiment_direction=row.sentiment_direction,
        sentiment_delta_7d=row.sentiment_delta_7d,
        source_breakdown=row.source_breakdown or {},
        key_topics=row.key_topics or [],
        notable_headlines=row.notable_headlines or [],
    )


def _quant_view(row: QuantDaily | None) -> schemas.QuantView | None:
    if row is None:
        return None
    return schemas.QuantView(
        as_of=row.as_of,
        close=row.close,
        change_1d=row.change_1d,
        change_5d=row.change_5d,
        change_20d=row.change_20d,
        rsi_14=row.rsi_14,
        above_50sma=row.above_50sma,
        above_200sma=row.above_200sma,
        macd_signal=row.macd_signal,
        volume_vs_20d_avg=row.volume_vs_20d_avg,
        sector_etf=row.sector_etf,
        relative_return_5d=row.relative_return_5d,
        health_score=row.health_score,
    )


def _enrichment_view(row: EnrichmentDaily | None) -> schemas.EnrichmentView | None:
    if row is None:
        return None
    return schemas.EnrichmentView(
        as_of=row.as_of,
        insider_trades=row.insider_trades or {},
        next_earnings=row.next_earnings,
        upcoming_events=row.upcoming_events or [],
        analyst_activity=row.analyst_activity or {},
    )


def _sector_for(ticker: str) -> str | None:
    for entry in load_watchlist():
        if entry["ticker"].upper() == ticker.upper():
            return entry.get("sector")
    return None


# ───────────────────────────── Routes ─────────────────────────────── #


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/watchlist", response_model=list[schemas.WatchlistEntry])
def watchlist() -> list[dict[str, Any]]:
    return [{"ticker": e["ticker"], "sector": e.get("sector")} for e in load_watchlist()]


@app.get("/watchlist/snapshot", response_model=schemas.WatchlistSnapshot)
def watchlist_snapshot(
    on_date: Date | None = Query(default=None, alias="date"),
    session: Session = Depends(get_db),
) -> schemas.WatchlistSnapshot:
    target = on_date or Date.today()
    entries: list[schemas.TickerSnapshot] = []
    for cfg in load_watchlist():
        ticker = cfg["ticker"].upper()
        entries.append(
            schemas.TickerSnapshot(
                ticker=ticker,
                sector=cfg.get("sector"),
                sentiment=_sentiment_view(_latest(session, SentimentDaily, ticker, target)),
                quantitative=_quant_view(_latest(session, QuantDaily, ticker, target)),
                enrichment=_enrichment_view(_latest(session, EnrichmentDaily, ticker, target)),
            )
        )
    return schemas.WatchlistSnapshot(as_of=target, entries=entries)


@app.get("/tickers/{symbol}", response_model=schemas.TickerSnapshot)
def ticker_detail(
    symbol: str,
    on_date: Date | None = Query(default=None, alias="date"),
    session: Session = Depends(get_db),
) -> schemas.TickerSnapshot:
    ticker = symbol.upper()
    target = on_date or Date.today()
    sentiment = _sentiment_view(_latest(session, SentimentDaily, ticker, target))
    quant = _quant_view(_latest(session, QuantDaily, ticker, target))
    enrichment = _enrichment_view(_latest(session, EnrichmentDaily, ticker, target))
    if sentiment is None and quant is None and enrichment is None:
        raise HTTPException(status_code=404, detail=f"no data for {ticker} on or before {target}")
    return schemas.TickerSnapshot(
        ticker=ticker,
        sector=_sector_for(ticker),
        sentiment=sentiment,
        quantitative=quant,
        enrichment=enrichment,
    )


@app.get("/tickers/{symbol}/history")
def ticker_history(
    symbol: str,
    limit: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_db),
) -> dict[str, list[dict[str, Any]]]:
    ticker = symbol.upper()

    sent_rows = session.execute(
        select(SentimentDaily)
        .where(SentimentDaily.ticker == ticker)
        .order_by(SentimentDaily.as_of.desc())
        .limit(limit)
    ).scalars().all()

    quant_rows = session.execute(
        select(QuantDaily)
        .where(QuantDaily.ticker == ticker)
        .order_by(QuantDaily.as_of.desc())
        .limit(limit)
    ).scalars().all()

    return {
        "sentiment": [
            {
                "as_of": r.as_of.isoformat(),
                "score": r.sentiment_score,
                "direction": r.sentiment_direction,
            }
            for r in sent_rows
        ],
        "quant": [
            {
                "as_of": r.as_of.isoformat(),
                "close": r.close,
                "change_1d": r.change_1d,
                "rsi_14": r.rsi_14,
                "health_score": r.health_score,
            }
            for r in quant_rows
        ],
    }


# ───────────────────────────── Portfolio ──────────────────────────── #


def _fetch_current_prices(tickers: list[str]) -> dict[str, float]:
    """Best-effort live price snapshot. Empty dict if yfinance is unavailable
    or every lookup fails — callers fall back to last-known prices."""
    try:
        import yfinance as yf
    except ImportError:
        return {}
    prices: dict[str, float] = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).fast_info
            price = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
            if price is not None:
                prices[ticker] = float(price)
        except Exception:
            pass
    return prices


@app.get("/portfolio", response_model=schemas.PortfolioView)
def get_portfolio(session: Session = Depends(get_db)) -> schemas.PortfolioView:
    from src.storage.portfolio_repo import (
        get_or_create_portfolio,
        get_positions,
        portfolio_snapshot,
    )

    portfolio = get_or_create_portfolio(
        session,
        name="default",
        starting_equity=100_000.0,
        inception_date=Date.today(),
    )
    tickers = [p.ticker for p in get_positions(session, portfolio.id)]
    prices = _fetch_current_prices(tickers) if tickers else {}
    snap = portfolio_snapshot(session, portfolio, prices)
    return schemas.PortfolioView(
        name=snap["name"],
        inception_date=Date.fromisoformat(snap["inception_date"]),
        starting_equity=snap["starting_equity"],
        cash=snap["cash"],
        equity=snap["equity"],
        total_return_pct=snap["total_return_pct"],
        position_count=snap["position_count"],
        positions=[
            schemas.PositionView(
                ticker=p["ticker"],
                direction=p["direction"],
                shares=p["shares"],
                entry_price=p["entry_price"],
                current_price=p["current_price"],
                unrealized_pnl=p["unrealized_pnl"],
                entry_date=Date.fromisoformat(p["entry_date"]),
                reasoning=p.get("reasoning", "") or "",
            )
            for p in snap["positions"]
        ],
    )


@app.get("/portfolio/history", response_model=schemas.PortfolioHistory)
def get_portfolio_history(
    session: Session = Depends(get_db),
) -> schemas.PortfolioHistory:
    """Daily equity curve from inception, reconstructed by replaying trades
    against ``QuantDaily`` closes. Resize signs are solved against close-trade
    and current-position anchors."""
    from src.storage.models import QuantDaily, Trade
    from src.storage.portfolio_repo import get_or_create_portfolio, get_positions

    portfolio = get_or_create_portfolio(
        session, name="default", starting_equity=100_000.0, inception_date=Date.today()
    )

    trades = list(
        session.execute(
            select(Trade)
            .where(Trade.portfolio_id == portfolio.id)
            .order_by(Trade.trade_date, Trade.created_at)
        ).scalars().all()
    )
    if not trades:
        return schemas.PortfolioHistory(
            starting_equity=portfolio.starting_equity,
            inception_date=portfolio.inception_date,
            points=[],
        )

    current_shares = {p.ticker: p.shares for p in get_positions(session, portfolio.id)}

    # Resolve resize signs per ticker so we can replay trades exactly.
    from collections import defaultdict

    by_ticker: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        by_ticker[t.ticker].append(t)

    signed_delta: dict[int, float] = {}
    for ticker, t_list in by_ticker.items():
        running = 0.0
        pending: list[Trade] = []

        def solve(pending: list[Trade], start: float, target: float) -> None:
            n = len(pending)
            need = target - start
            for mask in range(1 << n):
                s = 0.0
                for i in range(n):
                    sign = 1.0 if (mask >> i) & 1 else -1.0
                    s += sign * pending[i].shares
                if abs(s - need) < 1e-3:
                    for i in range(n):
                        sign = 1.0 if (mask >> i) & 1 else -1.0
                        signed_delta[pending[i].id] = sign * pending[i].shares
                    return
            # Fallback: assume decreases (matches observed agent behavior).
            for p in pending:
                signed_delta[p.id] = -p.shares

        for t in t_list:
            if t.action == "open":
                if pending:
                    solve(pending, running, 0.0)
                    pending = []
                running = t.shares
            elif t.action == "close":
                solve(pending, running, t.shares)
                pending = []
                running = 0.0
            else:  # resize
                pending.append(t)
        if pending:
            solve(pending, running, current_shares.get(ticker, 0.0))

    # Build per-ticker price series indexed by date.
    tickers = list(by_ticker.keys())
    price_rows = session.execute(
        select(QuantDaily.ticker, QuantDaily.as_of, QuantDaily.close)
        .where(QuantDaily.ticker.in_(tickers))
        .order_by(QuantDaily.ticker, QuantDaily.as_of)
    ).all()
    prices: dict[str, list[tuple[Date, float]]] = defaultdict(list)
    for ticker, as_of, close in price_rows:
        if close is not None:
            prices[ticker].append((as_of, float(close)))

    def price_on_or_before(ticker: str, day: Date) -> float | None:
        series = prices.get(ticker, [])
        last: float | None = None
        for d, c in series:
            if d > day:
                break
            last = c
        return last

    # Determine date range: inception → latest QuantDaily date across held tickers.
    inception = portfolio.inception_date
    latest_price_date: Date | None = None
    for series in prices.values():
        if series:
            d = series[-1][0]
            if latest_price_date is None or d > latest_price_date:
                latest_price_date = d
    if latest_price_date is None:
        latest_price_date = inception
    end_date = max(latest_price_date, max(t.trade_date for t in trades))

    # Replay trades and snapshot equity each day.
    cash = portfolio.starting_equity
    positions: dict[str, tuple[str, float]] = {}  # ticker -> (direction, shares)
    trade_idx = 0
    points: list[schemas.EquityPoint] = []

    day = inception
    while day <= end_date:
        while trade_idx < len(trades) and trades[trade_idx].trade_date <= day:
            t = trades[trade_idx]
            if t.action == "open":
                if t.direction == "long":
                    cash -= t.shares * t.price
                else:
                    cash += t.shares * t.price
                positions[t.ticker] = (t.direction, t.shares)
            elif t.action == "close":
                if t.direction == "long":
                    cash += t.shares * t.price
                else:
                    cash -= t.shares * t.price
                positions.pop(t.ticker, None)
            else:  # resize
                delta = signed_delta.get(t.id, 0.0)
                cur = positions.get(t.ticker)
                if cur is not None:
                    direction, shares = cur
                    new_shares = max(shares + delta, 0.0)
                    if direction == "long":
                        cash -= delta * t.price
                    else:
                        cash += delta * t.price
                    if new_shares <= 1e-6:
                        positions.pop(t.ticker, None)
                    else:
                        positions[t.ticker] = (direction, new_shares)
            trade_idx += 1

        pos_value = 0.0
        for ticker, (direction, shares) in positions.items():
            close = price_on_or_before(ticker, day)
            if close is None:
                continue
            if direction == "long":
                pos_value += shares * close
            else:
                pos_value -= shares * close

        points.append(
            schemas.EquityPoint(
                as_of=day,
                equity=round(cash + pos_value, 2),
                cash=round(cash, 2),
                positions_value=round(pos_value, 2),
            )
        )
        day = day + timedelta(days=1)

    return schemas.PortfolioHistory(
        starting_equity=portfolio.starting_equity,
        inception_date=inception,
        points=points,
    )


@app.get("/trades", response_model=schemas.TradeHistory)
def get_trades_route(
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_db),
) -> schemas.TradeHistory:
    from src.storage.portfolio_repo import get_or_create_portfolio, get_trades

    portfolio = get_or_create_portfolio(
        session,
        name="default",
        starting_equity=100_000.0,
        inception_date=Date.today(),
    )
    trades = get_trades(session, portfolio.id, limit=limit)
    return schemas.TradeHistory(
        trades=[
            schemas.TradeView(
                ticker=t.ticker,
                action=t.action,
                direction=t.direction,
                shares=t.shares,
                price=t.price,
                trade_date=t.trade_date,
                reasoning=t.reasoning or "",
            )
            for t in trades
        ]
    )


@app.get("/briefing/{on_date}", response_model=schemas.BriefingView)
def get_briefing(on_date: Date, session: Session = Depends(get_db)) -> schemas.BriefingView:
    row = session.execute(
        select(BriefingDaily).where(BriefingDaily.as_of == on_date)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"no briefing stored for {on_date}")
    return schemas.BriefingView(
        as_of=row.as_of,
        tickers=row.tickers,
        markdown=row.briefing_markdown,
        model=row.model,
        created_at=row.created_at,
    )


# ────────────────────────── Pipeline triggers ─────────────────────── #


def _resolve_tickers(ticker: str | None) -> list[str]:
    if ticker:
        return [ticker.upper()]
    tickers = [t["ticker"].upper() for t in load_watchlist()]
    if not tickers:
        raise HTTPException(status_code=400, detail="watchlist is empty; pass ?ticker=SYM")
    return tickers


def _run_sentiment_job(tickers: list[str], on_date: Date) -> None:
    from src.engines.sentiment.aggregator import aggregate, apply_history
    from src.storage.sentiment_repo import get_score_near, upsert_sentiment_daily

    session = _session_factory()()
    try:
        for ticker in tickers:
            try:
                payload = aggregate(ticker, on_date)
                prior = get_score_near(
                    session, ticker, on_date - timedelta(days=7), window_days=7
                )
                apply_history(payload, prior)
                upsert_sentiment_daily(session, payload)
            except Exception as exc:
                logger.exception(f"api: sentiment {ticker} failed: {exc}")
    finally:
        session.close()


def _run_quant_job(tickers: list[str], on_date: Date) -> None:
    from src.engines.quantitative.aggregator import aggregate
    from src.storage.quant_repo import upsert_quant_daily

    watchlist = {t["ticker"].upper(): t.get("sector") for t in load_watchlist()}
    session = _session_factory()()
    try:
        for ticker in tickers:
            try:
                payload = aggregate(ticker, on_date, sector=watchlist.get(ticker))
                upsert_quant_daily(session, payload)
            except Exception as exc:
                logger.exception(f"api: quant {ticker} failed: {exc}")
    finally:
        session.close()


def _run_enrichment_job(tickers: list[str], on_date: Date) -> None:
    from src.engines.enrichment.aggregator import aggregate
    from src.storage.enrichment_repo import upsert_enrichment_daily

    session = _session_factory()()
    try:
        for ticker in tickers:
            try:
                payload = aggregate(ticker, on_date)
                upsert_enrichment_daily(session, payload)
            except Exception as exc:
                logger.exception(f"api: enrichment {ticker} failed: {exc}")
    finally:
        session.close()


def _run_meta_job(tickers: list[str], on_date: Date) -> None:
    from src.meta.llm_client import MODEL, generate_briefing
    from src.meta.payload_builder import build_payload

    session = _session_factory()()
    try:
        payload = build_payload(session, on_date, tickers=tickers)
        markdown = generate_briefing(payload)
        existing = session.execute(
            select(BriefingDaily).where(BriefingDaily.as_of == on_date)
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                BriefingDaily(
                    as_of=on_date,
                    tickers=tickers,
                    payload=payload,
                    briefing_markdown=markdown,
                    model=MODEL,
                )
            )
        else:
            existing.tickers = tickers
            existing.payload = payload
            existing.briefing_markdown = markdown
            existing.model = MODEL
        session.commit()
    finally:
        session.close()


_JOBS = {
    "sentiment": _run_sentiment_job,
    "quant": _run_quant_job,
    "enrichment": _run_enrichment_job,
}


@app.post("/pipeline/meta", response_model=schemas.PipelineRunResponse)
def run_meta(
    background: BackgroundTasks,
    ticker: str | None = None,
    on_date: Date | None = Query(default=None, alias="date"),
    wait: bool = False,
) -> schemas.PipelineRunResponse:
    tickers = _resolve_tickers(ticker)
    target = on_date or Date.today()

    if wait:
        _run_meta_job(tickers, target)
        return schemas.PipelineRunResponse(
            status="completed",
            command="meta",
            tickers=tickers,
            as_of=target,
        )

    background.add_task(_run_meta_job, tickers, target)
    return schemas.PipelineRunResponse(
        status="scheduled",
        command="meta",
        tickers=tickers,
        as_of=target,
        detail="running in background",
    )


@app.post("/pipeline/{engine}", response_model=schemas.PipelineRunResponse)
def run_pipeline(
    engine: str,
    background: BackgroundTasks,
    ticker: str | None = None,
    on_date: Date | None = Query(default=None, alias="date"),
    wait: bool = False,
) -> schemas.PipelineRunResponse:
    if engine not in _JOBS:
        raise HTTPException(status_code=404, detail=f"unknown engine: {engine}")
    tickers = _resolve_tickers(ticker)
    target = on_date or Date.today()
    job = _JOBS[engine]

    if wait:
        job(tickers, target)
        return schemas.PipelineRunResponse(
            status="completed",
            command=engine,
            tickers=tickers,
            as_of=target,
        )

    background.add_task(job, tickers, target)
    return schemas.PipelineRunResponse(
        status="scheduled",
        command=engine,
        tickers=tickers,
        as_of=target,
        detail="running in background",
    )


# ───────────────────────────── Entrypoint ─────────────────────────── #


def serve() -> None:
    """Console script entrypoint: ``sfe-api``."""
    import uvicorn

    host = os.environ.get("SFE_API_HOST", "127.0.0.1")
    port = int(os.environ.get("SFE_API_PORT", "8000"))
    uvicorn.run("src.api.main:app", host=host, port=port, reload=False)
