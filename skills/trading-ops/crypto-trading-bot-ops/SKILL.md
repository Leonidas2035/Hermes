---
name: crypto-trading-bot-ops
description: >-
  Operate, diagnose, and analyze crypto trading-bot systems (HFT/scalp bots,
  orchestrators, exchange gateways) and build multi-source market-analysis
  pipelines. Covers ccxt async exchange access (BingX VST/testnet), QuestDB
  REST queries, Puppeteer+TradingView scraping, Firecrawl news sentiment, and
  safe daemon restarts. Trigger when the user runs or debugs a trading bot,
  asks to read exchange balance/positions/orders, wants a market analysis /
  trading plan, or mentions an orchestrator/supervisor role over a bot stack.
---

# Crypto Trading Bot Ops

You act as the **Orchestrator / Supervisor** of a trading system: you read
exchange state, decide strategy, and keep the bot stack alive. This skill is
the durable technique layer — project-specific state (symbols, keys, open
positions) lives in memory, not here.

## 1. Exchange access with ccxt (ASYNC)

**The #1 pitfall:** in asyncio code use `import ccxt.async_support as ccxt`,
NEVER sync `import ccxt`. With sync ccxt, `await ex.load_markets()` raises
`TypeError: object dict can't be used in 'await' expression` because sync
methods return dicts, not coroutines. The async module returns coroutines.

```python
import asyncio, os
from dotenv import load_dotenv; load_dotenv()
import ccxt.async_support as ccxt

async def probe():
    use_testnet = str(os.getenv("USE_TESTNET","1")).lower() in {"1","true","t"}
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY","")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET","")
    ex = ccxt.bingx({"apiKey":ak,"secret":sc,
                     "options":{"defaultType":"swap"},
                     "enableRateLimit":True,"timeout":30000})
    if use_testnet: ex.set_sandbox_mode(True)
    await ex.load_markets()
    sym = "XRP/USDT:USDT"          # swap format, NOT "XRP/USDT"
    fr = await ex.fetch_funding_rate(sym)     # fundingRate, markPrice, indexPrice
    oi = await ex.fetch_open_interest(sym)    # openInterestValue (USD)
    pos = await ex.fetch_positions(symbols=[sym])
    # cancel all open orders (does NOT close positions):
    await ex.cancel_all_orders(sym)
    # hedge-mode partial close of a SHORT (buy-to-cover):
    await ex.create_order(sym,"market","buy",qty,params={"positionSide":"SHORT"})
    ex.close()                     # SYNC in ccxt 4.x — do NOT `await ex.close()`
```

- Symbol for futures/swap: `BASE/USDT:USDT`. Spot: `BASE/USDT`.
- Read-only probes are safe: balance, positions, open orders never place trades.
- BingX rate-limits: repeated rejected orders (e.g. `101204 Insufficient margin`)
  escalate to `109429` ("over 20 error ... within 480000 ms") — back off.

## 2. QuestDB REST (time-series history)

HTTP REST on port 9000: `http://127.0.0.1:9000/exec?query=<urlencoded>`.
Response: `{"columns":[...],"dataset":[[...]],"count":N}` or `{"error":...}`.

**The #2 pitfall:** the designated timestamp column is named **`timestamp`**,
NOT `ts`. `ORDER BY ts` / `WHERE ts > ...` fails with `Invalid column: ts`.
Always use `timestamp`.

```sql
SELECT close, volume FROM klines_1m
WHERE symbol='XRPUSDT' AND timestamp > dateadd('m',-60,now())
ORDER BY timestamp DESC LIMIT 60
```

Key tables: `klines_1m(symbol,open,high,low,close,volume,trades_count,timestamp)`,
`microstructure_v1`, `market_features`, `trades`, `portfolio_state`,
`realized_trades`, `orderbook_snapshots`, `bot_telemetry`. Call via
`curl -s "http://127.0.0.1:9000/exec?query=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$Q")"`.

## 3. Puppeteer + TradingView (technical context)

Install without re-downloading chromium when system chrome exists:
`PUPPETEER_SKIP_DOWNLOAD=true npm install puppeteer` (Node + google-chrome prereq).

```js
const browser = await puppeteer.launch({ headless:'new',
  executablePath:'/usr/bin/google-chrome',
  args:['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'] });
const page = await browser.newPage();
await page.goto('https://www.tradingview.com/symbols/XRPUSDT/technicals/',
                { waitUntil:'networkidle2', timeout:45000 });
await new Promise(r=>setTimeout(r,3500));   // let widgets render
const tech = await page.evaluate(() => {
  const t = document.body.innerText;
  return { rating:(t.match(/(Strong Buy|Buy|Neutral|Sell|Strong Sell)/)||[])[1],
           oscillators:(t.match(/Oscillators\s+(Strong Buy|Buy|Neutral|Sell|Strong Sell)/)||[])[1],
           movingAverages:(t.match(/Moving Averages\s+(Strong Buy|Buy|Neutral|Sell|Strong Sell)/)||[])[1],
           levels:[...t.matchAll(/(Resistance|Support)\s*[:]?\s*([\d.]+)/g)].map(x=>`${x[1]} ${x[2]}`) };
});
await browser.close();
```

Parse rating → bias map: Strong Buy/Buy→LONG, Neutral→NEUTRAL, Sell/Strong Sell→SHORT.

## 4. Firecrawl (news sentiment)

`POST https://api.firecrawl.dev/v1/search`, header `Authorization: Bearer <key>`,
body `{"query":"XRP Ripple price news today","limit":3}`.
Response: `{"success":true,"data":[{url,title,description}]}`.

Free Tier: **1 request, limit 3** — minimize calls. Naive sentiment = count
bull/bear keywords in titles+descriptions. Pass the key via env
`FIRECRAWL_API_KEY` at runtime (see Pitfalls — don't write it into `.env` if the
user restricts that file).

## 5. Safe daemon restart (orchestrator)

- **Always restart via the project venv**, e.g. `.venv/bin/python3 QuantumEdge.py start`.
  Using system `python3` causes `ModuleNotFoundError: No module named 'xgboost'`
  (bot deps live in the venv) → component crashes on import.
- Orchestrators with a ZMQ guard cleanup kill processes holding critical ports
  at startup → **brief trading interruption, but exchange positions survive**
  (bots don't close positions on shutdown). Snapshot balance/positions via a
  read-only API call BEFORE restart and compare AFTER.
- **Monitoring false-positive pitfall:** if the orchestrator only tracks
  self-spawned procs (`self.processes`), an externally-started bot shows as
  `TERMINATED`. Fix: in the telemetry report, if a component's proc is dead,
  re-detect a live external instance via `psutil.process_iter` matching the
  cmdline signature (e.g. `ai_scalper_bot.run_bot`); report RUNNING + note.

## 6. User interaction pitfalls (HARD rules for this user)

- **No `rm`** — user denies destructive deletes. Use other means or ask.
- **No inline `python3 -c "..."`** one-liners — user denies them. Write a script
  file (`tools/_verify_x.py`) and run it instead.
- **No editing `.env` / credential stores directly** — user denies. Pass secrets
  via env at command launch: `FIRECRAWL_API_KEY=xxx python3 tools/analyze.py`.
- Prefer file-based, re-runnable scripts over hand-typed one-liners.

## 7. Verification discipline

For ad-hoc ops scripts there is usually no `pytest` suite and they need network.
Verify with: (a) `ast.parse` (py) / `node --check` (js) for syntax; (b) a real
run that hits the exchange/db and returns data. State clearly when `pytest` is
not applicable (no suite / network-bound) rather than claiming full verification.

## References
- `references/exchange-ccxt.md` — ccxt async + BingX VST recipes (funding, OI, hedge close).
- `references/questdb-rest.md` — QuestDB REST querying, column names, tables.
- `references/puppeteer-tradingview.md` — headless TradingView scraping recipe.
- `references/firecrawl-search.md` — Firecrawl search API + sentiment.
- `references/daemon-restart.md` — safe venv restart + monitoring re-detection.
