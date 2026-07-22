# BingX swap — modifying / setting a Stop-Loss (hedge-mode pitfalls)

Condensed from a live session. These are NOT in ccxt docs clearly.

## What does NOT work
1. **`ex.edit_position(...)` does not exist on `ccxt.bingx`.**
   Calling it raises `AttributeError` → falls through to any fallback. Do not rely on it.
2. **`reduceOnly: True` is REJECTED in hedge mode.**
   BingX returns: `{"code":109400,"msg":"In the Hedge mode, the 'ReduceOnly' field can not be filled."}`
   So a stop-order created with `params={"reduceOnly": True}` fails. Omit it — in
   hedge mode a SELL for a LONG (or BUY for a SHORT) already reduces the position.

## Working pattern (cancel + recreate stop)
```python
async def set_sl(ex, pos_side, new_sl):
    await ex.load_markets()
    ps = await ex.fetch_positions(symbols=[CCXT_SYMBOL])
    pos = next((p for p in ps
                if p.get("side","").upper()==pos_side.upper()
                and float(p.get("contracts") or 0) > 0), None)
    if not pos:
        return {"modified": False, "error": f"no open position for {pos_side}"}
    qty = float(pos["contracts"])          # REAL position size, not 0
    # 1) cancel existing SL/trigger orders for this side
    oo = await ex.fetch_open_orders(CCXT_SYMBOL)
    for o in oo:
        info = o.get("info", {})
        is_sl = o.get("type") in ("stop","trigger") or \
                bool(info.get("stopLossPrice") or info.get("triggerPrice"))
        if is_sl and info.get("positionSide","").upper()==pos_side.upper():
            try: await ex.cancel_order(o["id"], CCXT_SYMBOL)
            except Exception: pass
    # 2) create new stop as a market order with stopLossPrice
    sl_side = "sell" if pos_side.upper()=="LONG" else "buy"
    params = {"positionSide": pos_side.upper(), "stopLossPrice": float(new_sl)}  # NO reduceOnly
    o = await ex.create_order(symbol=CCXT_SYMBOL, type="market", side=sl_side,
                              amount=qty, price=None, params=params)
    return {"modified": True, "new_sl": new_sl, "qty": qty}
```
- `amount` MUST equal the full position size (a `0.0` amount is rejected:
  "must be greater than minimum amount precision of 1").
- A wide SL (e.g. entry*1.05 for short / entry*0.95 for long) is a *gap hedge*,
  not a tight active stop — matches the owner rule "auto-stop disabled".

## Where this lives in QuantumEdge
`tools/qe_trade.py` → `set_sl(ex, pos_side, new_sl)` (BingX VST hedge-mode).
Called by `tools/xrp_short_watch.py` (autonomous 5-min swing-trader daemon) and
`trader.py` `trail_to_breakeven()` (moves SL to breakeven at +safe_dist).
