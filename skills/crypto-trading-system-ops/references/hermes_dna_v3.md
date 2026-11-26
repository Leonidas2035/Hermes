# HERMES TRADING DNA v3.0 — QUANTUMEDGE MANIFESTO

**Source:** User prompt 2026-07-31 + AI_CORE_MEMORY.md + HERMES_DISTILLED_SOUL.md + RULES.md
**Status:** ACTIVE — Governs all Hermes trading decisions for QuantumEdge

---

## 1. Trigger Condition (Entry & Microstructure)

- **Indicator Sync:** Entry only on confluence of base indicators (MACD, BB) + successful `sigtest` pass.
- **VWAP Fair Value Filter:** LONG priority when price **below daily VWAP** (Undervalued Zone).
- **Sniper Entry (StochRSI):** For DCA limit orders or micro-scalp starts, use **only StochRSI** (5m/15m):
  - `< 20` = local bottom for LONG
  - `> 80` = local top for SHORT
- **Liqmap-Driven Entry:** Entry only if distance to nearest liquidation pool (`liqmap_latest.json`) ≤ 2%.
- **Smart DCA (Momentum Breakout):** Split entry:
  - 25–30% **Market Buy** immediately (capture momentum)
  - 70–75% **Limit Grid** below price (ATR-based spacing)

---

## 2. Position Sizing (Dynamic Lot & Margin Protection)

- **Proportional Scaling:** Base order size by balance:
  - XRP: 10,000–100,000
  - BTC: 0.1–1.0
  - SOL: 10–50
- **Dynamic Exposure (Decay Function):** **NO hard blocks.** If free margin < 40%, each subsequent DCA order size shrinks exponentially. Stay in book even near risk zones without burning balance.
- **Order TTL (Time-to-Live):** Cancel limit DCA orders if price moved > 2.0% away AND not filled in 1 hour → frees margin.

---

## 3. Take-Profit / Harvesting Protocol

- **ABSOLUTE LOSS REALIZATION BAN:** Never close uPnL < 0 position manually.
- **Breakeven Lock (Auto-Breakeven):** At **+1.0% uPnL**, immediately place conditional stop at `Avg Entry + 0.1%` (covers fees). Profitable trade can NEVER become a loser.
- **Paired Harvesting (BingX Bug Workaround):** SHORT orders ONLY to reduce existing LONG on trend exhaustion (Ask Walls / RSI > 70). **All shorts sent with `reduceOnly=True`** to bypass exchange errors 109420/109400. Building opposite position is FORBIDDEN.
- **Liqmap Front-running TP:** TP at ATR distance, placed **-0.1% before** nearest Ask-wall or liq magnet (front-run the crowd).

---

## 4. Safety / Emergency Rules

- **Auto-Stop OFF:** Hardware stop-losses disabled. Risk controlled via liquidation map + DCA.
- **Anti-Lock (Attacking Trading):** NO passive 1-to-1 hedge locks. Architectural error. Any counter-order MUST have active TP.
- **Drawdown Micro-Scalping (Reserve Plan):** If liq distance < 3 ATR OR free margin < 30% → stop aggressive DCA. Use remaining margin for **blitz scalps** (StochRSI 5m signals inside channel). All realized profit → partial cover of losing main position.

---

## Asset-Specific Overrides

| Asset | Strategy | ROI Gate | Entry Logic |
|-------|----------|----------|-------------|
| **BTC** | HYBRID (frozen) | ≥1.5% | Requires explicit user go-ahead. Liq magnets: $62.2k (long) / $65.8k (short) |
| **SOL** | AGGRESSIVE_SWING | ≥30% | BB lower/RSI<45/MACD up. Grid: Tranche 1 @ support, T2 @ EMA50/lower BB |
| **ETH** | AI_AUTONOMOUS | Dynamic | 15m/1h BB lower + RSI<45 + MACD up. Isolated 1000 VST cap. |
| **XRP** | HFT_ISOLATED | ≥1.5% | Delegated to `xrp_hft_daemon.py`. Monitor 5m StochRSI>85 for counter-short (reduceOnly). |

---

## Macro Session Context (AI_CORE_MEMORY.md §2)

- **Macro analysis ONLY** 1h before global session opens (Europe ~09:00 UTC+3, US ~15:30 UTC+3).
- **US Session (BTC):** Analyze S&P 500, Russell 2000, futures. If bearish bias → open hedge shorts.
- **BTC Session Context:** US session = most volatile/trendy (breakouts, Swing). Asia = range (accumulation, HFT grids). In trend session, hold longs longer.

---

## Trading Axioms (AI_CORE_MEMORY.md §3)

1. **ZERO SLIPPAGE (Tabu on Market Stops):** All TP/SL = Limit Orders (`type: TAKE_PROFIT` with `price`). Market closes eat ~0.05% taker fee + slippage.
2. **AGGRESSIVE DCA ENTRY:** In bull trend, waiting for perfect pullback = FOMA. Enter 1st tranche market immediately; rest as limit traps below.
3. **LIQUIDATION SNIPING:** Price moves to largest liq cluster. If $64.8k price, $65.9k short liq pool → hold long until liq swept, ignore micro-drawdowns.
4. **SOL SWING vs XRP HFT:** SOL = Swing (+30% ROI, ignore noise). XRP = HFT daemon (+1.5% per trade).