# SFE Portfolio Strategy

Operating framework for the Signal Fusion Engine portfolio. This document is authoritative — when in doubt, follow it. Update it explicitly when the strategy evolves; do not let practice drift from documentation.

Last updated: 2026-05-15.

## Mandate

- **Objective:** Hybrid — (1) test the agentic trading system end-to-end, (2) generate alpha vs benchmark.
- **Benchmark:** **QQQ** (Nasdaq-100). Watchlist composition is Mag7-heavy; QQQ is the honest comparison.
- **Evaluation horizon:** 3-month rolling. Long enough to separate signal from noise, short enough to iterate the system.
- **Max drawdown:** **-10% from peak equity** triggers forced de-grossing.
  - **Defensive trigger at -7% from peak:** mechanically reduce gross exposure before hitting the kill line.

## Deployment

- **Net long target when fully deployed: 70-85%.**
  - Below 70%: structural tracking-error drag vs QQQ. Avoid except in active de-gross.
  - Above 85%: aggressive — only when conviction is high across many names.
- **Cash drag is real.** Every percentage point of cash in a rising market is negative tracking error vs QQQ. Justify cash above 25% with a written reason (catalyst, drawdown, breadth deterioration).
- **No leverage.** Max gross long = 100% of equity.

## Position sizing

Three tiers — sizing must carry signal:

| Tier | Size | When to use |
|---|---|---|
| **High conviction** | 7% | Full signal convergence (sentiment + quant + enrichment all aligned), clear catalyst, strong technicals |
| **Medium** | 4% | Solid setup but one factor mixed or one risk overhang |
| **Starter / hedge** | 2% | Speculative, early thesis, or sector hedge |

- **Max single position: 10%** of equity (cap before resizing further).
- **Max single sector: 40%** of equity. Forces sector breadth before redeploying tech-heavy.
- **Min position: 1%** — anything smaller doesn't move the needle.

## Short book

**Long-only.** No single-name shorts. If hedging is required in a defensive regime, use index instruments (e.g. QQQ short) — not single names with unbounded loss and squeeze risk.

## Risk framework — kill rules

Three position-level stops. Whichever triggers first wins:

1. **Hard stop: -15% from entry price.** Mechanical. Removes hope-based holding.
2. **Trailing stop: -10% from peak.** Locks in gains on winners; binding once position is up ~5%+.
3. **Thesis-break stop:** if the original reasoning becomes false (e.g. earnings miss invalidates the breakout thesis), close regardless of P&L.

Portfolio-level: see Mandate (-7% defensive, -10% kill).

## Review cadence

- **Weekly review** (default Monday). Re-run signals, score open positions, check stops, prune broken theses, deploy fresh conviction.
- **Event-driven exceptions:** earnings, Fed days, CPI prints, individual stop hits — review those positions same-day.

## Watchlist composition (21 names, post-2026-05-15 expansion)

| Sector | Names |
|---|---|
| Technology | NVDA, MSFT, AAPL, AVGO, AMD, TSM |
| Communication services | GOOGL, META |
| Consumer discretionary | AMZN, TSLA |
| Financials | BRK-B, JPM, V, MA |
| Healthcare | LLY, UNH |
| Consumer staples | WMT, COST |
| Energy | XOM, CVX |
| Industrials | GE |

Sector concentration risk: Technology + Communication services + Consumer discretionary = 10 of 21 names. The 40% sector cap is the main guardrail against unintentional Mag7 overweight.

## Operating notes

- **Trade reasoning must cite specific signals.** Every open/resize/close should reference the sentiment, quant, or enrichment data point that drove it. This is what makes the experiment evaluable.
- **Document mandate violations.** If a position exceeds caps or net exposure breaks the band, write down why before doing it — or fix it.
- **NVDA earnings 2026-05-20 AMC** is the next major catalyst. Plan to redeploy aggressively post-print (5/21+) given current 16% net long is far below the 70% floor.
