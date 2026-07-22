---
name: crypto-trading-system-ops
description: >-
  Operate, analyze, and supervise a crypto trading bot/system. Covers BingX
  (ccxt, testnet/VST), QuestDB HTTP queries, TradingView scraping via Puppeteer,
  read-only exchange probes, sanctioned order actions, and orchestrator
  process-monitoring pitfalls. Use when the user asks to check a trading
  account, pull balance/positions/open-orders, analyze a pair, or fix a bot
  that the orchestrator falsely reports as down.
category: trading
---

# Crypto Trading System Ops

Class-level playbook for running, diagnosing, and supervising a crypto trading
stack (bots + orchestrator + TSDB + market data). Built from real QuantumEdge
work but written so the techniques apply to any ccxt/BingX/QuestDB/Puppeteer setup.

## When to use
- User asks to connect to the exchange, read balance / open positions / open orders.
- User wants a market analysis / trading plan for a pair (e.g. XRP/USDT).
- A bot is "not trading" or the orchestrator reports a component TERMINATED while it is clearly alive.
- User mentions BingX, ccxt, QuestDB, TradingView, market-data hub, ZMQ.

## Golden rules (user preferences embedded here)
- **Analysis over hard stops.** This user explicitly prefers quality market
  analysis + a Supervisor trading plan INSTEAD of an auto risk-management kill
  switch. Do not re-enable `risk_management_enabled` or add stop-loss automation
  unless they ask. Protect via analysis, not auto-blocks.
- **Ukrainian by default** for reports to this user.
- **Never edit credential stores directly** (e.g. `~/.hermes/.env`). If a key
  must be wired in, pass it via env at launch (`KEY=... python script.py`) or
  ask the user to edit the file. The user blocks direct edits / destructive cmds.
- **Use file-based verify scripts, not `python3 -c` one-liners or `rm`** — the
  user blocks those. Write a small `tools/_verify_x.py` and run it.
- **No order without sanction.** Read-only probes are free. Cancel / close /
  place requires explicit user go-ahead, and you MUST verify after (re-pull
  balance/positions/orders).
- **testnet/VST is safe to act on** when `USE_TESTNET=true`; real mainnet needs
  explicit confirmation + the real keys.

## Core techniques

### 1. ccxt in async context — IMPORT GOTCHA
Always `import ccxt.async_support as ccxt` inside asyncio code (bots, probes).
Using the sync `import ccxt` makes `await ex.load_markets()` raise
`object dict can't be used in 'await' expression` (you await a dict).
Verify once with a tiny diag if unsure:
```python
import asyncio, ccxt.async_support as ccxt
async def t():
    ex = ccxt.bingx({'apiKey':'x','secret':'y','options':{'defaultType':'swap'}})
    ex.set_sandbox_mode(True)
    m = await ex.load_markets()   # must be a coroutine
    print(type(m), len(m))
asyncio.run(t())
```

### 2. BingX testnet/VST read-only probe
```python
import asyncio, os, ccxt.async_support as ccxt
from dotenv import load_dotenv; load_dotenv()
sym = os.getenv("MARKET_DATA_SYMBOLS","XRPUSDT").split(",")[0]
BASE = sym.replace("USDT",""); CCXT = f"{BASE}/USDT:USDT"
async def main():
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY","")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET","")
    ex = ccxt.bingx({"apiKey":ak,"secret":sc,"options":{"defaultType":"swap"},"enableRateLimit":True})
    if str(os.getenv("USE_TESTNET","1")).lower() in {"1","true","t"}:
        ex.set_sandbox_mode(True)
    bal = await ex.fetch_balance()            # swap account; VST key in testnet
    pos = await ex.fetch_positions(symbols=[CCXT])
    ordr = await ex.fetch_open_orders(symbol=CCXT)
    # balance quote asset is "VST" on VST, "USDT" on mainnet
    await ex.close()
```
Notes: symbol format `BASE/USDT:USDT` (swap/perp). To partially CLOSE a hedge
short, `create_order(symbol, "market", "buy", qty, params={"positionSide":"SHORT"})`.
`cancel_all_orders(symbol=...)` removes resting limits WITHOUT touching positions.

### 3. QuestDB HTTP REST
`curl "http://127.0.0.1:9000/exec?query=URLENCODED_SQL"`.
- The designated timestamp column is named **`timestamp`**, NOT `ts` — `ORDER BY ts` fails with `Invalid column: ts`.
- klines table is `klines_1m` (columns: symbol, open, high, low, close, volume, trades_count, timestamp).
- Time filter: `WHERE symbol='XRPUSDT' AND timestamp > dateadd('m', -60, now()) ORDER BY timestamp DESC LIMIT 60`.
- `SHOW TABLES` lists tables; a `SELECT symbol FROM <table> LIMIT 5` may return only one symbol even if many exist (rows aren't grouped) — don't conclude "no history" from a small LIMIT; use `count()`.

### 4. TradingView scraping via Puppeteer (system chrome)
Node + `puppeteer` with `executablePath: '/usr/bin/google-chrome'`, `headless:'new'`,
args `['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage']`.
Skip the chromium download: `PUPPETEER_SKIP_DOWNLOAD=true npm install puppeteer`.
Parse the technicals page `https://www.tradingview.com/symbols/<SYM>/technicals/`
for rating (Strong Buy/Buy/Neutral/Sell/Strong Sell), oscillators, moving averages.
The summary page often mixes words — prefer the `/technicals/` subpage.
See `references/quantumedge-context.md` for the working TradingView parse
snippet and the QuantumEdge architecture/action-flow notes.

### 5. Orchestrator false TERMINATED (process monitoring)
If an orchestrator reports a component TERMINATED but the process is clearly
alive, the cause is usually: the monitor only checks processes IT spawned
(`self.processes`), missing externally-started ones. Fix: add a psutil fallback
that finds the live process by **cmdline signature** (e.g. `ai_scalper_bot` +
`run_bot`) and reports RUNNING. Always iterate the known component names and
skip those already in the spawned dict.

## Verification of this class of code
These ops scripts need network / headless browser / exchange — `pytest` is NOT
applicable (no offline unit tests, and `QuantumEdge.py` binds a ZMQ port in
`__init__`). Verify with: `ast.parse(open(f).read())` for syntax + a REAL run
that returns live data (balance/positions/orders/TV rating). State this blocker
explicitly instead of claiming pytest-passed.

## Pitfalls
- Sync ccxt import in async → "object dict can't be used in 'await'".
- QuestDB `ts` vs `timestamp` column name.
- Concluding "no QuestDB history" from a small `LIMIT` query.
- Treating `free=0` balance as a bug — it means margin is fully locked (drawdown/
  over-exposure); exchange blocks new orders. Cancel stale limits + partially
  close the oversized side to free margin (user-sanctioned).
- Editing `.env` directly — blocked; pass key via env at launch.
