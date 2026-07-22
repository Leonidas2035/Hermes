# BingX VST Hedge-Mode SL Stacking Bug (learned 2026-07-21)

## Symptom
The autonomous trader (`~/.hermes/quantumedge_analysis/trader.py`) runs every 5 min.
Its `trail_to_breakeven()` called `qe(["modify_sl", "LONG", str(new_sl)])` each
cycle WITHOUT cancelling the previous SL. On BingX VST hedge-mode this does NOT
update the existing stop — it CREATES A NEW stop-market order. Result: a stack of
15 duplicate SL orders accumulated on the full position size (898,145 XRP @1.1216),
all `sell market`. Visible in `trade_journal.jsonl` as a repeated `modify_sl` series
(2026-07-21 11:14→12:11) and in `qe_trade.py snapshot` as `open_orders_count: 15`.

## Why it happens (BingX hedge-mode quirks)
- `ccxt.bingx` has NO `edit_position()` → AttributeError if called.
- `reduceOnly: True` is REJECTED in hedge mode → `109400 "In the Hedge mode, the
  'ReduceOnly' field can not be filled."` So you cannot modify a SL via reduce-only.
- `qe_trade.py modify_sl` works by `create_order(type="market", side=sell-for-LONG,
  params={"stopLossPrice": X, "positionSide": "LONG"})` (NO reduceOnly) — this
  ADDS a new SL trigger every call; it never replaces.
- **`cancel_all` is ALSO buggy in hedge mode** — BingX ignores `cancel_all_orders`
  without `positionSide`, so `qe_trade.py cancel_all` returned `{"cancelled": 0}`
  while 15 orders were live. Must cancel by individual order ID with `positionSide`.

## Working cleanup (verified)
Cancel each SL by ID (the IDs come from `snapshot()["open_orders"]`):
```bash
cd /home/layman/QuantumEdge
.venv/bin/python3 tools/qe_trade.py cancel <order_id>   # works per-ID
# snapshot open_orders_count must go to 0; the POSITION itself is untouched
```
Position legs are NEVER touched by `cancel` — only the orders. Safe.

## Owner's stance on trailing SL (IMPORTANT — not a violation of Rule #5)
The owner CONFIRMED auto-trailing / breakeven SL is DESIRED ("авто-трейлінг -
підтверджую"). It is NOT a hard risk-management stop (Rule #5 auto-stop stays OFF
per owner will). A BE+ SL only ever closes the position at entry or a tiny profit
(never at a loss), so it does NOT break Rule #1 ("never close a losing position").
It is a dump-protection: if XRP dumps below entry, the SL fixes zero/tiny-profit
instead of sitting in a deficit. So: KEEP a single smart trailing SL; just fix the
stacking bug so there is exactly ONE at a time.

## Fix pattern for the code (coder task)
Before placing a new SL for a leg, find & cancel that leg's existing SL order by ID
(read `open_orders`, match `positionSide` + stop type). Then place the new one.
Make it idempotent: if `new_sl == current_sl`, do NOT cancel+place (avoid per-cycle
spam). See
`~/.hermes/skills/trading/liq-zone-trading/references/CODER_TASK_smart_sl.md` for
the full coder prompt (smart trailing SL: BE+ floor, ATR trail, manip-hold,
reversal-tighten, gap buffer).
