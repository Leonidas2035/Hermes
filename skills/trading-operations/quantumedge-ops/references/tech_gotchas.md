# QuantumEdge — Technical Gotchas & Known-Good Snippets

Condensed from the 2026-07-15 ops session. Use as a recipe bank, not a mirror.

## 1. Read-only account probe (BingX VST / testnet) — KNOWN GOOD
```python
import asyncio, os
from dotenv import load_dotenv; load_dotenv()
import ccxt.async_support as ccxt   # <-- async_support, NOT sync ccxt

USE_TESTNET = str(os.getenv("USE_TESTNET","1")).lower() in {"1","true","t"}
ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY","")
sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET","")
SYM = "XRP/USDT:USDT"   # swap format, NOT "XRPUSDT"

async def main():
    ex = ccxt.bingx({"apiKey":ak,"secret":sc,"options":{"defaultType":"swap"},
                     "enableRateLimit":True,"timeout":30000})
    if USE_TESTNET: ex.set_sandbox_mode(True)
    ex.options["defaultType"]="swap"
    bal = await ex.fetch_balance()          # quote asset "VST" on testnet
    pos = await ex.fetch_positions(symbols=[SYM])
    ord_ = await ex.fetch_open_orders(symbol=SYM)
    # ... print ...
    try: ex.close()                          # v4.5 returns None, no await
    except Exception: pass
asyncio.run(main())
```
Env note: `.env` is a symlink to `/home/layman/.hermes/.env`. Process env of a
running bot is readable at `/proc/<pid>/environ` (tr '\0' '\n').

## 2. QuestDB HTTP queries (port 9000)
- Designated timestamp column is named **`timestamp`** (NOT `ts`).
- Correct: `SELECT close, volume FROM klines_1m WHERE symbol='XRPUSDT' AND timestamp > dateadd('m', -60, now()) ORDER BY timestamp DESC LIMIT 60`
- Wrong: `... ORDER BY ts DESC` -> `Invalid column: ts`.
- Confirm a symbol exists with `SELECT symbol, count() FROM klines_1m`. Do NOT
  trust `LIMIT 5` on a multi-symbol table (returns arbitrary first rows).
- Invoke from shell: `curl -s "http://127.0.0.1:9000/exec?query=<urlencoded>"`.

## 3. Puppeteer + TradingView (Node, system chrome)
- Install: `cd tools/tv_analyzer && npm init -y && PUPPETEER_SKIP_DOWNLOAD=true npm install puppeteer@23`
- Launch with system chrome (already at `/usr/bin/google-chrome`):
  `puppeteer.launch({headless:'new', executablePath:'/usr/bin/google-chrome',
   args:['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage']})`
- TV technicals page: `https://www.tradingview.com/symbols/XRPUSDT/technicals/`
  -> page.evaluate to grab rating / oscillators / moving averages / levels.
- Wait for widgets: `networkidle2` + ~4s sleep before evaluate.

## 4. Orchestrator process liveness (false TERMINATED fix)
`generate_telemetry_report` only trusts `self.processes` (spawned by the
orchestrator). External components need a psutil cmdline scan:
```python
import psutil
sig = ("ai_scalper_bot", "run_bot")   # signature per component
for proc in psutil.process_iter(["pid","cmdline"]):
    cl = " ".join(proc.info.get("cmdline") or [])
    if all(t in cl for t in sig) and proc.is_running():
        return proc   # PID found -> report RUNNING
```

## 5. Live market-data sanity check (ZMQ :5555)
`python tools/check_zmq.py` subscribes to the Hub and prints depth/trade/walls
events for XRPUSDT — confirms the data feed is alive without touching the bot.

## Account-context reminder (transient — verify live, do not hardcode)
BingX VST testnet, XRP/USDT swap, leverage x5, hedge mode. Free margin rises
after canceling stale orders / partial-close. Re-check with the probe above
before any decision. (Session balances/positions were transient and are NOT
recorded here on purpose.)
