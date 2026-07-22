# Trader Brain — trader.py (autonomous execution)

Built 2026-07-16 to replace the old `no_agent` script-cron (which made zero
profit because the agent never woke to read the book / harvest). This is the
ACTIVE trade loop the 5-min cron `752701ce6015` calls.

## Files (all under ~/.hermes/quantumedge_analysis/)
- `trader.py` — the brain. `run()` (or `--deep`) → `analyze()` from
  `market_analysis.py` → `decide_and_act()` → real orders via `qe_trade.py`.
- `trader_journal.jsonl` — every action logged (HARVEST_SHORT, ADD_LONG,
  GRID_LONG, SCALP_LONG, BREAKOUT_UP, CYCLE, HOLD). `tail -f` to watch live.
- `trader_state.json` — `cycle`, `realized_pnl`, `trades`, `wins`, `last_bias`.
- `market_analysis.json` — verdict consumed by `decide_and_act` (bias,
  conviction, levels, trend_shift, manipulation, btc_analysis).

## Decision ladder (decide_and_act)
1. Pull fresh `qe_trade.py snapshot` (legs, open_orders, free margin).
2. Compute `room_contracts` from 1M USDT notional cap — CLAMP every LONG add.
3. If SHORT in profit (price < short_entry, uPnL > 0):
   `market buy SHORT` (harvest ~15%) → free margin → `place buy LONG`
   (~= harvested qty, within room) at price*0.999, TP +0.2%. (Lock Rules 2/3.)
4. Refill LONG grid: 3 `place buy LONG` steps below `support_book`, qty
   `min(50000, room_contracts//3)`, only if `room_contracts > 10000`.
5. Scalp LONG if conviction ≥0.6 and `room_contracts > 50000`.
6. `--deep` (15m cron `51a8fe4fba50`): add breakout orders just outside BB
   (buy LONG above BB_upper; sell SHORT below BB_lower only if short small).
7. MM manipulation HIGH + low conviction → HOLD (don't walk into spoof trap).

## Hard guards (do not remove)
- Never `market sell LONG` in loss (Lock Rule 1).
- Never add to SHORT (101209 cap) — SHORT is harvest-only.
- Harvest FIRST, then add LONG (frees notional quota).
- Log EVERY action to `trader_journal.jsonl` (so PnL is auditable).

## Known gap (fix when touching this file)
SHORT-harvest PnL is not written as a `close` record, so `trader_state`
realized_pnl reads 0. Compute `realized=(short_entry-price)*qty` inline and
append a `close` entry after each HARVEST_SHORT to make rollup truthful.
