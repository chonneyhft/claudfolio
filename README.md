# Signal Fusion Engine (SFE)

Personal trading decision-support tool. Fuses sentiment, quantitative, and enrichment signals through a Claude-powered meta-layer into a daily pre-market briefing.

**Status:** Phase 0 — skeleton scaffolded. No engines implemented yet.

Source of truth for architecture: `~/Documents/Obsidian Vault/Obsidian Vault/Project Ideas/Signal-Fusion-Tool.md`.

## Setup

```bash
# 1. Install dependencies (core only)
uv sync

# 2. Copy env template and fill in keys as you wire up each source
cp .env.example .env

# 3. Populate the watchlist
$EDITOR config/watchlist.yaml

# 4. Run the CLI
uv run sfe --help
```

### Optional dependency groups

Installed on demand to keep the base environment lean:

```bash
uv sync --group sentiment-ml   # transformers + torch (FinBERT)
uv sync --group quant          # scikit-learn, xgboost, yfinance
uv sync --group llm            # anthropic SDK (meta-layer)
```

## Layout

```
config/      # watchlist.yaml, sources.yaml
src/
  engines/
    sentiment/     # Phase 1 — news, social, SEC → score → aggregate
    quantitative/  # Phase 2 — OHLCV, technicals, ML health score
    enrichment/    # Phase 3 — insider, options, short, events, ...
  meta/            # Phase 4 — payload builder, Claude client, formatter
  delivery/        # email, Slack, Streamlit
  storage/         # SQLAlchemy models + session
  pipeline.py      # CLI entry point
tests/
data/        # raw/ + processed/ (gitignored)
notebooks/
```

## Phase status

- [x] Phase 0 — skeleton
- [ ] Phase 1 — sentiment engine MVP
- [ ] Phase 2 — quantitative engine MVP
- [ ] Phase 3 — enrichment signals
- [ ] Phase 4 — meta-synthesis layer
- [ ] Phase 5 — polish, dashboard, backtesting
