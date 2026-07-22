# BTC weekday seasonality & weekend-sweep study

The owner trades XRP off BTC as the leading indicator and has a standing thesis:
**"Monday moves are deceptive/false; the true move starts Tuesday in the opposite
direction. After the weekend, the weekend range highs/lows get swept."** This file
records how to test that thesis and the empirical result, so you don't re-derive it.

## How to fetch historical klines (exchange fallback — IMPORTANT)
`api.binance.com` is NOT resolvable from this host (`NameResolutionError` /
`Temporary failure in name resolution`). Do NOT hardcode `ccxt.binance` for
history. Use a fallback loop over reachable exchanges — **BingX works** (it's the
project's own exchange) and is the right default; bybit/okx/kraken as backups:

```python
import ccxt
def get_ex():
    for name in ["bingx","bybit","okx","kraken","gateio","kucoin","mexc"]:
        try:
            e = getattr(ccxt, name)({"enableRateLimit": True})
            e.load_markets()
            return e, name
        except Exception:
            continue
    raise SystemExit("no exchange reachable")
ex, _ = get_ex()
sym = "BTC/USDT:USDT" if "BTC/USDT:USDT" in ex.markets else "BTC/USDT"
# NOTE: for the SYNC ccxt client fetch_ohlcv returns a list directly — do NOT await.
```

Runnable script: `scripts/weekday_study.py` (paginates daily OHLCV, prints all the
stats below). Run with `~/QuantumEdge/.venv/bin/python3 scripts/weekday_study.py`.

## Empirical result (BTC 1d, ~112 weeks since 2024-06, via BingX — 2026-07-20 run)
- **Avg daily return by weekday (open→close):** Mon +0.20% (%up 54%),
  Tue −0.07% (median −0.38%, %up only **43%** — weakest day), Wed +0.30%,
  Thu −0.42% (also weak), Fri +0.12%. → Tuesday genuinely the softest day.
- **Monday-dir vs Tuesday-dir:** opposite only **53%** (near coin-flip — the raw
  "Tue reverses Mon" thesis is WEAK). BUT the conditional is the real signal:
  - **Mon GREEN → Tue RED 59% of the time** (Tue avg −0.08%). Strongest pattern.
  - Mon RED → Tue up only 46% (weakness persists, no reliable bounce).
- **Weekend-range sweep by Mon+Tue:** sweep weekend HIGH 68%, sweep weekend LOW
  61%, sweep BOTH 32%. False breakout up (swept high, Tue closed back below) 39%;
  false breakdown (swept low, Tue closed back above) 35%. → "weekend edges get
  swept" is REAL (60-68%); the false-move confirmation is ~35-39%.

## Trading takeaways (encode into XRP-long context)
- The cleanest edge is **green Monday → fade into Tuesday** (short bias / expect
  pullback). A RED Monday does NOT give a reliable Tuesday bounce — don't assume
  a mirror rebound to defend a long.
- Watch whether BTC sweeps the **weekend LOW and closes back above it** (false
  breakdown, 35% base) → that is the bullish-reversal trigger that supports an
  XRP long. Conversely a close-and-hold below the weekend low warns of downside.
- Owner rule alignment: hold losing XRP long (Rule 1), watch US session (13-21
  UTC) for the sweep/reversal, act only on the false-breakdown confirmation.
