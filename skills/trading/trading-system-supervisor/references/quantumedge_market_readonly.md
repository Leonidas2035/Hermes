# QuantumEdge — Read-only market assessment chain

When Leonid asks "what do the indicators say?" / "what is the market doing?", DO
NOT hand-wave. Run the actual project tools from the QuantumEdge root. The venv
is at `QuantumEdge/.venv` (ccxt is only there, not in the hermes venv).

```bash
cd /home/layman/QuantumEdge
source .venv/bin/activate

# 1. Live account + order-book state (BingX VST, hedge mode, REAL account)
python tools/qe_trade.py snapshot
#   -> JSON: mark_price, book imbalance, balance(free/used),
#      legs[side/size/entry/uPnL/lev], open_orders[]

# 2. Composite Signal Engine (4+1 axes, -100..+100, calibrated confidence)
python -m tools.composite_signal.cli --tf 1h --limit 150
#   -> JSON + prints SCORE / regime / per-axis breakdown
#   -> saved to runtime/composite_latest.json

# 3. Indicator calibration / edge table (historical win-rates per signal)
python -m tools.sigtest.cli
#   -> saved to runtime/sigtest_calibration.json
#   NOTE: prints HORIZON tables (12h/24h/48h). These are BACKTEST stats,
#         not the current tick. Use to judge WHICH indicators have edge,
#         not to "see current RSI". Use composite_signal.cli for the live read.
```

## CRITICAL cross-symbol pitfall
`composite_signal.cli` and `sigtest.cli` compute on **BTC** (the live composite
run in the originating session printed `Price: 66788.5` = **BTC**, NOT XRP).
Meanwhile `qe_trade.py snapshot` + the bot's open position are on **XRP**
(`XRPUSDT`, ~1.15).

=> When you present "indicators say LONG / on the highs", you are showing the
**BTC** composite. The bot's open position is **XRP SHORT**. A bullish BTC
composite is TAILWIND AGAINST the XRP short. Always state the symbol explicitly
and flag the mismatch. Never silently imply the indicator read applies to the
symbol you hold.

## Reading the composite output
- Score >= +80 in BULL regime, or <= -40 in BEAR regime = tradeable per
  calibration. Counter-trend (<50% confidence) = ignore.
- 5 axes: Trend(EMA+ADX) / Momentum(MACD+RSI) / Volatility(BB+ATR) /
  Volume-Flow(OI+OBV) / LiqMap. A high score dominated by a single axis is
  weaker than a broad consensus. Report the axis breakdown, not just the number.
- For Leonid's exit rule on a LONG: hold while RSI<=70 AND MACD_hist>0; trail to
  BE once in profit and pullback >= 0.3%. (See owner rules in memory.)
