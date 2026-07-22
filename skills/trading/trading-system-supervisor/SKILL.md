---
name: trading-system-supervisor
description: >
  Operate, audit, and safely intervene in a live (or testnet) crypto trading
  system while acting as Supervisor / Orchestrator. Mandatory methodology:
  READ-ONLY exchange probe first, diagnose with ground-truth data, obtain
  EXPLICIT user sanction before any order, VERIFY after. Includes the working
  BingX (VST/testnet) connection recipe via ccxt.async_support and the
  non-obvious pitfalls (ccxt sync-vs-async import, "Insufficient margin"
  101204, orchestrator false-reports).
---

# Trading System Supervisor

You are the Supervisor / Orchestrator of a live crypto trading system. The user
delegates operational control, but **you must never self-authorize real-money
(or even testnet) order actions**. This skill encodes the safe operating loop
and the BingX ccxt connection technique that actually works.

## Core methodology (non-negotiable order)

1. **READ-ONLY FIRST.** Before any action, connect read-only and pull account
   state: balance (free vs used), open positions (size, side, entry, uPnL,
   leverage), open orders. Use `scripts/bingx_readonly_probe.py`.
2. **DIAGNOSE WITH GROUND TRUTH, not orchestrator status.** Never conclude a
   component is "broken/dead" from the orchestrator's `status` command alone.
   Cross-check three independent sources:
   - `ps aux | grep run_bot` (is the process alive?)
   - the component's live log (what is it actually printing NOW?)
   - a live exchange probe (real balance / positions / orders)
   In-session example: orchestrator reported `ai_scalper=TERMINATED` but the
   process was alive and trading; the real blocker was exchange error
   `101204 "Insufficient margin"` (account 100% margin-locked, free=0). The
   "dead bot" was a misdiagnosis.
3. **SANCTION BEFORE ACT.** Never place / cancel / close orders without
   explicit user confirmation. Offer a menu and wait:
   - A) leave as-is (HODL positions)
   - B) cancel stale open orders (idempotent, does NOT touch positions)
   - C) partial close of an overexposed side (frees margin, cuts risk)
   - D) revive / fix a stuck component
4. **VERIFY AFTER.** Re-run the read-only probe to confirm the action landed
   (margin freed, size changed, orders cleared).

## Read-only market assessment chain (Leonid: "what do the indicators say?")

Run the actual project tools from the QuantumEdge root — never hand-wave. The
venv is `.venv` (ccxt NOT in the hermes venv). Full recipe + the cross-symbol
pitfall in `references/quantumedge_market_readonly.md`:

1. `python tools/qe_trade.py snapshot` — live balance / positions / book / orders.
2. `python -m tools.composite_signal.cli --tf 1h --limit 150` — live 4+1 Composite
   Score (-100..+100) + per-axis breakdown. This is the CURRENT read.
3. `python -m tools.sigtest.cli` — historical indicator edge table (BACKTEST
   stats, not current tick). Use to judge which indicators have edge.

**CRITICAL cross-symbol pitfall:** `composite_signal.cli` / `sigtest.cli` compute
on **BTC** (live run printed `Price: 66788.5` = BTC). `qe_trade.py` + the bot's
open position are on **XRP** (~1.15). A bullish BTC composite is TAILWIND AGAINST
an XRP SHORT — always state the symbol and flag the mismatch. Never imply the
indicator read applies to the symbol you hold.

## Connecting to BingX (VST / testnet) via ccxt

```python
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
import ccxt.async_support as ccxt   # <-- async_support, NOT sync `ccxt`
```

- **PITFALL — async import:** `import ccxt` (sync) returns dicts from its
  methods; `await ex.load_markets()` then raises
  *"object dict can't be used in 'await' expression"*. Always use
  `ccxt.async_support`.
- Credentials: when `USE_TESTNET` is truthy, use
  `BINGX_TESTNET_API_KEY` / `BINGX_TESTNET_SECRET` (fall back to
  `BINGX_API_KEY` / `BINGX_SECRET`). Loaded from `.env` via `dotenv`.
- `ex = ccxt.bingx({apiKey, secret, "options": {"defaultType": "swap"}, ...})`
  then `ex.set_sandbox_mode(True)` for VST.
- **Symbol format:** swap/perp uses `BASE/USDT:USDT` (e.g. `XRP/USDT:USDT`).
- **Balance key:** in swap/testnet the quote asset is `VST`, not `USDT`.
  Set `ex.options["defaultType"] = "swap"` before `fetch_balance()`.
- **Close:** in ccxt 4.5 `ex.close()` returns `None` — call it WITHOUT
  `await` (wrapping in try/except pass is fine).
- `ex.load_markets()` once after init; then `fetch_balance()`,
  `fetch_positions(symbols=[sym])`, `fetch_open_orders(symbol=sym)`.

See `references/bingx_ccxt.md` for the full annotated recipe.

## Safe actions (ONLY after explicit sanction)

- **B) Cancel all stale orders** — idempotent, never touches positions:
  `await ex.cancel_all_orders(symbol=CCXT_SYMBOL)`
- **C) Partial close of a SHORT (buy-to-cover, hedge mode):**
  `await ex.create_order(symbol, "market", "buy", qty, params={"positionSide": "SHORT"})`
  Verify the SHORT size dropped and free margin rose.
- After any action, re-run the read-only probe to verify.

See `scripts/bingx_safe_actions.py` (cancel-all + partial SHORT close; set
`SUPERVISOR_SHORT_CLOSE_QTY` env to control volume).

## Pitfalls (encode these — they recur)

- **ccxt sync vs async import** → "object dict can't be used in 'await'
  expression". Fix: `import ccxt.async_support as ccxt`.
- **"Insufficient margin" (code 101204)** = account fully margin-locked;
  bots silently fail to open new orders, free balance = 0. The exchange is NOT
  "broken" — it is correctly blocking new exposure. Fix: free margin via
  actions B+C, then bots resume on their own (no restart needed).
- **Orchestrator status false-report:** a component can show `TERMINATED`
  while the process is alive (heartbeat desync). Trust `ps` + live logs +
  exchange probe over the orchestrator `status` command.
- **LLM circuit breaker open** (policy `reason` contains `LLM_CB_OPEN`) =
  LLM market moderation inactive. **`risk_management_enabled: false`** = no
  drawdown / loss protection at all. Always flag both to the user.
- **API keys in `/proc/<pid>/environ`** are world-readable by the user; note
  as a security risk even on testnet, recommend tightening `.env` perms.
- **Modifying a Stop-Loss on BingX swap (hedge-mode) — two traps:**
  1. `ex.edit_position(...)` does **NOT** exist on `ccxt.bingx`
     (AttributeError). Do not call it.
  2. `reduceOnly: True` is **REJECTED** in hedge mode →
     `{"code":109400,"msg":"In the Hedge mode, the 'ReduceOnly' field can not be filled."}`
  Working pattern: `fetch_positions` → get REAL `contracts` (never `amount=0`,
  that's rejected as "below min precision") → `cancel_order` any existing
  stop/trigger order for that `positionSide` → `create_order(type="market",
  side=sell-for-LONG/buy-for-SHORT, amount=qty, params={"stopLossPrice": X,
  "positionSide": SIDE})` (NO reduceOnly). See
  `references/bingx_stop_loss_modify.md` for the full snippet. Used by
  `qe_trade.py:set_sl` and `trader.py:trail_to_breakeven` (BE move) and
  `xrp_short_watch.py` (autonomous swing daemon).

## Files in this skill

- `scripts/bingx_readonly_probe.py` — connect read-only, print balance /
  positions / orders. Safe to run any time.
- `scripts/bingx_safe_actions.py` — cancel-all + partial SHORT close (set
  `SUPERVISOR_SHORT_CLOSE_QTY`).
- `references/bingx_ccxt.md` — detailed ccxt recipe + field notes.
- `references/quantumedge_notes.md` — project-specific gotchas for the
  QuantumEdge deployment (component map, known issues, risk.yaml).
- `references/quantumedge_market_readonly.md` — the read-only market
  assessment chain (snapshot + composite + sigtest) and the BTC-vs-XRP
  cross-symbol pitfall.

## When NOT to use this skill

Pure market analysis, backtesting, or building a strategy from scratch — this
skill is about *operating* a system that already exists, not designing one.
