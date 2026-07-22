---
name: quantumedge-ops
description: Operations, supervision, and debugging playbook for the user's personal HFT system QuantumEdge (/home/layman/QuantumEdge). Covers the Orchestrator/Supervisor role, live market-data/balance probes, BingX (testnet/VST) execution via ccxt, QuestDB queries, TradingView analysis via Puppeteer, and known project pitfalls. Load this whenever the user asks about QuantumEdge, the AI Scalper bot, XRP/USDT trading, or "act as supervisor/orchestrator" for their trading system.
---

# QuantumEdge Operations (Orchestrator / Supervisor)

QuantumEdge is the user's personal HFT orchestration project at
`/home/layman/QuantumEdge`. The agent's role here is **Orchestrator + Supervisor**:
read system state, analyze the market, publish a trading plan, and apply
user-sanctioned exchange actions.

**Two operating modes — the user tells you which:**
- **Per-action authorization (default):** NEVER trade or close positions on
  your own initiative — get explicit per-action authorization for anything
  that moves the account.
- **Delegated autonomy (user delegates the shift, e.g. "you're in charge
  tonight, report in the morning"):** you MAY execute live orders
  unattended, but ONLY within the user's standing rules and the guardrails
  below. Build it as a stateless-safe cron autopilot, not ad-hoc.

**ACTIVE SUPERVISOR — every-cycle discipline (FIRST-CLASS correction this session):**
The agent cron (`905acfcf7fbf`) wakes every 5 min and YOU reason each tick. The
user's explicit verdict: do NOT just observe and "wait for the script" — you are
the BRAIN, you trade. Concrete failures that drew correction:
- **Stale data:** I once reported an 08:41 snapshot at 09:25 (market had swept
  down, SHORT flipped to profit) and said "both legs in loss, waiting." The user:
  "в тебе невірні дані, з відки ти береш дані?" → ALWAYS pull a FRESH
  `qe_trade.py snapshot` immediately before reporting or acting. Never cite an
  old snapshot. The 5-min cron means positions MOVE between your reads.
- **Passive loop:** citing "both legs in loss → waiting" while the market moved
  and a profitable leg existed = "you did nothing every 5 min." The user:
  "ти маєш активно торгувати а не надіятись на скрипти... Виставляй та закривай
  прибуткові ордери самостійно!" → Every cycle: fresh snapshot → if a leg is
  profitable, HARVEST it (market close part of it) → if grid thinned, REFILL it
  → report ≤5 lines. If genuinely nothing actionable (both legs loss + no BTC
  signal), say so in one line — but that is rare; usually a profitable leg exists.

**Heads-up — the user corrected agent risk-posturing (FIRST-CLASS signal):**
When given a trading/supervision task, the user expects you to **actively
seek trading opportunities, not enumerate reasons to stand aside**. Do not
hide behind risk caveats — surface them briefly, then get on with finding
the trade. Concrete correction: "головне завдання не сидіти сховавши голову
за ризиками а шукати можливості для трейду." Keep technical guardrails
Keep technical guardrails (ledger vs duplicate orders, live-switch dry-run) — those prevent real bugs,
they are not risk-avoidance.

**Communication style — explicit user correction (FIRST-CLASS signal):**
The user wants CHAT REPLIES KEPT SHORT and token-light, especially during live trading:
"менше пиши в чат, пиши коротко, по справі чи ордеру, чи стану ринку, економим токени на тексті."
Apply in this project: report only signal-bearing facts — price, imbalance, session, orders placed,
closed/won trades, realized PnL. No preamble, no restated context, no "as an AI" filler, no long
rationale unless the user asks. Bullet or one-liner. Tables OK only when comparing multiple values.

## Trader persona — Shark / Market-Maker (user elevation, standing)
The user promoted the agent from passive supervisor to an active trader:
"тепер ти трейдер на ф'ючерсному крипторинку, акула, маркет-мейкер, 15+ років
досвіду." Expected analysis depth (encode into every report/decision):
- **Early trend-shift detection:** MACD histogram turn + line/signal cross,
  Bollinger squeeze (width contraction → imminent impulse), RSI divergence
  (price makes new high, RSI lower → downside reversal), swing structure
  (HH/HL vs LH/LL).
- **Order-book manipulation reading:** spoofing (wall >4x avg, >300k),
  wall clusters (fake support/resistance), absorption (large top-10 volume,
  tiny price move), imbalance extremes (>±0.3 = one side pressing).
- **Macro via BTC** + XRP/BTC correlation, mapped to video zones.
- Output a **verdict with conviction (0..1)** + concrete entry/TP1/TP2/SL levels,
  not vague advice. When MM manipulation is HIGH severity, LOWER conviction
  (don't walk into the trap).
The `market_analysis.py` contour implements exactly this. See
`references/analysis_contour.md`.

## Project shape (verify with search_files before assuming)
- `QuantumEdge.py` — Unified Orchestrator daemon (JSON-RPC over ZMQ :5560).
  `python QuantumEdge.py status|start|stop|run|dashboard`.
- `config/` — `risk.yaml`, `quantumedge_testnet.yaml`, `supervisor.yaml`,
  `llm_*.yaml`, `ports.yaml`. NOTE: `quantumedge_testnet.yaml` may hold a
  STALE `MARKET_DATA_SYMBOLS` (e.g. ETHUSDT) — the live symbol is whatever the
  running process env says (check `/proc/<pid>/environ`).
- `src/quantum_edge_core/ai_scalper_bot/` — the main scalper (run_bot.py,
  bot/infrastructure/bingx_gateway.py via ccxt).
- `src/quantum_edge_core/market_data/hub.py` — MarketDataHub (ZMQ PUB :5555).
- QuestDB on HTTP :9000, pgwire :8812.
- Logs: `bot.log` (ai_scalper), `logs/quantum_edge.log` (dyndca/main __main__),
  `/home/layman/logs/processes/ai_scalper_bot.log` (per-process fd target).

## Supervisor operating rules (user decisions — embed, don't re-litigate)
- **Risk management auto-stop is OFF by design** (`risk.yaml:
  risk_management_enabled: false`). Protection is delivered via QUALITY
  MARKET ANALYSIS + explicit trading plan, NOT hard stops. Do not silently
  re-enable risk management; if you think it's needed, propose it, don't do it.
- LLM moderation may sit behind an open circuit breaker (policy reason
  `OK|LLM_CB_OPEN`) — then YOU do the analysis.
- "free=0 / Insufficient margin" on the exchange usually means margin is fully
  locked in positions (drawdown/over-exposure), NOT a bug. The user treats this
  as normal. Freeing margin = partial-close a position or cancel stale orders.

## Read-only market/account probe pattern (safe, repeatable)
Use `.venv/bin/python3` with **`ccxt.async_support as ccxt`** (NOT sync `ccxt`
— see pitfalls). Testnet/VST keys come from env (`BINGX_TESTNET_API_KEY`,
`BINGX_TESTNET_SECRET`), `USE_TESTNET=true`. `set_sandbox_mode(True)`.
Symbol for swap: `XRP/USDT:USDT`. `fetch_balance()` (account type "swap",
quote asset "VST" on testnet), `fetch_positions(symbols=[...])`,
`fetch_open_orders(symbol=...)`. See references/tech_gotchas.md for a
known-good probe skeleton.

## Action pattern (user-authorized only)
Cancel-all / partial-close use the SAME gateway. `cancel_all_orders(symbol=)`
is safe & idempotent. To reduce a net-short bias in hedge mode, place a market
`buy` with `params={"positionSide":"SHORT"}`. Verify AFTER the action with a
read-only probe (free margin should rise, size should drop).

## Market analysis stack (built this session)
- `tools/supervisor_market_analysis.py` — joins TradingView (Puppeteer) +
  BingX funding/OI + Firecrawl news + QuestDB klines → prints an **OPERATIONAL**
  trading plan (entry/exit/BE/trailing/position-management). NO orders placed.
  Run: `.venv/bin/python3 tools/supervisor_market_analysis.py` from project root.
  Persists plan to `runtime/supervisor_plan.md` + `runtime/supervisor_plan.json`.
- `tools/tv_analyzer/` — Node + Puppeteer (system `/usr/bin/google-chrome`,
  installed with `PUPPETEER_SKIP_DOWNLOAD=true`). `tv_parse.js` extracts TV
  technical rating / oscillators / moving averages / price / day's range.
- `config/firecrawl.key` — **Firecrawl API key lives HERE, not in `.env`**
  (user blocks `.env` edits). `fetch_news()` resolves key order: env
  `FIRECRAWL_API_KEY` → `config/firecrawl.key`. Free Tier: 1 request/run,
  `limit=3`, keep minimal. Sentiment = naive bull/bear keyword count.
- `tools/supervisor_readonly_probe.py` — balance/positions/orders probe.
- **Agent's OWN analysis now lives ISOLATED at `~/.hermes/quantumedge_analysis/`**
  (`market_analysis.py` = shark/market-maker verdict; `indicators.py` =
  RSI/MACD/BB/ATR; `market_data.py` = exchange+TV+news collector). It is kept OUT
  of the bot code, uses the project `.env`/venv, and SUPERSEDES
  `supervisor_market_analysis.py` for the agent's decisions. Run:
  `cd ~/.hermes/quantumedge_analysis && ~/QuantumEdge/.venv/bin/python3 market_analysis.py`
  → writes `market_analysis.json` (read by the agent each cycle). Full layout in
  `references/analysis_contour.md`.
- **`trader.py` — the AUTONOMOUS EXECUTION BRAIN (built 2026-07-16):** reads
  `market_analysis.json`, takes a `qe_trade.py snapshot`, then DECIDES and ACTS
  (real orders). Core logic: (1) HARVEST SHORT when in profit + price < short
  entry → `market buy SHORT` → free margin → `place buy LONG` (lock Rule 2/3);
  (2) refill LONG grid via `place buy LONG` steps below `support_book`;
  (3) scalp LONG on conviction ≥0.6; (4) `--deep` adds breakout orders outside
  BB. Persists every action to `trader_journal.jsonl`; cycle count + realized PnL
  to `trader_state.json`. Run: `~/QuantumEdge/.venv/bin/python3 trader.py`
  (or `--deep` for the 15m tick). THIS is what the 5m cron calls — NOT a bare
  script. See `references/trader_brain.md`.

### Operational plan format (Supervisor output)
`build_plan()` derives concrete levels from data, NOT vague advice:
- Volatility proxy `vol_pct` = max((qdb max−min)/min, 0.0005) from 1h klines.
- LONG: entry = price·(1−0.5·vol), TP1 = +vol, TP2 = +2·vol, SL = −1.5·vol,
  BE = +0.4·vol. SHORT: mirrored. RANGE: buy/sell at ±vol around mid.
- BE (breakeven): move SL to entry+0.05% once in profit.
- Trailing: walk SL after BE by ~0.02–0.05% steps, holding min +0.1%.
- Position mgmt: partial TP at TP1 (50%), rest trails to TP2; if TV/news flip
  bias → shrink size or exit; on range breakout → replan.
- Bias = TV rating → {LONG/SHORT/NEUTRAL}; funding>0 or news BULLISH nudges
  NEUTRAL toward "mildly bullish".

### BTC as LEADING indicator (added this session — user validated)
The user supplies VIDEO DISTILLATIONS (translated market analysis, usually about
BTC). XRP is correlated (~0.6-0.7) to BTC, so **drive the XRP plan off BTC price**,
not just XRP internals.
- `fetch_btc_ctx()` (in `supervisor_market_analysis.py`): pulls `BTC/USDT:USDT`
  ticker + funding + OI via ccxt, AND derives `xrp_btc = XRP.last / BTC.last`.
- **BingX has NO direct `XRP/BTC` pair** (`ccxt` errors "does not have market symbol
  XRP/BTC:USDT") — compute it from the two USDT pairs. Don't try to fetch it directly.
- `build_plan()` prints a BTC block and maps BTC zones to XRP action:
  - **BTC target zone for the OWNER's exit rule = 63,600** (NOT 66k). The user
    clarified: when XRP SHORT is in profit AND BTC reaches its target zone
    (≈63.6k, i.e. the video's expected down-sweep / correction low), the rule is
    → HARVEST (close) the profitable SHORT and ADD a little LONG. BTC ≥ ~66k is a
    separate breakout-up signal (long more aggressively, US session).
  - BTC ≤ ~64 500 → "zone de correction 63.6-64.5k (video) — wait for sweep, don't
    buy the highs" → hold LONG additions, expect a dip to add long (aligns with owner
    Rule 3: add long on dips).
- **Weekday seasonality / weekend-sweep thesis (owner-supplied, empirically tested):**
  owner's rule — "Monday moves are false; true move starts Tuesday opposite; weekend
  range highs/lows get swept." Tested on ~112 weeks of BTC 1d: cleanest edge is
  **green Monday → red Tuesday (59%)**; raw Mon→Tue reversal is only 53% (weak); a
  RED Monday gives NO reliable Tuesday bounce; weekend HIGH/LOW gets swept 61-68%;
  the bullish trigger for defending an XRP long is BTC sweeping the **weekend LOW and
  closing back above it** (false breakdown, 35% base). Full stats + reusable study
  script (`scripts/weekday_study.py`): `references/btc_seasonality.md`. NOTE: fetch
  history via BingX/bybit fallback — `api.binance.com` is NOT resolvable from this host.
- The user's video gave BTC long-bias for July, expecting a liquidity sweep DOWN to
  63.6-64.2k before the next leg up. Translates to XRP: wait for the down-sweep
  (bid_walls zone), then fill the LONG grid there. Do NOT add long at the top of the
  range (matches "don't buy the highs" from the video and Rule 3).
- Always re-run a real analysis after adding `fetch_btc_ctx` — a multi-block `patch`
  that inserts `fetch_btc_ctx` can silently DELETE the `def fetch_questdb_recent(...)`
  signature (leaving only its docstring) → `NameError` on run. Verify every
  `def` line survived the patch.

### Analysis gaps (KNOWN — not yet wired; useful when improving the plan)
- **RSI / MACD / ATR / Bollinger Bands are NOW wired into the agent's isolated
  analysis contour** at `~/.hermes/quantumedge_analysis/indicators.py`
  (`compute_indicators` + `trend_score`). They are pulled from XRP OHLCV via
  `ohlcv = await ex.fetch_ohlcv(...)` (async, AWAITABLE in this env — see
  Pitfall #1, the "do NOT await" note is WRONG and broke `watchdog.py`'s
  vol_index). The project's `supervisor_market_analysis.py` still derives bias
  ONLY from TV + funding + news (no RSI/MACD) — the `.hermes` contour
  supersedes it for the agent's own decisions. See
  `references/analysis_contour.md`.
- **QuestDB volatility is daemon-dependent.** `fetch_questdb_recent()` hits
  `http://127.0.0.1:9000` (klines_1m). If the MarketDataHub/Orchestrator daemon
  is down (it was disabled 2026-07-16), the query returns no rows and `vol_pct`
  falls back to a flat 0.3% — so TP/SL spacing is currently STATIC, not
  volatility-derived. Pull OHLCV from the exchange directly for real vol instead
  of relying on the daemon.

### Autonomous trading crons (CURRENT design — 2026-07-21, REVISED this session)
- **WHO CONTROLS POSITIONS = the agent IN CHAT, NOT an autonomous cron.**
  FIRST-CLASS correction (2026-07-21): the old design had a 5-min cron
  (`02c3d45bd603`) that ran `trader.py` and executed orders ITSELF. The user
  caught it silently SCALP-REDUCING the LONG (100k+70k closes) without the
  agent's knowledge and WITHOUT a Telegram report. Owner verdict: "керувати
  позиціями має Hermes у чаті, а не крони." FIX APPLIED:
  - `02c3d45bd603` (5m trader) and `8ea10dca157c` (15m deep) → **PAUSED**
    (`cronjob action=pause`). They no longer auto-trade.
  - Replaced by an **ALARM-CLOCK cron `258abcced588`** (`every 5m`,
    `deliver=local` — CRITICAL: see collision pitfall #16; `no_agent=false`): it
    wakes the AGENT IN THIS CHAT; the agent reads `watchdog_signal.json` + fresh
    `qe_trade.py snapshot`, reasons, and trades manually via `qe_trade.py` (variant
    A: full autonomy per the standing plan, no asking). This IS the Watchdog→chat
    bridge the owner wanted — Watchdog can't post to chat directly (no gateway), so
    the alarm polls the signal file every 5 min and wakes the agent.
  - **CRITICAL — alarm MUST use `deliver=local`, NEVER `deliver=origin` (FIRST-CLASS,
    2026-07-21):** `deliver=origin` posts the agent's actions to Telegram. The Hermes
    **gateway** is ALSO connected to that same Telegram chat. When the gateway-Hermes
    SEES those messages it treats them as user input and STARTS TRADING on the same
    BingX account → TWO agents on one account → order/position COLLISIONS (duplicate
    closes, a partial -2333 loss close, conflicting short/long legs). FIX: alarm uses
    `deliver=local` (saved, not chat-delivered) so only the in-terminal chat agent
    trades. Telegram trade delivery is OFF by owner order ("вимкни звіти в телеграм
    щоб сесії не запаралелюсь"). If TG reports are ever re-enabled, route to a SEPARATE
    channel the gateway ignores — never let a trading agent's output share the
    gateway's Telegram surface.
  - **Watchdog** stays as the local systemd daemon (unchanged), still writing
    `watchdog_signal.json`. It does NOT trade.
- **SILENT-reporting trap (FIRST-CLASS, found 2026-07-21):** the cron's
  `wake==false → SILENT` branch only reported when "uPnL changed >2% vs balance
  OR orders changed." Partial position CLOSURES (harvest/scale-out) slipped
  through → no TG report, owner missed the size drop. Owner rule: EVERY order
  action (open/close/partial/scale) MUST report to TG; on position CLOSE always
  include realized PnL + balance. The alarm-clock prompt embeds this. If reusing
  an autonomous cron, the SILENT condition MUST key off
  `trade_journal.jsonl` new `act=close/place` rows, not just uPnL delta.
- Both crons MUST be on a STABLE model (hy3). LOCAL-only ⇒ output saved, not
  chat-delivered; for chat use `deliver=origin` (the alarm does this).
- To watch live: `tail -f ~/.hermes/quantumedge_analysis/trader_journal.jsonl`.

### Restarting the orchestrator (xgboost trap — FIRST-CLASS)
- ALWAYS restart via `.venv/bin/python3 QuantumEdge.py start|stop`. System
  `python3` lacks `xgboost` → ai_scalper crashes on import
  (`ModuleNotFoundError: No module named 'xgboost'`) → component FAILED.
- Sequence: `stop` (old daemon halts, frees :5560) → `start` via `.venv`.
- `_zmq_guard_cleanup` kills processes on known ports at startup, then
  bootstrap re-launches all. POSITIONS ON EXCHANGE ARE PRESERVED (the bot
  never auto-closes on shutdown) — verify after with read-only probe.
- Monitor fix (deep): `generate_telemetry_report` only saw spawned procs; if a
  spawned proc DIED (e.g. first bad restart) its entry stayed TERMINATED even
  after a live external instance appeared. Patch: when an entry is not running,
  re-scan via `_find_external_process(name)` (psutil cmdline match) and
  overwrite to RUNNING. Verify with `QuantumEdge.py status` showing ai_scalper
  RUNNING, and `ps` showing `ai_scalper_bot.run_bot`.

### Telegram / session history (how memory actually works here)
- Telegram messages arrive as the SAME session (field `source: "telegram"`),
  fully in `session_search` — they are NOT auto-copied to memory. Memory
  (MEMORY.md/USER.md) is populated ONLY by deliberate `memory` writes.
- The user referenced a **"міст bridge для делегування складних завдань agy -
  Antigravity"** (session `20260713_192852`, Telegram): an external-agent bridge
  config in `~/.hermes`. Earlier (weak model) attempts to use it failed. If the
  user asks to "ask the Scalp bot via the bridge", first `search_files` `~/.hermes`
  for `bridge`/`Antigravity`/`agy` to locate the config before delegating.

## Pitfalls (project-specific, durable)
1. **ccxt async vs sync**: importing `ccxt` (sync) and `await`-ing its methods
   raises `object dict can't be used in 'await' expression`. ALWAYS
   `import ccxt.async_support as ccxt` for async scripts.
   **VERSION NUANCE — CORRECTED (2026-07-21):** an earlier note claimed
   `fetch_ticker`/`fetch_ohlcv` "return directly, do NOT await" on ccxt 4.5.64.
   That is WRONG for THIS install. On the pinned `ccxt==4.5.64` here, ALL of
   `load_markets`, `fetch_balance`, `fetch_positions`, `fetch_order_book`,
   `fetch_funding_rate`, `fetch_open_interest`, `fetch_open_orders`,
   `fetch_ticker`, AND `fetch_ohlcv` are AWAITABLE coroutines — `await` every
   one. The bad note caused a real bug: `watchdog.py` called
   `ex.fetch_ohlcv(...)` WITHOUT await → got a coroutine → `vol_index` silently
   computed as **0.0** (volatility monitor dead for days). FIX in any new
   script: `ohlcv = await ex.fetch_ohlcv(symbol, tf, limit=N)` inside an async
   fn, call via `asyncio.run(...)`. Always verify with a 1-line diag before
   building a loop:
   `async def t(): ex=ccxt.bingx(...); await ex.load_markets(); print(type(await ex.fetch_ohlcv('XRP/USDT:USDT','5m',30)))` → must print `<class 'list'>`, never `coroutine`.
2. **ccxt `close()` in v4.5**: returns None, not a coroutine — call `ex.close()`
   inside `try/except`, not `await ex.close()`.
3. **QuestDB designated timestamp column is `timestamp`**, not `ts`. Queries
   like `ORDER BY ts` fail with `Invalid column: ts`. Use
   `... AND timestamp > dateadd('m', -60, now()) ORDER BY timestamp DESC`.
4. **BingX swap symbol format**: `BASE/USDT:USDT` (e.g. `XRP/USDT:USDT`), not
   `XRPUSDT` and not `XRP/USDT`. Hedge-mode position closes need
   `params={"positionSide":"SHORT"/"LONG"}`.
5. **Orchestrator false-report TERMINATED**: `generate_telemetry_report` only
   sees processes it spawned itself (`self.processes`). Components started
   externally (e.g. ai_scalper running before `start`) show as TERMINATED even
   when alive. Verify liveness directly via `ps` / `/proc/<pid>/environ` or a
   psutil cmdline scan, not just `QuantumEdge.py status`.
6. **`LIMIT 5` on a multi-symbol table returns an arbitrary first rows** — a
   `SELECT symbol FROM klines_1m LIMIT 5` returned all BTCUSDT and falsely
   suggested "no XRP history". Always `GROUP BY symbol` or filter by symbol to
   confirm presence.
7. **`rm` is blocked by the user's environment** for safety — don't try to
   delete scratch files; leave them (they're harmless, un-imported).

## Verification norm for this project
No pytest suite exists for `tools/*.py` / `QuantumEdge.py` (the latter binds
ZMQ :5560 on import; the former need network). Verify with `ast.parse` (Python)
+ `node --check` (JS) for syntax, then a REAL run (read-only probe / psutil
scan) for function. Don't claim verified without a real run.

## Delegated-autonomy autopilot (when the user puts you in charge)
When the user delegates the shift (sleeps, you trade, report in the morning),
build the loop with **THE AGENT IN THE LOOP**, not a bare `no_agent` script.

**FIRST-CLASS correction this session:** an early attempt used a `no_agent=true`
cron job running a hardcoded `if`-ladder script. It executed orders but made
ZERO realized profit across the night — because the agent never woke up to
read the book, place take-profits, or harvest. The user's verdict: "ти сам
участі в торгах не брав а поклався на автопілот." Lesson: when the user says
"you're in charge / be the brain," use **`no_agent=false` (LLM) cron** so the
agent reasons every tick. A stateless script alone cannot scalp (no TP logic,
no read-loop). Reserve `no_agent` scripts for pure watchdog/emit-text jobs.
User's eventual preferred structure: **agent-driven now; move to a HYBRID
(script places grid every 5m, agent wakes every 15m to correct/forecast) once
the strategy is hardened into a skill** — let agent rest longer then.

**Current user directive (2026-07-16, standing when autonomous mode is on):**
"працюй автономно, не питай у мене рішення, не покладайся на скрипти — приймай
торгове рішення кожні 5 і 15 хв." Interpretation: a **5-min agent decision loop**
(reason from `market_analysis.json` + fresh `qe_trade.py snapshot`, act per lock
rules) AND a **15-min deep-analysis refresh** (`market_analysis.py` →
`market_analysis.json`). The AGENT decides — no `clarify`, no waiting on script
output. LIVE ORDER EXECUTION IS CONFIRMED (user said "Дозволяю ставити РЕАЛЬНІ
ордери (limit/market через qe_trade.py). Рахунок — демо" on 2026-07-16). The
agent now EXECUTES real orders on the VST demo account autonomously every 5 min
via `trader.py` — no `clarify`, no waiting. Analysis-only mode (B) is no longer
the default; the account is demo so the user accepts the risk to watch the
agent's style/results. Keep all lock-unwinding rules + 101209 notional guard.

Full recipe, cron wrapper, env guardrails, and the opportunity-seeking
decision ladder live in `references/night_autopilot.md`.

### Trading toolkit `tools/qe_trade.py` (built this session — PREFERRED agent interface)
CLI the agent calls each tick. BingX VST, hedge-mode. Run from project root with
`.venv/bin/python3`.
- `snapshot` → JSON: price, `book` (top20 bid/ask + `bid_walls`/`ask_walls`
  clusters + `imbalance` + `best_bid/ask`), `balance`, `legs` (positions),
  `open_orders`, and **`session`** (ASIA/EU/US via UTC hour — US 13-21 UTC is
  the volatile/trending one to expect range breakouts).
- **`snapshot` hides a leg's SL/TP**: `legs[]` carries only side/size/entry/uPnL/lev —
  NO `stopLossPrice`/`takeProfitPrice`. To confirm an SL exists (or catch a live
  "no SL" rule violation), query `fetch_positions` via ccxt directly and read
  `stopLossPrice`/`takeProfitPrice`. (Caught a SHORT with `stopLossPrice:null`
  this way — invisible in `snapshot`.)
- `place <buy|sell> <LONG|SHORT> <qty> <price> [tp] [sl]` → limit order, logs intended TP. **The 7th positional `[sl]` IS wired** (passed to `stopLoss` triggerPrice) — e.g. `place sell SHORT 150000 1.1475 1.138 1.1550` sets TP 1.138 + SL 1.1550 on the short. Both `tp` and `sl` are *trigger* prices, not limit prices. Verified this session.
- `market <buy|sell> <LONG|SHORT> <qty>` → market close; **computes realized PnL
  itself** (entry-vs-exit) and appends to `runtime/trade_journal.jsonl`.
- `modify_sl <LONG|SHORT> <price>` → set/replace the trailing SL for that leg
  (on BingX VST hedge-mode this ADDS a new stop-market order — see Pitfall #11 SL
  stacking; always cancel the old SL by ID via `cancel <id>` first, then one
  `modify_sl`). **NOTE: the command is `modify_sl`, NOT `set_sl`** — running
  `qe_trade.py set_sl ...` returns `{"error":"unknown cmd set_sl"}`. Verified this
  session.
- **After `modify_sl`, the new SL appears in `open_orders` as `type:"market"` with
  `positionSide` of the leg and `reduceOnly:true`** — and a MISLEADING `price` field
  (the trigger is `stopLossPrice`, not the displayed price). Don't mistake it for a
  stray limit; verify via `fetch_positions` (`stopLossPrice`).
- `cancel_all` / `cancel <id>` / `grid <lo> <hi> <n_side> <qty>` / `trades <hours>`.
- **Hedge-to-delta-neutral execution (Rule #4 / risk→hedge+wait):** when a leg is
  underwater against the trend and Rule #1 forbids closing at a loss, open an
  EQUAL-SIZE opposite limit leg (`place buy LONG <qty>` = short size) to neutralize,
  locking the entry-gap loss and waiting. **To fill against a RISING price, the limit
  must CROSS the ask** (price ≥ `best_ask` from `snapshot` `book`) — a limit at/below
  best ask RESTS and won't fill while price climbs, leaving the position unhedged.
  Verify the hedge filled via `snapshot` `legs` (new opposite leg at the filled entry).
  Manage per Rule #2 when one side turns profitable.
- `trades <hours>` reads `runtime/trade_journal.jsonl` (NOT the exchange) for
  realized PnL — see BingX quirk below.

### Durable BingX VST (testnet) quirks (learned the hard way)
1. **No `realizedPnl` in trade objects AND `fetchLedger` unsupported** for BingX
   via ccxt. `fetch_my_trades` returns `commission`/`price`/`volume` but never
   pnl. So realized PnL MUST be computed by the agent: read the leg's
   `entryPrice` before closing, get `mark` from `fetch_order_book`, then
   `realized = (mark-entry)*qty` for LONG close, `(entry-mark)*qty` for SHORT
   close. Persist to a journal; never trust the exchange field. (`qe_trade.py
   market` already does this.)
2. **Notional/position cap: `ccxt` error `code 101209 "max position value for
   this leverage is 1000"`** fires when the SHORT leg hits its size limit at the
   current 10x leverage. Result: you CANNOT add to SHORT — only reduce it
   (buy-to-cover) when in profit. Build grid ASYMMETRIC: keep adding LONG on
   dips (TP +0.2%), only HARVEST the SHORT in profit. Don't retry SHORT adds.
   **`grid` returns MIXED results near the cap:** a single `grid` call may
   return some legs `closed` (filled immediately as market because price crossed
   the limit) and the rest `"err": 101209`. This is expected, not a bug — always
   `snapshot` + inspect `open_orders` AFTER a `grid` call, and only re-grid the
   missing side if lopsided. The cap is GLOBAL per account (shared with the agent
   cron 905acfcf7fbf), so a full-grid failure often means the cron already filled it.
3. Grid sizing: total notional ≈ open_orders × qty × price must fit `free`
   margin. At ~20k VST free, ~15×15 grid of 2000 XRP each side is too big —
   prefer 2000/side and watch `open_orders_count` in snapshot.
4. Interrupted `grid` runs leave PARTIAL grids (some legs placed, some not) —
   ALWAYS `snapshot` + inspect `open_orders` after any interruption before
   re-running; `cancel_all` then re-grid only if lopsided.
5. **Notional guard when ADDING LONG (autonomous `trader.py` lesson):** the 1M
   USDT cap bites BOTH legs. Before any LONG add, compute `room_contracts =
   int((900000 - long_leg.size*price)/price)` and clamp every add to it; skip the
   add entirely if `room_contracts < 10000`. Without this guard the agent
   SPAMS `101209` errors each cycle (wasted calls, no fills). SHORT harvest
   frees notional quota, so harvest FIRST, then add long.
6. **Realized-PnL accounting gap (BingX VST):** `qe_trade.py market buy SHORT`
   (harvest) does NOT append a `close` record to `trade_journal.jsonl` the way a
   LONG close does, so `trader.py`'s realized-PnL rollup reads 0 even though
   profit was taken. **STILL UNRESOLVED in `trader.py`** — the HARVEST_SHORT log
   entry records the leg's live `uPnL`, not a `close` record, so `trades <hours>`
   ignores it. Fix when hardening: after a `HARVEST_SHORT`, compute
   `realized = (short_entry - price)*qty` and append a `close` journal line, OR
   read the leg's uPnL delta before/after. Until then, realized SHORT-harvest PnL
   must be read from the leg's uPnL history, not `qe_trade.py trades`.
7. **Leverage REJECTED when position value is large (`ccxt` code 101201, "The
   value of your long position is too large, the leverage must be lower than
   5x"):** you CANNOT raise leverage (e.g. 20x) while a large position is open —
   BingX caps max-leverage by current notional. The owner asked to bump 10x→20x to
   gather a bigger position; API refused at 904k LONG. **Lesson:** bigger notional
   via higher leverage is NOT available on an already-large position — stay at 10x
   (1M USDT notional cap) and grow the position by harvesting SHORT to free
   notional quota, then adding LONG within the 900k room guard. Don't fight 101201;
   it's a hard exchange constraint, not a code bug.
8. **`liquidationPrice` is `None` on BingX VST** via ccxt `fetch_positions` — you
   cannot read it. Compute it yourself: `liq_long ≈ entry*(1 - 1/lev*0.95)` (the
   0.95 leaves maintenance-margin buffer), then `dist_pct = (price - liq)/price*100`.
   `trader.py` embeds this: if `dist_pct < 1.0` it raises HEDGE_ALERT and places a
   `HEDGE_SHORT` (does NOT close the long — Rule 1) to cap downside. At 10x, long
   904k @1.1215 → liq ≈ 1.009, ~9% buffer at price 1.10 — safe; watch as XRP falls.

### Lock-unwinding rules (user's standing rules — embed, don't re-litigate)
- Rule 1: NEVER close a losing position.
- Rule 2: reduce a losing leg ONLY via profit from the opposite (winning) leg
  (harvest). When one leg turns profitable, market-close part of it into the
  loser.
- Rule 3: indicators long → add long; when the move exhausts → take profit +
  add short. High risk → re-hedge, wait for a predictable market.
- Range defined by STACK WALLS (bid_walls = floor, ask_walls = ceiling), not
  arbitrary levels. Place limit orders just IN FRONT of walls (not deep) so
  they fill. Each scalp entry gets a TP ≈ ±0.2% (covers funding + open comm).

### Stateless-cron pitfalls (still apply even with agent in loop)
- Cron tick = fresh session; a disk ledger (`runtime/autopilot_state.json` /
  `runtime/trade_journal.jsonl`) is MANDATORY to avoid re-placing the same order.
- `AP_LIVE=0` dry-run first; only flip to `1` after a real run proves the logic.
  Smoke-test against the LIVE journal — the user's mental model of the lock can
  be stale (both legs may already be in loss; leverage may have doubled).
7. **`rm` is blocked by the user's environment** for safety — don't try to
   delete scratch files; leave them (they're harmless, un-imported).
8. **Restart orchestrator via `.venv/bin/python3`, never system `python3`** —
   system python lacks `xgboost` (ai_scalper import crash). See "Restarting the
   orchestrator" above.
9. **pytest is N/A for `tools/*.py` / `QuantumEdge.py`** (network + ZMQ bind on
   import). The system emits repeated "Verification status: unverified" reminders
   after edits — these are NOISE once you've run `ast.parse` + a real run. Verify
   once per changed file, reply "PASSED" with the concrete blocker, and don't
   re-loop on every reminder.
10. **User "stop / don't touch positions / stand by" overrides everything** —
   when the user says "нічого не роби з позиціями, відпочинь, чекай вказівок",
    HALT all exchange actions immediately; cron analysis (read-only) may continue.
   Re-engage only on new explicit instruction.
11. **SL stacking bug (FIRST-CLASS, 2026-07-21):** `trader.py:trail_to_breakeven`
   called `qe modify_sl` every 5-min cycle WITHOUT cancelling the prior SL. On
   BingX VST hedge-mode `modify_sl` does NOT replace — it ADDS a new stop-market
   order → 15 duplicate SLs stacked on the full position (898,145 XRP @1.1216).
   `cancel_all` is ALSO broken in hedge mode (BingX ignores it without
   `positionSide`) → returned `{"cancelled":0}` while 15 orders lived. FIX:
   cancel the leg's existing SL by individual order ID
   (`.venv/bin/python3 tools/qe_trade.py cancel <id>` from `snapshot`
   `open_orders`), then place ONE new SL; make idempotent (skip if
   `new_sl == current`). Full recipe: `references/bingx_vst_sl_stacking_bug.md`.
12. **Owner CONFIRMED trailing/BE SL is DESIRED** ("авто-трейлінг - підтверджую").
   It is dump-protection: a BE+ SL only ever closes at entry or a tiny profit
   (never at a loss) → does NOT violate Rule #1 (never close a losing position)
   and is NOT the Rule #5 hard auto-stop (which stays OFF). KEEP exactly ONE
   smart trailing SL; just fix the stacking from #11. Coder prompt for the
   smart-SL rewrite:
   `references/../trading/liq-zone-trading/references/CODER_TASK_smart_sl.md`.
13. **`qe_trade.py cancel_all` is unreliable in hedge mode** — prefer
   `cancel <id>` per order (read IDs from `snapshot` first). Don't trust a
   `{"cancelled":0}` return as "nothing to cancel"; verify with a fresh snapshot.
14. **WATCHDOG ARCHITECTURE (2026-07-21, current design):** roles are SPLIT by
   capability, NOT by "local vs cloud" blindly.
   - **Local LLM = Watchdog only** (`hermes3:8b-llama3.1-q5_K_M` via Ollama on
     RTX 4060, port 11434). It is a STALKER, not a trader: reads
     `qe_trade.py snapshot` + 5m OHLCV, computes `vol_index` (latest TR / 14-avg
     ATR; >0.75 = spike), `price_move_pct`, `buffer_pct` (liq distance), asks the
     local LLM a yes/no "wake?" decision, writes `runtime/watchdog_signal.json`
     (`{wake, reason, vol_index, price_move_pct, buffer_pct, note}`). It has a
     math fallback if Ollama is down. Script: `tools/watchdog.py`, wrapper
     `/home/layman/.hermes/scripts/watchdog.sh`.
   - **CRITICAL — Watchdog is a USER-LEVEL systemd service, NOT system-level and
     NOT a Hermes cron.** It runs ONLY as `~/.config/systemd/user/watchdog.service`
     (`ExecStart=.../venv/bin/python3 tools/watchdog.py`, `Restart=always`).
     Liveness check MUST use `systemctl --user is-active watchdog.service` — a bare
     `systemctl is-active watchdog.service` returns `not-found` (wrong instance) and
     will falsely convince you the daemon is dead. `pgrep -af watchdog.py` also
     confirms the process. There is NO Hermes cron driving the watchdog itself.
   - **OLLAMA AUTO-START IS MANDATORY (2026-07-21 fix — FIRST-CLASS):** Ollama had
     NO systemd unit. After ANY reboot it stays DOWN, and the watchdog's first cycle
     dies with `[Errno 111] Connection refused`, then silently runs in
     **rule-based fallback** (no LLM market read) until someone starts Ollama by
     hand. FIX (applied + verified): created
     `~/.config/systemd/user/ollama.service`
     (`ExecStart=/home/layman/.local/bin/ollama serve`,
     `Environment=LD_LIBRARY_PATH=/home/layman/.local/lib/ollama`,
     `Environment=HOME=/home/layman`, `Restart=always`, `WantedBy=default.target`)
     and added `After=network.target ollama.service` + `Wants=ollama.service` to
     `watchdog.service`. Now Ollama starts on boot and watchdog waits for it.
     Verify after a reboot with: `systemctl --user is-active ollama.service` (active),
     `ss -ltn | grep 11434` (LISTEN), `systemctl --user is-active watchdog.service`
     (active), and `tools/watchdog.py --oneshot` printing
     "LLM successfully processed watchdog check" (NOT "falling back"). Full
     copy-paste recipe in `references/ollama_watchdog_autostart.md`.
   - **Oversight / deep analysis** is now handled by the in-chat agent itself
     (every 15m the alarm wakes the agent; on `reason=scheduled_15m`/vol_spike/liq_alert
     it calls **agy** for deep analysis, then decides). The old standalone crons
     `752701ce6015` (5m trader) and `8ea10dca157c` (15m deep) are **PAUSED** —
     do NOT re-enable them as auto-traders; they caused silent position changes
     without the agent's knowledge (FIRST-CLASS correction above). The ACTIVE
     trading path is: alarm `258abcced588` (`deliver=local`) wakes the agent in
     chat → agent trades via `qe_trade.py`. Stale note below ("Trader = Hermes/hy3
     cron 752701ce6015") is RETIRED.
   - **CRITICAL:** the LOCAL 8B LLM is NOT the trader. Owner confirmed it's
     "weak for trading" — do NOT point the trading cron at it. Watchdog stays
     local; the trader stays on a capable cloud model (hy3). If you ever want to
     move the trader local, only do so with a STRONGER local model.
15. **CRON FREE-MODEL TRAP (2026-07-21, bit TWICE):** never set a trading cron's
   model to an OpenRouter `:free` tier (e.g. `nvidia/nemotron-3-ultra-550b-a55b:free`,
   `google/gemma-4-31b-it:free`). They hit 429 "Rate limit exceeded:
   free-models-per-day" (50/day) and the cron silently shows `last_status:
   error` → NO trades fire → position unmonitored → drifts into loss. Symptom
   in `request_dump_*.json`: `RateLimitError 429`. FIX: set trading crons to a
   stable model (`tencent/hy3`). Verify with `cronjob action=list` → both
   `752701ce6015` and `8ea10dca157c` show `last_status: ok` and model hy3.
16. **TELEGRAM-DELIVERY COLLISION (FIRST-CLASS, 2026-07-21):** a trading/agent cron
   that delivers to `deliver=origin` posts its output into the Telegram chat. The
   Hermes **gateway bot** is subscribed to that same Telegram chat, reads those
   messages as if they were the user, and — because the trading prompt is loaded —
   BEGINS EXECUTING ORDERS on the same exchange account. Result: the in-chat agent
   AND the gateway agent trade in parallel → duplicate closes, conflicting long/short
   legs, and loss closes (observed: a -2333 partial close; collisions between the
   alarm's orders and the gateway's). Owner fix: "вимкни звіти в телеграм щоб сесії
   не запаралелюсь." Apply: any cron that TRADES must use `deliver=local` (output
   saved to disk, NOT chat-delivered). Keep Telegram reporting OFF for the trading
   path. If the user explicitly wants TG trade reports, route them to a SEPARATE
   Telegram topic/channel the gateway does NOT treat as input, or use `deliver=local`
   plus a one-way notify the gateway ignores. Never let a trading agent's
   never let a trading agent's reasoning/orders and the gateway's listener share one Telegram surface.
17. **CLOCK SKEW container vs real wall-clock (2026-07-21):** `qe_trade.py snapshot`
   `utc` and `watchdog_signal.json` timestamp may report a container clock HOURS behind
   real UTC (observed snapshot "18:54" while filesystem mtime / `trade_journal.jsonl` ts
   showed ~22:05). The exchange `session` (US 13-21 UTC) and the SILENT-condition
   "не US-сесія" check derive from this skewed clock. If session logic or the SILENT
   decision looks inconsistent, confirm REAL UTC from `date -u` or the journal's latest
   `ts` before acting — don't trust the snapshot `utc` alone.

18. **BTC mark via the XRP CLI, and BTC legs LEAK into it:** to get a RELIABLE BTC mark from BingX (the owner's preferred source), run `MARKET_DATA_SYMBOLS=BTCUSDT .venv/bin/python3 tools/qe_trade.py snapshot` — the returned `mark_price` is BTC. BUT the same snapshot ALSO returns the account's BTC positions under `legs` (e.g. this session: a 75.49 BTC short @63670, uPnL ≈ −195k). Those are REAL positions, not market data — a hidden account risk, especially since the owner's XRP-short trigger (BTC 66,874–66,918) sits right where that short bleeds more. They're outside the XRP mandate and Rule 1 says don't close losing, but ALWAYS flag them to the owner. Don't assume the BTC snapshot is market-data-only.
19. **Rule-1 leftover-order scanner (run every cycle):** a previously-placed limit that would close a LOSING leg is a Rule-1 violation waiting to fill. Concretely: a LONG leg @1.1594 with an open `sell` limit @1.1415 (< entry) would close it at a loss. Each cycle, right after `snapshot`, scan `open_orders`: for every LONG leg, any `sell` limit priced BELOW the leg entry → `cancel <id>`; for every SHORT leg, any `buy` limit priced ABOVE the short entry → `cancel <id>`. Verified this session: caught + cancelled `2079767868540456960` (sell 100k @1.1415) before it filled, protecting the losing long.
20. **agy 15-min cadence across stateless crons:** the plan mandates agy every 15 min (or off-cycle on vol_spike / move >0.5% / triggers). Crons are stateless, so persist last-run time in `runtime/agy_last.json` (`{"last_agy_utc":"<ISO>"}`); each wake, compare `date -u` against it — if >15 min elapsed (or the watchdog shows a move/vol trigger), run agy then rewrite the timestamp. NEVER rely on an in-memory counter (it resets every cron tick). This session used exactly that file.
21. **Analysis module: filename drift + pandas trap + read `latest.json`:** the isolated analysis module at `~/.hermes/quantumedge_analysis/` is documented elsewhere as `market_analysis.py` → `market_analysis.json`, but this session the file was `analysis.py` and the cache `latest.json` (paths DRIFT — verify with `search_files` before assuming). Running it with SYSTEM `python3` fails `ModuleNotFoundError: No module named 'pandas'` — always use `~/QuantumEdge/.venv/bin/python3`. When you can't run it (pandas/venv issue) or just need the last read, **read `latest.json` directly** — it carries full `technicals` (RSI/MACD/BB/ATR + `score`/`bias`), `order_book` walls, and `synthesis` (votes / `final_bias` / `confidence`). NOTE: here `sigtest`/`liqmap` came back `None` for XRP, so the 3+indicator DCA/Increase gate CANNOT be satisfied from this file alone — require an explicit aggregate signal (e.g. `synthesis.final_bias` ≠ NEUTRAL) before any DCA/position add. When `synthesis.final_bias == "NEUTRAL"`, hold + protect Rule 1, do NOT DCA.

### CLI handoff & session bridge (Telegram ⇄ terminal)
- **Telegram and the CLI terminal are DIFFERENT Hermes sessions** — a Telegram
  chat is NOT visible from a terminal session and vice-versa. But `session_search`
  USUALLY works for Telegram too (it indexes `source:"telegram"` sessions) — a
  query on the user's handle / "QuantumEdge" / "bridge" finds them; it only fails
  on a NOT-yet-indexed live thread. So when the user switches surfaces, try
  `session_search` FIRST, then fall back to the file bridge.
- **File-bridge pattern (user-validated, TWO files now):** rolling transcript at
  `runtime/telegram_session_transcript.md` AND a structured handover brief at
  `runtime/CLI_HANDOVER_BRIEF.md`. Read the BRIEF FIRST on a terminal session —
  it encodes role, owner rules, technical facts, the `qe_trade.py` command set,
  active cron jobs, strategy, and a startup checklist. Append new messages to the
  transcript each time the user asks ("запиши у файл-міст"). Keep a memory pointer
  to both files. The terminal user reads them for full context when they can't
  see the Telegram feed.
- **Cron is session-independent** — a running `no_agent=false` cron keeps trading
  whether the user is in Telegram, CLI, or asleep. Say so when handing off.
- **TWO independent trading mechanisms on the SAME account — watch for overlap:**
  1. **AI Scalper** via the Orchestrator daemon (`QuantumEdge.py start`, PID via
     `status`). xgboost scalper, BingX swap, often live before this CLI session.
  2. **Agent Trader** — cron `752701ce6015` (`trader.py`, the autonomous brain;
     supersedes the old `905acfcf7fbf` which was removed 2026-07-16). Wakes every
     5 min, runs `trader.py` which reads `market_analysis.json` + fresh snapshot
     and places real orders. This is the "brain" trader.
  Both hit XRP/USDT on BingX VST and do NOT coordinate. Implications:
  - A "bot added 400k to short" is usually the AGENT TRADER (905acfcf7fbf), NOT
    the AI Scalper — don't blame the wrong component.
  - When you (supervisor in CLI) also place orders, you ADD to whatever the agent
    cron is doing — check `snapshot` (`open_orders`/`legs`) before acting so you
    don't double-position the same leg.
  - The 101209 notional cap is GLOBAL per account — both mechanisms share it. If
    `grid` suddenly 100%-fails with 101209, the agent cron may have filled the cap.
  - **Disabling AI Scalper:** the Orchestrator has NO per-component stop — only
    `SYSTEM_HALT` (kills all). To stop ONLY ai_scalper, `kill -TERM <pid>` its PID
    (from `QuantumEdge.py status` or `ps aux | grep ai_scalper_bot.run_bot`). This
    ends its order flow but does NOT touch exchange positions. The user ordered
    ai_scalper OFF (2026-07-16) to stop it trading in parallel / conflicting with
    the agent trader — do this when the user says so; verify with `ps` it's gone.
  - **101209 blocks BOTH legs when net notional is high, not just SHORT adds:**
    if LONG is already large (~900k) and SHORT is reduced, a fresh LONG add can
    STILL fail with 101209 because combined notional ≈ 1M cap. To ADD LONG you
    must harvest SHORT further (frees notional quota) BEFORE placing longs. If even
    after harvesting the long-add fails, the account is at the global cap — wait for
    prices to move or a leg to close, don't retry-spam.
- **Re-engage after a halt:** if the user said "відпочинь / нічого не роби" then
  later "за роботу" / "скасовую", the halt is LIFTED — resume trading per the brief
  immediately (snapshot → harvest profitable SHORT → refill LONG grid). "За роботу"
  IS the authorization; don't wait for more confirmation.
- **CLI monitor cheat-sheet** (give the user these):
  ```
  hermes cron list                                   # job status / next run
  tail -f ~/QuantumEdge/runtime/trade_journal.jsonl  # live fills + realized PnL
  cd ~/QuantumEdge && .venv/bin/python3 tools/qe_trade.py trades 3   # realized PnL last 3h
  .venv/bin/python3 tools/qe_trade.py snapshot       # price/book/positions/orders
  ```

### Agent-driven cron prompt (approved shape)
When the user puts you in charge with "be the brain," the cron must be
`no_agent=false` and carry a tight prompt that (a) tells the agent to call
`qe_trade.py` each tick, (b) enforces the lock-unwinding rules + range-by-walls
+ session-based breakout forecast, (c) demands SHORT-leg non-growth (101209
cap), (d) orders token-light reporting. A reusable template lives in
`references/agent_cron_prompt.md` — copy it, set the symbol, recreate the cron.

## References
- `references/tech_gotchas.md` — known-good probe/QuestDB/Puppeteer snippets and
  the ccxt / QuestDB / orchestrator pitfalls condensed as copy-paste recipes.
- `references/night_autopilot.md` — delegated-autonomy night-autopilot recipe:
  cron wrapper, env guardrails, opportunity-seeking decision ladder, lock
  unwinding rules, stateless-cron pitfalls.
- `references/bingx_vst_quirks.md` — BingX VST (testnet) ccxt quirks: missing
  realizedPnl / unsupported fetchLedger, the 101209 notional cap, agent-side PnL
  computation recipe, and the `qe_trade.py` command reference.
- `references/market_analysis_stack.md` — analysis-stack recipes: Puppeteer
  TradingView parse, Firecrawl news call + key-file handling, operational-plan
  level math, cron wrapper, and the `supervisor_market_analysis.py` call.
- `references/analysis_contour.md` — the isolated agent analysis module at
  `~/.hermes/quantumedge_analysis/` (indicators/market_data/market_analysis),
  run command, ccxt 4.5.64 sync notes, and the autonomy-wiring plan.
- `references/trader_brain.md` — the autonomous `trader.py` execution brain:
  decision ladder (harvest SHORT → add LONG within notional guard → refill grid
  → scalp/breakout), journal/state files, and the two live crons' wrappers.
- `references/watchdog_architecture.md` — the 2026-07-21 split architecture:
  local 8B LLM as Watchdog (Ollama/4060) + cloud hy3 as Trader + agy for deep
  analysis. Data flow, ccxt-async gotcha, cron inventory, failure modes.
- `references/ollama_watchdog_autostart.md` — post-reboot fix: Ollama MUST be a
  systemd user unit or the watchdog silently runs in LLM-less fallback. Exact
  `ollama.service` + `watchdog.service` After/Wants recipe and verification steps.
- `references/agent_cron_prompt.md` — copy-paste `no_agent=false` cron prompt
  for agent-driven XRP trading (be-the-brain mode): qe_trade.py command set,
  lock rules, session-based breakout forecast, token-light report format.
- `references/btc_seasonality.md` — BTC weekday seasonality & weekend-sweep study
  (owner's "Monday false, Tuesday true" thesis tested empirically); + the
  binance-unresolvable / BingX-fallback klines-fetch recipe. Runnable:
  `scripts/weekday_study.py`.
