# Market Analysis Stack — QuantumEdge (Supervisor)

Recipes for the 4-source analysis pipeline and the operational trading plan.
All paths relative to `/home/layman/QuantumEdge`.

## 1. Puppeteer / TradingView parse
Node + system chrome; Puppeteer installed with `PUPPETEER_SKIP_DOWNLOAD=true`.
- Smoke test: `node tools/tv_analyzer/smoke.js` → prints TV title + `PUPPETEER_OK`.
- Parse: `node tools/tv_analyzer/tv_parse.js XRPUSDT` → JSON
  `{technicalsPage:{rating,oscillators,movingAverages,levels}, priceText,
  fullTextSample, ...}`. `fullTextSample` holds "Day's range X – Y" (regex it).
- Verify JS with `node --check tools/tv_analyzer/tv_parse.js`.
- Chrome launch: `puppeteer.launch({headless:'new',
  executablePath:'/usr/bin/google-chrome', args:['--no-sandbox']})`.

## 2. Firecrawl news layer (Free Tier, keep minimal)
- Key stored in `config/firecrawl.key` (NOT `.env` — user blocks `.env` edits).
  Script resolves: env `FIRECRAWL_API_KEY` → `config/firecrawl.key`.
- Call: `POST https://api.firecrawl.dev/v1/search` with
  `Authorization: Bearer <key>`, body `{"query":"XRP Ripple price news today","limit":3}`.
- Returns `{success:true, data:[{title, description, ...}]}`.
- Sentiment = count bull/bear keywords in titles+descriptions →
  BULLISH / BEARISH / NEUTRAL. 1 request per analysis run.

## 3. Operational-plan level math (`build_plan`)
Inputs: `price` (float from TV or BingX mark), `vol_pct` (1h klines range or 0.003
fallback), `bias` (LONG/SHORT/NEUTRAL from TV; funding>0 or news BULLISH nudges).
- LONG:  entry=price·(1−0.5·vol), TP1=+vol, TP2=+2·vol, SL=−1.5·vol, BE=+0.4·vol
- SHORT: mirror signs
- RANGE: buy=mid·(1−vol), sell=mid·(1+vol), TP=opposite edge, SL=1.5·vol
- BE: SL→entry+0.05% once in profit. Trailing: walk SL ~0.02–0.05%/tick, min +0.1%.
- Size: base 50 XRP/order, scale by vol. Partial TP at TP1 (50%), rest trails.
- If TV/news flip bias → shrink size / exit; on range breakout → replan.

## 4. Run + persist
`.venv/bin/python3 tools/supervisor_market_analysis.py` (from project root so
`load_dotenv` + `config/firecrawl.key` resolve). Prints plan; also writes
`runtime/supervisor_plan.md` and `runtime/supervisor_plan.json`.

## 5. Analysis cron (plan-only, SAFE)
- `cronjob create` schedule `*/15 * * * *`, `deliver='local'`, prompt runs:
  `cd /home/layman/QuantumEdge && .venv/bin/python3 tools/supervisor_market_analysis.py`
- LOCAL-only ⇒ no chat delivery; plan accumulates in `runtime/supervisor_plan.md`.
  To deliver to Telegram, set `deliver='telegram'`.
- This cron NEVER places orders — it only publishes the Supervisor plan.

## 6. Failure watch
- If `ai_scalper` shows FAILED after a restart → almost always the
  `xgboost` import crash from running the orchestrator with system `python3`.
  Always use `.venv/bin/python3 QuantumEdge.py start`.
- Cron "completed normally (exit 0)" notifications for old daemon attempts are
  stale — check the LIVE `QuantumEdge.py status` (ai_scalper RUNNING) instead.

## 7. BTC as LEADING indicator (video-distillation → XRP plan)
The user feeds translated VIDEO analysis (usually BTC-focused). XRP correlates
~0.6-0.7 to BTC, so the XRP plan should be driven off BTC price, not just XRP
internals. Added `fetch_btc_ctx()` + BTC block in `build_plan()`.

Recipe (condensed):
- `fetch_btc_ctx()` (in supervisor_market_analysis.py):
  CCXT_BTC = "BTC/USDT:USDT"
  tk  = await ex.fetch_ticker(CCXT_BTC)        # .get("last"), .get("percentage")
  fr  = await ex.fetch_funding_rate(CCXT_BTC)   # .get("fundingRate")
  oi  = await ex.fetch_open_interest(CCXT_BTC)  # .get("openInterestValue")
  xrp = await ex.fetch_ticker(CCXT_SYMBOL)
  xrp_btc = round(xrp.get("last") / tk.get("last"), 8)   # BingX has NO XRP/BTC pair
- BingX has NO direct XRP/BTC pair — ccxt raises "does not have market symbol
  XRP/BTC:USDT". Compute XRP/BTC = XRP/USDT ÷ BTC/USDT. Never fetch it directly.
- Map BTC zones to XRP action in the plan (user's July video = BTC long-bias,
  expects a liquidity sweep DOWN to 63.6-64.2k before the next up-leg):
  - BTC <= ~64500 -> correction zone -> wait for the down-sweep, do NOT add long at
    the top; expect to fill LONG grid on the dip (bid_walls zone). Aligns w/ owner
    Rule 3 (add long on dips).
  - BTC >= ~66000 -> breakout up -> long more aggressively, esp. US session (13-21 UTC).
  - middle -> neutral, wait for signal.
- `main()` must call `fetch_btc_ctx()` (async) and pass `btc=btc` into `build_plan`;
  also persist into `save_plan` payload so runtime/supervisor_plan.json keeps it.
- PATCH PITFALL: inserting `fetch_btc_ctx` via patch can silently drop the
  `def fetch_questdb_recent(symbol, minutes=60) -> dict:` signature (leaving only
  its docstring) -> NameError at run. After any multi-block patch in this file,
  re-read the region and confirm every `def` line is intact; ast.parse alone won't
  catch a missing signature because the orphaned docstring string still parses fine.
