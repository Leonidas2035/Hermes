# BingX VST (testnet) ccxt quirks & workarounds

Condensed from a live trading session. The testnet (`USE_TESTNET=true`,
`BINGX_TESTNET_API_KEY/SECRET`, `set_sandbox_mode(True)`, symbol `XRP/USDT:USDT`)
behaves differently from docs — capture the fixes, don't re-discover them.

## 1. No realized PnL from the exchange (compute it yourself)
`fetch_my_trades` returns objects whose `info` has
`filledTm, volume, price, amount, commission, positionSide, ...` but **no
realizedPnl / realisedPnl field**. `fetchLedger(...)` raises
`bingx fetchLedger() is not supported yet`.

So: read the leg's `entryPrice` via `fetch_positions` BEFORE closing, get mark
from `fetch_order_book`, and compute realized PnL yourself. Persist to a journal
(`runtime/trade_journal.jsonl`) — never trust the exchange field.

```python
# in tools/qe_trade.py market(), before create_order:
await ex.load_markets()
ps = await ex.fetch_positions(symbols=[CCXT_SYMBOL])
entry = None
for p in ps:
    if str(p.get("side","")).upper() == pos_side.upper() and float(p.get("contracts") or 0)!=0:
        entry = float(p.get("entryPrice") or 0)
ob = await ex.fetch_order_book(CCXT_SYMBOL, limit=5)
bids, asks = ob.get("bids",[]), ob.get("asks",[])
mark = (bids[0][0]+asks[0][0])/2 if bids and asks else None
# after create_order:
if pos_side.upper()=="LONG":
    realized = round((mark-entry)*float(qty), 4)
else:  # SHORT closed by buying
    realized = round((entry-mark)*float(qty), 4)
```

Then `trades <hours>` reads the journal (not the exchange) for realized PnL.

## 2. Error `code 101209` — max position value / notional cap
When adding to a leg, BingX returns:
`{"code":101209,"msg":"The maximum position value for this leverage is 1000 @ 1.1141"}`
at the current 10x leverage, the SHORT leg has hit its size limit (~890k XRP).
Implication: **you CANNOT add to SHORT — only reduce it** (buy-to-cover) when in
profit. Build the grid ASYMMETRIC: keep adding LONG on dips (TP +0.2%), only
HARVEST the SHORT in profit. Don't retry SHORT adds; they will keep failing.

## 3. `qe_trade.py` command reference (agent's preferred interface)
Run from `/home/layman/QuantumEdge` with `.venv/bin/python3`.
- `tools/qe_trade.py snapshot` → price, book (±20 + wall clusters + imbalance),
  balance, legs, open_orders, **session** (ASIA/EU/US by UTC hour).
- `tools/qe_trade.py place <buy|sell> <LONG|SHORT> <qty> <price> [tp]`
- `tools/qe_trade.py market <buy|sell> <LONG|SHORT> <qty>`  (self-computes PnL)
- `tools/qe_trade.py cancel_all` | `cancel <id>`
- `tools/qe_trade.py grid <lo> <hi> <n_side> <qty>` — n_side buy-limits below mid
  (TP+0.2%) + n_side sell-limits above (TP−0.2%) + 2 breakout orders each edge.
- `tools/qe_trade.py trades <hours>` — realized PnL from the journal.

## 5. Modifying a Stop-Loss on BingX VST hedge-mode (cost real cycles this session)
Three traps, all hit live:
- **`ccxt.bingx` has NO `edit_position` method** — calling it raises `AttributeError`,
  so a first-try `edit_position` branch dies and falls through to a buggy fallback.
- **`reduceOnly: True` is REJECTED** in hedge mode:
  `code 109400 "In the Hedge mode, the 'ReduceOnly' field can not be filled."`
  → drop it from params entirely.
- **Correct life-cycle (cancel + recreate):** fetch_positions → get real
  `qty = float(pos["contracts"])` → fetch_open_orders → cancel any existing
  SL/trigger order for that `positionSide` (filter `type in ("stop","trigger")`
  OR `info.stopLossPrice` / `info.triggerPrice`) →
  `create_order(symbol, type="market", side=OPPOSITE, amount=qty,
  params={"positionSide":..., "stopLossPrice": new_sl})`.
  A fallback that used `amount=0.0` is rejected ("minimum amount precision of 1").
  The cancel+recreate path with the REAL position qty is the only working one.
  Implemented in `tools/qe_trade.py set_sl`.

## 6. Autonomous skills-based short-entry daemon (built this session)
Pattern for "watch an open LONG, auto-open SHORT hedge when indicators flip":
- `tools/xrp_short_watch.py` — 5-min loop. Each tick: live OHLCV from BingX →
  `sigtest.indicators.enrich` (EMA/RSI/MACD/OBV/ADX/BB/ATR) + `liqmap.model`
  (heatmap → near liquidation zones ≤2%). Entry rule (owner's standing logic):
  **3+ indicator votes in one direction AND a liquidation zone in that same
  direction within 2% → place order with TP=zone, wide SL (≈5%, gap protection,
  NOT an active tight stop per Rule 5).**
- Trail-to-BE: move SL to entry±0.05% only when `uPnL>0` AND price moved ≥0.3%
  (safe distance), AND indicators NOT showing reversal (RSI>70/MACD<0 for long).
  Hold a LONG until indicators show overbought/reversal OR price hits the
  liquidation zone (TP). Never auto-close a losing position (Rule 1).
- The daemon calls `tools/qe_trade.py` (`place` / `market`) to execute — runs as a
  background process; writes a jsonl watch-log. Real orders on VST demo per the
  owner's "act autonomously, open/close by setup" directive.

## 7. When debugging a stubborn bug, DELEGATE to the coder (FIRST-CLASS correction)
User: "Якщо завдання важке, просто опиши проблему та склади промпт, кодер швидко
тобі все зпрограмує." When looping on a small bug (rotation counter, malformed
path, API param), STOP hand-fixing. Write a self-contained `CODER_TASK_*.md` in
`references/` with: exact file paths, the observed failure (paste real traceback/
output), desired behavior, acceptance criteria (pytest + a real run), and the
standing rule "no fabricated data." The user prefers this over agent thrashing.

