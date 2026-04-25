# Signal Fusion Engine (SFE)

Fuses sentiment, quantitative, and enrichment signals through a Claude-powered meta-layer to produce pre-earnings context briefs and daily market briefings. One command, 60 seconds, structured output with a directional read.

```
$ uv run sfe run-earnings-brief --ticker NVDA

## Earnings Brief — NVDA — 2026-05-28

### Setup
NVIDIA reports Q1 FY2027 on May 28. The stock is trading at $950, up 12% over
the past 20 days. Sentiment is positive (0.52) with bullish insider activity...

### Consensus
Street expects EPS of $0.88 (32 analysts). Revenue estimate: $43.2B...
```

## Quick start

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), a free [Finnhub API key](https://finnhub.io/register), and an [Anthropic API key](https://console.anthropic.com/).

```bash
# 1. Clone and install
git clone https://github.com/samwise-k/signal-fusion-engine.git
cd signal-fusion-engine
uv sync
uv sync --group quant    # yfinance (options-implied move)
uv sync --group llm      # anthropic SDK (Claude briefings)

# 2. Configure API keys
cp .env.example .env
# Edit .env and set at minimum:
#   FINNHUB_KEY=your_finnhub_key
#   ANTHROPIC_API_KEY=your_anthropic_key
#   SEC_EDGAR_USER_AGENT=sfe/0.1 (your-email@example.com)

# 3. Check what's reporting soon
uv run sfe earnings-calendar

# 4. Generate an earnings brief
uv run sfe run-earnings-brief --ticker MSFT

# 5. For a richer brief, run the signal engines first
uv run sfe run-sentiment --ticker MSFT
uv run sfe run-quant --ticker MSFT
uv run sfe run-enrichment --ticker MSFT
uv run sfe run-earnings-brief --ticker MSFT
```

## What it does

SFE pulls data from multiple free sources, scores it, and sends a structured payload to Claude for synthesis:

```
Finnhub (news, insider trades, analyst revisions, earnings calendar, consensus)
EDGAR (SEC filings: 8-K, 10-K, 10-Q)                                          → Sentiment
finlight (financial news)                                                         + Quant
yfinance (OHLCV, technicals, options chains)                                      + Enrichment
                                                                                     ↓
                                                                              Claude meta-layer
                                                                                     ↓
                                                                            Structured briefing
```

**Earnings briefs** are the primary workflow: per-ticker, pre-earnings context with consensus estimates, 8-quarter beat/miss history, options-implied move, multi-tier signal analysis, and a directional read with conviction tag.

**Daily briefings** cover the full watchlist: cross-ticker signal convergence/divergence ranking with conviction tags.

## CLI commands

| Command | What it does |
|---------|-------------|
| `sfe earnings-calendar` | Show watchlist tickers reporting in the next 14 days |
| `sfe run-earnings-brief --ticker SYM` | Generate a per-ticker pre-earnings context brief |
| `sfe log-outcome --ticker SYM ...` | Record prediction vs actual outcome after earnings |
| `sfe run-sentiment [--ticker SYM]` | Run sentiment engine (Finnhub + EDGAR + finlight) |
| `sfe run-quant [--ticker SYM]` | Run quantitative engine (technicals, sector-relative) |
| `sfe run-enrichment [--ticker SYM]` | Run enrichment engine (insider, analyst, calendar) |
| `sfe run-meta [--ticker SYM]` | Generate a daily watchlist briefing via Claude |

All commands accept `--date YYYY-MM-DD` (defaults to today). Commands without `--ticker` run against the full watchlist in `config/watchlist.yaml`.

### Tracking outcomes

After a company reports, log how the brief's call did:

```bash
uv run sfe log-outcome \
  --ticker MSFT \
  --earnings-date 2026-04-29 \
  --predicted-dir bullish \
  --conviction 0.7 \
  --actual-eps-surp 4.1 \
  --stock-move-1d 3.2 \
  --outcome correct
```

Next time you run `run-earnings-brief` for that ticker, Claude sees the prior call and can reference the track record.

## API keys

| Key | Required for | Free tier |
|-----|-------------|-----------|
| `FINNHUB_KEY` | Sentiment, enrichment, earnings | Yes (60 calls/min) |
| `ANTHROPIC_API_KEY` | `run-meta`, `run-earnings-brief` | Pay-per-use |
| `SEC_EDGAR_USER_AGENT` | SEC filing fetches | Keyless (requires email in UA) |
| `FINLIGHT_KEY` | Additional news sentiment | Yes |

Set these in `.env` (gitignored). Only `FINNHUB_KEY` and `ANTHROPIC_API_KEY` are needed to run earnings briefs.

## Setup (detailed)

```bash
# Core only (sentiment + storage + CLI)
uv sync

# Optional dependency groups, installed on demand:
uv sync --group sentiment-ml   # transformers + torch (FinBERT scorer)
uv sync --group quant          # scikit-learn, xgboost, yfinance
uv sync --group llm            # anthropic SDK (Claude briefings)
uv sync --group api            # fastapi + uvicorn (HTTP layer)
```

### Watchlist

Edit `config/watchlist.yaml` to set your tickers:

```yaml
tickers:
  - ticker: NVDA
    sector: technology
  - ticker: MSFT
    sector: technology
  - ticker: JPM
    sector: financials
```

The `sector` field maps to SPDR ETFs for sector-relative returns (XLK, XLF, etc.).

### Frontend (optional)

```bash
cd frontend
npm install
npm run dev       # Vite dev server on :5173, proxies /api to 127.0.0.1:8000
# Backend must be running in another shell: uv run sfe-api
```

### Tests

```bash
uv run pytest               # 137 tests, ~4 seconds
```

## Layout

```
config/      # watchlist.yaml, sources.yaml
src/
  engines/
    sentiment/     # news, social, SEC → score → aggregate
    quantitative/  # OHLCV, technicals, sector-relative, health score
    enrichment/    # insider trades, analyst revisions, earnings calendar
    earnings/      # consensus, beat/miss, options-implied, earnings payload
  meta/            # payload builder, Claude client, formatter, prompt templates
  api/             # FastAPI app, Pydantic schemas, `sfe-api` entry
  delivery/        # email, Slack (not yet wired)
  storage/         # SQLAlchemy models, repos, session
  pipeline.py      # CLI entry point (all `sfe` commands)
frontend/    # React + Vite + TS dashboard
tests/       # 137 tests
data/        # raw/ + processed/ (gitignored)
```

## Disclaimer

This is a personal research tool, not a financial product. It does not provide investment advice. The author may hold positions in securities discussed. Past framework outputs do not predict future results. See the auto-appended disclaimer on every earnings brief for the full text.

## Known limitations

- **EDGAR signal quality (Phase 1).** 8-K item codes are expanded to SEC
  English titles (`sec_item_codes.py`) and primary-document bodies are
  fetched, HTML-stripped, and truncated to 50k chars before scoring
  (`sec_fetcher.fetch_filing_body`). Bodies are cached in-process by URL.
  Remaining weakness: the entire front matter of a 10-K/10-Q is scored
  uniformly — risk-factor boilerplate dilutes signal from MD&A. Targeting
  Item 7 (MD&A) specifically would improve this but requires section-anchor
  parsing that varies across filings. Deferred until scores show it matters.

## Phase status

- [x] Phase 0 — skeleton
- [x] Phase 1 — sentiment engine MVP
- [ ] Phase 2 — quantitative engine MVP _(starting slice live; GBT deferred to Phase 5)_
- [ ] Phase 3 — enrichment signals _(starting slice live; short interest / congressional / options / macro deferred to Phase 5)_
- [ ] Phase 4 — meta-synthesis layer _(starting slice live; delivery deferred to Phase 5)_
- [ ] Phase 5 — polish, dashboard, backtesting, delivery, GBT, deferred enrichment _(FastAPI + React dashboard live; backtesting, delivery, GBT, deferred enrichment still pending)_

## Improvement backlog (2026-04-19 review)

Captured from a whole-project review; not yet scheduled. Use this as the
menu when picking what to zoom in on next. Ordered within each engine by
rough signal-quality impact.

### Sentiment
- Promote FinBERT to default scorer; retire TextBlob after spot-checking a week of rows. Single biggest quality lever.
- Split `sec_filings` weight into `sec_8k` vs `sec_periodic` (8-Ks carry more event signal than 10-K/10-Q front matter). Cheaper than MD&A section parsing.
- Dedup Finnhub + finlight articles before `weighted_rollup` (hash on normalized title + publisher) so wire-service reprints don't double-count.
- Either populate `key_topics` (top TF-IDF tokens across the day's headlines) or remove the field from the schema and prompt.

### Quantitative
- Replace binary-vote `predict_health` with a z-score composite per indicator so magnitude/regime matter (no ML required).
- Pin the GBT label definition now (forward 5d return vs sector? Sharpe over N days?) so accumulated scorecards are trainable later.
- Add SPY-relative return alongside sector-relative; divergence between the two is itself a signal.
- Add a volatility feature (ATR or realized vol) so the meta-layer can weight a 5% move by the name's typical range.

### Enrichment
- Insider summary: weight by net dollar value and insider role (CEO/CFO vs 10%-holder), not just P/S code counts.
- Analyst revisions: weight the latest revision heavier than MoM aggregate; use firm name if exposed.
- Add a post-earnings-drift flag ("earnings N days ago, stock ±X%") to the payload.
- Pull FRED FOMC/CPI macro calendar forward from the deferred list — free, low-effort, meta-layer currently has no macro context.

### Meta layer
- Feed yesterday's briefing (or a tier-change diff) into the prompt so Claude can reference prior calls instead of cold-starting each morning. `BriefingDaily` already persists — cheap add.
- Add a `briefing_outcomes` table for manual post-hoc right/wrong marking. Unblocks threshold tuning and eventually provides GBT labels.
- Broad-market context block (SPY/QQQ/VIX + upcoming FOMC/CPI) — already on the Phase 5 list; worth prioritizing because high-conviction calls on risk-off days should be downgraded.

### Cross-cutting
- `config/sources.yaml` weights are currently guesses and are the most important tuning knob. Backtest weight variants against forward returns once a few weeks of rows accumulate.
- Add a response cache layer on Finnhub fetchers keyed by (ticker, date), mirroring the in-process EDGAR body cache. Helps tests too.

## Task tracker

### Phase 0 — skeleton
- [x] `pyproject.toml` + `uv` dependency groups (core / dev / sentiment-ml / quant / llm)
- [x] CLI entry point (`sfe` console script, argparse subcommands)
- [x] SQLAlchemy engine + session factory (`src/storage/db.py`)
- [x] `.env.example` aligned to the four chosen Phase-1 sources
- [x] `config/sources.yaml` weights for `sec_filings`, `news_finnhub`, `news_finlight`, `social_reddit`
- [x] `src/config.py` YAML loaders (`load_sentiment_weights`, `load_watchlist`)
- [x] `config/watchlist.yaml` populated (10–15 tickers across 2–3 sectors)

### Phase 1 — sentiment engine MVP
**Schema & scoring**
- [x] `SentimentDaily` schema with `(ticker, as_of)` uniqueness + JSON columns
- [x] TextBlob scorer (`score_text`), neutral on empty input
- [x] `weighted_rollup` pure aggregation (per-source averaging → weighted blend; drops unconfigured sources)

**Fetchers**
- [x] Finnhub `news_fetcher` (`/company-news`, configurable lookback, env-keyed, raises clearly without `FINNHUB_KEY`)
- [x] SEC EDGAR `sec_fetcher` (CIK lookup via `company_tickers.json`, 10-K/10-Q/8-K filter, 30-day default window, requires `SEC_EDGAR_USER_AGENT`)
- [x] finlight news fetcher (`POST /v2/articles`, `X-API-KEY` header, TextBlob-scored; native `sentiment` field left as future upgrade)
- [ ] ~~Reddit PRAW fetcher~~ _(deprioritized: TextBlob mangles Reddit finance-speak; revisit only after FinBERT upgrade, or build as a standalone project that pipes into SFE)_

**Orchestration & persistence**
- [x] `aggregate(ticker, on_date)` — combines Finnhub + EDGAR with per-source failure isolation
- [x] `upsert_sentiment_daily` repo helper (insert-or-update on `(ticker, as_of)`)
- [x] CLI: `run-sentiment --ticker SYM --date YYYY-MM-DD` creates DB on demand and persists rows
- [x] Test suite (52 passing): scorer, rollup, item-code expansion, HTML-to-text + body-fetch cache, both fetchers, end-to-end aggregate (incl. failure isolation + body-feed verification), upsert

**Open work**
- [x] EDGAR signal quality: 8-K item-code → English map wired into aggregator
- [x] EDGAR signal quality: filing-body fetch + HTML strip + 50k truncation + per-URL cache
- [ ] EDGAR signal quality: MD&A section targeting for 10-K/10-Q (see Known limitations)
- [x] `sentiment_direction` + `sentiment_delta_7d` computed from history (pipeline anchors against the closest prior row within a 7-day window)
- [x] Watchlist seed + multi-ticker run path exercised live
- [x] FinBERT upgrade path (`sentiment-ml` dep group) — `SENTIMENT_SCORER=finbert` switches scorer; TextBlob remains default

### Phase 2 — quantitative engine MVP
- [x] yfinance OHLCV fetcher (`price_fetcher.fetch_ohlcv`, 300-day default lookback)
- [x] Technicals (`compute_indicators`): RSI-14, SMA-50/200 position, MACD signal, 1/5/20-day returns, volume-vs-20d-avg
- [x] Sector-relative 5-day return vs SPDR ETF (mapping from `watchlist.yaml` sector field → XLK/XLC/...); degrades to null on ETF fetch failure
- [x] Rule-based `predict_health` (strong / neutral / weak) — placeholder until GBT trains
- [x] `QuantDaily` schema with `(ticker, as_of)` uniqueness + `upsert_quant_daily` repo helper
- [x] CLI: `run-quant --ticker SYM --date YYYY-MM-DD` (watchlist run when `--ticker` omitted)
- [x] Test suite: technicals (empty/short/rising/falling/volume/sort), rule-based model, aggregator (happy + degraded + no-data + unknown-sector), repo upsert
- [ ] GBT technical-health model (xgboost) — train once enough daily scorecards accumulate

### Phase 3 — enrichment signals
- [x] Insider trades via Finnhub `/stock/insider-transactions` — P/S codes drive net sentiment (bullish/bearish/neutral), other codes listed but not counted
- [x] Earnings calendar via Finnhub `/calendar/earnings` — soonest upcoming + `days_until`
- [x] Analyst revisions via Finnhub `/stock/recommendation` — month-over-month bull-score delta → upgrade/downgrade/stable
- [x] `EnrichmentDaily` schema + `upsert_enrichment_daily` repo helper
- [x] CLI: `run-enrichment --ticker SYM --date YYYY-MM-DD` (watchlist run when `--ticker` omitted)
- [x] Test suite: per-source summarizers (insider/earnings/analyst) + aggregator (happy / full failure / partial failure) + repo upsert
- [ ] Short interest (FINRA bimonthly file) — Phase 5
- [ ] Congressional trades (Quiver Quant free tier, 45-day lag) — Phase 5
- [ ] Options flow (Unusual Whales, paid) — Phase 5
- [ ] FOMC/CPI macro calendar (hardcoded near-term or FRED) — Phase 5

### Phase 4 — meta-synthesis layer
- [x] `payload_builder.build_payload` — pulls latest `SentimentDaily` + `QuantDaily` + `EnrichmentDaily` per watchlist ticker (rows with `as_of <= on_date`; null when missing)
- [x] `prompts/daily_briefing.txt` — static system prompt (per-tier signal thresholds, convergence/divergence rules, `[high|medium|low]` conviction tags, thin-data escape hatch, output markdown structure), cached via `cache_control: ephemeral`
- [x] `llm_client.generate_briefing` — Anthropic SDK, `claude-opus-4-7`, adaptive thinking, streamed via `messages.stream` + `get_final_message`, `max_tokens=16000`
- [x] `formatter.format_briefing` — strip + prepend header if model omitted it
- [x] CLI: `run-meta --ticker SYM --date YYYY-MM-DD` (watchlist run when `--ticker` omitted); prints briefing to stdout
- [x] Test suite (11 meta tests): payload builder (missing data, all-three-present, latest-prior, future excluded) + formatter + smoke imports
- [ ] Email/Slack delivery — Phase 5
- [ ] Broad market context block (SPY/QQQ/VIX, upcoming FOMC/CPI) — Phase 5

### Earnings engine
- [x] Consensus estimates fetcher (Finnhub `/stock/metric` for forward EPS/revenue/analyst count)
- [x] Beat/miss history fetcher (Finnhub `/stock/earnings`, last 8 quarters, surprise % with div-by-zero guard)
- [x] Options-implied move fetcher (yfinance ATM straddle, graceful degradation when chain data unavailable)
- [x] Earnings payload builder (merges new fetchers + existing engine DB rows per ticker)
- [x] Earnings-specific prompt template (`prompts/earnings_briefing.txt`, 9-section structure)
- [x] `EarningsBriefOutcome` schema + repo (upsert on `(ticker, earnings_date)`, tracks predictions vs actuals)
- [x] CLI: `run-earnings-brief --ticker SYM` (auto-detects earnings date from Finnhub, `--earnings-date` override)
- [x] CLI: `log-outcome --ticker SYM --earnings-date ... --predicted-dir bullish --conviction 0.7 [--actual-eps-surp ...] [--outcome correct]`
- [x] CLI: `earnings-calendar` (watchlist tickers reporting in next 14 days, with consensus EPS)
- [x] Auto-disclaimer appended to all earnings briefs
- [x] Claude API error handling in `run-meta` and `run-earnings-brief`
- [x] DRY refactor: `_bootstrap_db()`, `_parse_date()`, `_resolve_tickers()` shared helpers in pipeline.py
- [x] Test suite: 28 earnings tests (beat/miss summarize + edge cases, consensus fetch, options helpers, payload builder with mocked fetchers, outcome repo CRUD + upsert + uniqueness, disclaimer formatting)
- [ ] Insider/analyst windowing (30-day pre-print lookback) — existing data acceptable for week 1
- [ ] Historical comparison anchor in briefs — needs prior outcome data first

### Phase 5 — polish
- [x] FastAPI HTTP layer (`sfe-api` console script): `/health`, `/watchlist`, `/watchlist/snapshot`, `/tickers/{symbol}`, `/tickers/{symbol}/history`, `/briefing/{date}`, `POST /pipeline/{sentiment|quant|enrichment|meta}` (background tasks by default, `?wait=true` for sync); CORS locked to `http://localhost:5173` via `SFE_CORS_ORIGINS`
- [x] `BriefingDaily` table + cache: `run-meta` via API persists Claude output so `GET /briefing/{date}` serves without re-hitting the LLM
- [x] Test suite: 9 API tests (TestClient + in-memory SQLite via StaticPool); total suite now 137 passing
- [x] React + Vite + TypeScript dashboard under `frontend/` (watchlist table, ticker drill-down, briefing view with generate button; talks to `sfe-api` via Vite `/api` proxy to `127.0.0.1:8000`)
- [ ] Backtesting framework, GBT model, deferred enrichment sources (short interest / congressional / options / macro), email/Slack delivery
