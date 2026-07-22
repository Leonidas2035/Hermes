# Autonomous Trader Quirks (ccxt 4.5.x + BingX VST + multi-cron)

Concrete, reusable gotchas from running an autonomous XRP/USDT trader on
BingX VST (testnet) via ccxt. Save hours next session.

## ccxt 4.5.x API SHAPE (different from old tutorials)
- `ex.load_markets()` and `ex.fetch_ticker(sym)` and `ex.fetch_ohlcv(sym, tf, limit=N)`
  return **sync** values (dict / list), NOT coroutines. Do NOT `await` them.
  Only `ex.fetch_balance / fetch_positions / fetch_open_orders / fetch_funding_rate
  / fetch_open_interest` are awaited. If you see `TypeError: object dict can't be
  used in 'await' expression`, drop the await.
- `ex.close()` in sync mode returns None → don't `await ex.close()`.
- `set_leverage(lev, symbol, params={'side':'LONG'|'SHORT'})` — side is REQUIRED
  as a param, not positional. Wrong call → "requires a side argument".
- `private_post_*` helpers don't exist on the ccxt bingx class in 4.5.x; use the
  public `set_leverage` / `create_order` wrappers.

## BingX VST hard limits (surface as ccxt error codes)
- **101209** "The maximum position value for this leverage is 1000000 USDT" →
  notional cap. At 10x, a ~904k-contract long @ ~1.10 ≈ 995k USDT is AT the cap.
  Compute `room_contracts = int((SAFE_NOTIONAL - long_size*price)/price)` and
  NEVER place a long that exceeds it. SAFE_NOTIONAL ~ 900k (100k buffer).
- **101201** "position value too large, leverage must be lower than 5x" → you
  CANNOT raise leverage (e.g. to 20x) while a large position exists. Raising
  leverage requires first shrinking the position (which conflicts with owner
  rule #1: never close a loser). So: keep 10x, don't promise higher leverage.
- **liquidationPrice** often comes back `None` from ccxt on VST. Compute
  manually: `liq_long ≈ entry * (1 - 1/lev * 0.95)`; distance% = (price-liq)/price*100.
  Alert/hedge when distance < 1–3%.

## Multi-cron state sharing (THE big bug)
- Two crons (5-min trade + 15-min oversight) write the SAME account but have
  separate LLM contexts. The 15-min "deep" run executed a BREAKDOWN_SHORT that
  the 5-min run never logged → short grew unnoticed for cycles.
- FIX pattern: `trader_state.json` holds last seen long/short size. Every cycle
  (both crons) reads it, compares to live `fetch_positions`, logs ANOMALY if a
  side changed without this cycle's own action. This catches cross-cron drift.
- Keep a single source of truth for "what is the current plan" (e.g.
  `trader_plan.md` or a `plan_gate` field) that the 15-min oversight writes and
  the 5-min trader reads. Risky adds (short add, breakout short) are gated on it.

## Architecture that worked (Hermes workspace, isolated from bot code)
`~/.hermes/quantumedge_analysis/`
- `indicators.py` — RSI(14)/MACD(12,26,9)/Bollinger(20,2)/ATR(14) via `ta` lib
  + `trend_score` (-3..+3 → LONG/SHORT/NEUTRAL). Pulled from the old BTC
  pipeline (`monitor_adjust.py`) and REWIRED to XRP — don't leave indicators
  orphaned in dead scripts.
- `market_data.py` — all collection from the exchange directly (klines, funding,
  OI, order book, BTC context, TV via Scanner API, Google News RSS). Does NOT depend
  on QuestDB/MarketDataHub daemon, so analysis works even if the daemon is down.
- `market_analysis.py` — "shark" analysis: early trend-shift detection (MACD
  hist flip, BB squeeze, RSI divergence, swing structure), order-book
  manipulation detection (spoofing >4x avg wall, wall-clusters, imbalance
  extremes, absorption), BTC macro zones (63.6–64.5k correction / >66k breakout).
- `trader.py` — THE BRAIN: runs analysis, decides, places REAL orders via
  `QuantumEdge/tools/qe_trade.py`. Harvests short when in profit, adds long
  within notional cap, hedges with short only when near liquidation.
- `trader_journal.jsonl` — every action logged. `trader_state.json` — cycle
  count, realized PnL, last sizes. `market_analysis.json` / `history/` — reports.

## Report delivery
- Cron `deliver='local'` saves output but does NOT push to Telegram. To reach
  the user, set `deliver='telegram'` (or a gateway platform) OR just print
  concise status into the active terminal session. Keep <=6-10 lines.
