# Cron post-trade verification recipe (QuantumEdge autonomous trader)

After EVERY `trader.py` run in the 15m deep-cycle, the engine's own report CAN lie
(see trap #6). The live snapshot is ground truth. Run this checklist before
reporting the cycle as "done".

## Commands
```bash
cd /home/layman/QuantumEdge
.venv/bin/python3 tools/qe_trade.py snapshot        # raw JSON, do NOT pipe to json.tool
# cancel a bad order:
.venv/bin/python3 tools/qe_trade.py cancel <order_id>
```

## Checklist (in order)
1. **Net-side flip.** In `legs`, confirm the book did NOT flip `long -> net-short`.
   If a `short` leg appeared and `long` shrank to near-zero, the rule-3 "fix+short"
   path fired. Flag it.
2. **Short notional cap (rule 6).** `short_notional = short_leg.size * mark`.
   MUST be <= 101 209. If over: do NOT auto-reduce (realizes loss = rule 1 conflict);
   flag owner for manual trim; act per rule 4 (hedge + wait).
3. **Anomalous order size (the silent blow-up).** Scan `open_orders`; cancel ANY order
   whose `amt` > 2x the largest `leg.size`, EVEN if its price is inside XRP range
   (~1.0-1.3). The old "cancel if TP>1.3" check MISSES these — a 350k sell-limit at
   1.1445 looks normal but would open a ~310k short on a one-tick uptick.
4. **Cross-symbol TP.** Cancel any order whose price/TP is outside XRP range
   (~1.0-1.3) — that's the BTC tp (~67000) leaking into an XRP order.
5. **Balance diagnostic.** `total` = `free` + `used` (wallet, EXCLUDES uPnL).
   A `total` crash is NOT necessarily realized loss: a pending oversized limit
   RESERVES margin, so `total` can drop tens of thousands with no fill. Re-snapshot
   after cancelling the bad order — `total` recovers. Only trust a drop as real loss
   after the bad orders are gone AND uPnL is separately negative.

## Incident: 2026-07-21 14:27 UTC
- Trigger: `trader.py --deep` while XRP/BTC 1h RSI ~74 (overbought).
- Outcome the engine reported: HARVEST_SHORT_INDICATOR 52500, SL for SHORT,
  SKILLS_LONG, GRID_LONG x3, SCALP_LONG, BREAKOUT_UP.
- Live snapshot revealed instead:
  - LONG gutted 338 330 -> 40 000 @1.143 (uPnL ~0).
  - SHORT 297 502 @1.142 opened (uPnL -266, losing). Notional ~340k = 3.3x cap 101 209.
  - Resting **SELL-LIMIT 350 000 @1.1445** (8x position) — blow-up order.
  - `total` 623 669 -> 571 088 (looked like -52k loss).
- Action: cancelled the 350k sell-limit. Re-snapshot: `total` -> 613 741
  (true ~-10k; the rest was reserved margin under the bad order).
- Left the losing short untouched (rule 1), hedged, no new orders (rule 4),
  reported all flags to owner.
- Lesson: the >1.3 price check was insufficient; size-based scan is mandatory.
