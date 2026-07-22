# Analysis Contour — ~/.hermes/quantumedge_analysis/

Isolated analysis/decision module for the QuantumEdge XRP/USDT supervisor,
built 2026-07-16. Kept OUT of the bot's working code (`/home/layman/QuantumEdge`)
so it can be improved without touching the trading system. Uses the project's
`.env` (BingX keys) and `.venv` (pandas/numpy/ta/ccxt).

## Files
- `indicators.py` — `compute_indicators(df)` -> RSI(14), MACD(12,26,9),
  Bollinger(20,2), ATR(14) + derived: rsi_zone, macd_state, bb_position,
  atr_pct. `trend_score(ind)` -> {-3..+3, bias LONG/SHORT/NEUTRAL}.
  Expects DataFrame cols: timestamp, open, high, low, close, volume.
- `market_data.py` — collectors (sync-friendly for ccxt 4.5.64):
  `fetch_xrp_klines(interval,limit)` (uses `ex.fetch_ohlcv` — SYNC, no await),
  `fetch_funding_oi`, `fetch_order_book(depth)` (bid/ask walls + imbalance),
  `fetch_btc_context` (BTC ticker+funding+OI + derived xrp_btc),
  `fetch_tv_rating` (Puppeteer tv_parse.js), `fetch_news` (Firecrawl Free Tier).
  `trading_session()` -> ASIA/EU/US by UTC hour.
- `market_analysis.py` — THE SHARK. `run()` builds the full report:
  technicals + `detect_trend_shift` (MACD histogram turn, BB squeeze, RSI
  divergence, swing structure) + `detect_manipulation` (spoofing / wall-cluster
  / absorption / imbalance extremes) + `analyze_btc` (video zones) +
  `trader_verdict` (weighted votes + conviction 0..1; MM-spoof HIGH lowers
  conviction) + `build_levels` (entry/TP1/TP2/SL from BB+ATR + book S/R).
  Prints human summary + writes `market_analysis.json`.
- `market_analysis.json` — latest report (agent reads this).
- `history/ma_*.json` — rolling archive (trimmed to 200).
- `README.md` — structure + how-to.

## Run
```bash
cd ~/.hermes/quantumedge_analysis
~/QuantumEdge/.venv/bin/python3 market_analysis.py
```
Outputs `market_analysis.json` + `history/ma_<ts>.json`.

## ccxt 4.5.64 sync/await (verified this session)
- AWAIT: `load_markets`, `fetch_balance`, `fetch_positions`,
  `fetch_order_book`, `fetch_funding_rate`, `fetch_open_interest`,
  `fetch_open_orders`.
- SYNC (no await): `fetch_ticker` (dict), `fetch_ohlcv` (list of OHLCV rows).
- `ex.close()` -> None (no await).
- BingX swap symbol: `XRP/USDT:USDT`. `set_sandbox_mode(True)` for VST.

## Why isolated
User wanted the agent's analysis OUT of `tools/` so it can evolve as a
"shark/market-maker" without risking the bot. The project's
`tools/supervisor_market_analysis.py` still exists but is superseded for the
agent's own decisions. When the user says "replace the old supervisor script,"
point here.

## Autonomy wiring (pending user A/B on real orders)
- 15-min cron: run `market_analysis.py` -> refresh `market_analysis.json`
  (read-only, safe; same role as the old `edea7528b7d2`).
- 5-min decision loop (agent in loop, `no_agent=false`): read
  `market_analysis.json` + fresh `qe_trade.py snapshot` -> act per lock rules
  (harvest profitable SHORT, refill LONG grid by walls, respect 101209 cap).
- Do NOT `clarify` in this mode — decide and report token-light.
