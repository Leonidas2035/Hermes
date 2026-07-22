---
name: crypto-market-analysis
description: >-
  Pull LIVE crypto market + exchange data and produce a structured trading-analysis
  plan. Covers three reusable data sources: ccxt (BingX/testnet VST), headless
  TradingView scraping via Puppeteer with system Chrome, and QuestDB REST queries.
  Use when the user wants market analysis, exchange balance/positions/orders
  inspection, a supervisor/orchestrator-style trading plan for a crypto pair, or
  anything involving reading crypto exchange state. Read-only by default; never
  place orders without explicit sanction.
---

# Crypto Market Analysis (data access toolkit)

## When to use
- User asks for market analysis of a crypto pair (e.g. XRP/USDT) or a trading plan.
- User wants to inspect exchange balance, open positions, or open orders.
- User wants you to act as "Supervisor/Orchestrator" of a trading system.
- Combine multiple sources into ONE structured plan; do not trade on a single signal.

## Three data sources (combine them)
1. **Exchange derivatives + account** — `ccxt` (BingX). Funding rate, Open Interest,
   balance, positions, orders. See `references/bingx_ccxt.md`.
2. **External technical context** — TradingView scraped with Puppeteer + system Chrome.
   Technical rating, oscillators, moving averages, levels. See `references/tradingview_puppeteer.md`.
3. **Local history** — QuestDB REST (port 9000). klines, microstructure. See
   `references/questdb_rest.md`. May be empty for a symbol — fall back to 1+2.

## Build an analysis (recipe)
1. Parse the symbol from env (`MARKET_DATA_SYMBOLS`, first of comma list).
2. Run TradingView parser (Node subprocess) → technical rating.
3. Fetch funding rate + open interest via ccxt (testnet-safe).
4. (Optional) query QuestDB for recent klines of that symbol.
5. Emit a structured plan: context → bias → tactical plan. Mark risk-management
   status explicitly (user may run analysis-driven control instead of hard stops).
6. NEVER place orders unless the user sanctions a specific action. Read-only probes
   are safe on testnet.

## Pitfalls (cost real debug cycles — avoid)
- **ccxt async gotcha**: `import ccxt.async_support as ccxt`, NOT `import ccxt`.
  Using sync `ccxt` makes `await ex.fetch_balance()` raise
  "object dict can't be used in 'await' expression". The methods return coroutines
  only under `async_support`.
- **ccxt.close() is sync** in ccxt 4.5 — do NOT `await ex.close()`; just `ex.close()`
  in a try/except. (Awaiting it raises "object NoneType can't be used in 'await'".)
- **BingX testnet (VST)**: call `set_sandbox_mode(True)`; balance lives under key
  `"VST"` (not `"USDT"`); swap symbol format is `XRP/USDT:USDT`; funding rate and
  open interest DO work on testnet.
- **Puppeteer**: install with `PUPPETEER_SKIP_DOWNLOAD=true npm install puppeteer`
  and launch with `executablePath: '/usr/bin/google-chrome'` + `--no-sandbox`
  (system Chrome already present — avoids downloading a second Chromium). Use
  `headless: 'new'`. Wait `networkidle2` THEN sleep 3-4s before reading widgets.
- **QuestDB**: REST is `http://127.0.0.1:9000/exec?query=<URL-encoded SQL>`
  (port 9000, not 8812 which is pgwire). ALWAYS `SHOW TABLES` first — a symbol may
  not be stored yet (QuantumEdge klines_1m had only BTCUSDT; XRPUSDT was absent).
- **Verification of ad-hoc scripts**: these tools/*.py and tv_analyzer/*.js are NOT
  covered by `pytest` (they need network/browser). Verify with `node --check` (JS)
  and `ast.parse` (Python) plus a real live run. Do NOT claim verified without a
  real run. Avoid `rm` and `python3 -c` one-liners in terminal — the user's
  environment gates them; prefer writing a small file and running it.
- **Orchestrator false-reports**: a process can be alive and trading while the
  orchestrator's status shows TERMINATED (heartbeat/sync gap). Check `ps aux` and
  the live log + actual exchange state before concluding a bot is down.

## Notes
- This skill is tooling-agnostic about any specific trading bot; it is about
  *reading the market and exchange* to inform a plan. Keep bot-specific logic
  (strategy, execution) out of here.
