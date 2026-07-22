# Autonomous Decision & Hedge — concrete recipes (QuantumEdge / XRP)

Hard-won detail for the "decide and act" autonomous register. Pair with the
**DECIDE AND ACT** and **Sizing a hedge** bullets in SKILL.md.

## 1. Cross-symbol Composite / Liq-map read (XRP, not BTC)
`tools/composite_signal.cli` and `tools/sigtest.cli` are HARDCODED to
`BTC/USDT:USDT`. The `qe_trade.py` position and the live bot are on **XRP**
(~1.15). A bullish BTC read is TAILWIND AGAINST an XRP short — never imply the
BTC composite applies to the XRP symbol you hold. To read XRP, run inline
Python reusing the engine functions:

```bash
cd /home/layman/QuantumEdge && source .venv/bin/activate
python - <<'PY'
import sys, json
from pathlib import Path
sys.path.insert(0, "/home/layman/QuantumEdge")
import pandas as pd
from tools.liqmap.datafeed import fetch_ohlcv, fetch_oi_history, fetch_context
from tools.liqmap.model import classify_regime, build_heatmap
from tools.composite_signal.engine import calculate_composite_score

SYM = "XRP/USDT:USDT"
ohlcv, src = fetch_ohlcv(timeframe="1h", limit=150, symbol=SYM)
oi_series, _ = fetch_oi_history(timeframe="1h", limit=150, symbol=SYM)
ctx = fetch_context(symbol=SYM)
fr = ctx.get("funding", 0.0)
df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])
regime = classify_regime(ohlcv, len(ohlcv))
res = calculate_composite_score(df, funding_rate=fr, oi_series=oi_series, liq_zones=None)
score = res["score"]
side = "LONG" if score > 10 else "SHORT" if score < -10 else "NEUTRAL"
print("XRP price", round(df.close.iloc[-1],4), "| regime", regime)
print("Composite", score, side)
print("Trend %+.1f  Momentum %+.1f  Vol %+.1f  Flow %+.1f" % (
    res["trend"], res["momentum"], res["volatility"], res["volume_flow"]))
# Liq-map magnets (nearest strong zones)
hm = build_heatmap(ohlcv, price_bins=140, oi_series=oi_series)
last = ohlcv[-1][4]
for z in sorted(hm.get("zones", []), key=lambda z: z["price"]):
    if abs(z["dist_pct"]) <= 6:
        print("  %.4f %+.2f%% int=%.2f %s" % (z["price"], z["dist_pct"], z["intensity"], z["side"]))
PY
```
Zone key is `intensity` (NOT `strength` — that field is absent/zero). `side`
values: `SHORT_LIQ` = magnets above price (short liquidations, upside fuel),
`LONG_LIQ` = below.

## 2. Hedge sizing — read `legs`, NOT `open_orders`
`qe_trade.py snapshot` returns both `legs` (real positions) and `open_orders`.
`open_orders` is dominated by **TP/SL tags**, not resting orders:
- `buy market 700000 @ 1.1442` → the SHORT's stop-loss tag (NOT a 700k buy order).
- `sell market 297502 @ 1.1509` → the LONG's take-profit tag.
- Real resting limit orders show as `buy limit ...` / `sell limit ...`.

**Always size hedge/close decisions from `legs`** (positionSide, size, entry,
uPnL). Pitfall from a live session: snapshot implied short ≈ 297.5k, but
`legs` revealed it was **700k** → hedged only 297.5k, leaving −402.5k still
exposed to an up-trending market. Procedure:
1. Read `legs` → net delta = Σ LONG − Σ SHORT size.
2. Place hedge = |net delta| on the opposite side (e.g. LONG 700k to neutralize
   a 700k short) via `qe_trade.py place buy LONG <qty> <price> [tp] [sl]`.
3. Re-read `legs` to confirm net delta ≈ 0. Report the neutralized state.

## 3. Order syntax (`tools/qe_trade.py`)
Run from project root with `.venv` activated (ccxt lives there, NOT hermes venv).
- `snapshot` → JSON: price, book, imbalance, balance, legs, open orders.
- `place <side> <posSide> <qty> <price> [tp] [sl]` → limit order (side=buy/sell,
  posSide=LONG/SHORT).
- `market <side> <posSide> <qty>` → market order (cover / take profit).
- `cancel_all` / `cancel <id>` / `trades <hours>`.
Real fill returns `"status": "closed"`. Successful hedge prints both legs with
equal sizes.

## 4. Decision logic (owner rules → action)
- Risk signal (indicator against position, liq-magnets pushing into exposure) →
  **hedge + wait** (rule 4). Do NOT close the loser (rule 1). Size hedge to net
  delta from `legs`.
- Indicators bullish in a long → add long (rule 3); exhaustion (RSI>70 /
  MACD_hist<0) → take profit + add short.
- After acting, publish a ≤6–10 line report: bias, action taken, legs state,
  PnL. No questions.
