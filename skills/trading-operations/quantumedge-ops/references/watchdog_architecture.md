# Watchdog Architecture (QuantumEdge, 2026-07-21)

Local LLM as STALKER, cloud LLM as TRADER. Built to stop the "free-model cron
died -> position unmonitored -> loss" failure that happened twice.

## Roles (capability-split, NOT naive local-vs-cloud)
- **Local LLM = Watchdog (Ollama, RTX 4060)** — `hermes3:8b-llama3.1-q5_K_M`
  (5.7GB, Q5_K_M). Runs on `http://localhost:11434`. NOT a trader: owner says
  8B "weak for trading". Its ONLY job: measure + decide wake/no-wake.
- **Trader = Hermes/hy3 (cloud)** — reasons every tick, gathers data, delegates
  deep analysis to `agy`, SELF executes orders.
- **agy (Antigravity CLI)** — heavy deep-market analyst with internet + news.
  Called by the trader for the 15m / vol_spike / liq_alert deep passes only.

## Data flow
```
[94bdbddb5f67 no_agent] watchdog.sh -> tools/watchdog.py
   -> qe_trade.py snapshot + 5m OHLCV (BingX VST)
   -> vol_index (latest TR / 14-avg ATR), price_move_pct, buffer_pct (liq dist)
   -> ask local LLM: wake?  (math fallback if Ollama down)
   -> runtime/watchdog_signal.json
            |
            v
[752701ce6015 hy3] trader cron reads watchdog_signal.json
   wake==false -> shallow check, SILENT
   wake==true  -> gather full data -> `agy ...` deep analysis -> SELF decide -> orders
```

## watchdog.py essentials (verified working)
- `vol_index = min(1.0, max(0.0, latest_tr / avg_atr / 2.0))`; threshold >0.75.
- `buffer_pct` for long: `liq = entry*(1 - 0.95/lev)`; `dist = (price-liq)/price*100`;
  alert if <3%.
- `price_move_pct = abs(price - last_price)/last_price*100`; threshold >1.0%.
- Scheduled 15m wake at minute in {0,15,30,45} +/-1.
- **ccxt MUST be async here**: `import ccxt.async_support as ccxt`,
  `ohlcv = await ex.fetch_ohlcv(...)`, call via `asyncio.run(...)`. The SYNC
  call returns a coroutine and silently zeroes vol_index (this bug shipped once).
- Local LLM called via `httpx.post("http://localhost:11434/api/generate",
  json={model, prompt, stream:False, format:"json", options:{temperature:0.1}})`.

## Cron inventory (current)
- `94bdbddb5f67` QE Local Watchdog — `*/5`, `no_agent=true`, script `watchdog.sh`.
- `752701ce6015` QE Trader — `*/5`, model `tencent/hy3`, reads watchdog signal.
- `8ea10dca157c` QE Oversight — `*/15`, model `tencent/hy3`, deep accountability.

## Failure modes seen
- Free-tier cron model -> 429 -> `last_status: error` -> no trades. Use hy3.
- `watchdog_signal.json` not read by trader -> trader trades blind. Ensure the
  trader cron prompt actually consumes the file.
- Ollama down -> math fallback still wakes on hard rules (liq<3%, vol>0.75). OK.
