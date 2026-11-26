# QuantumEdge — Init / Take-Control Recipe (from 2026-07-31 session)

Runbook for the "wake up, read my DNA, start the HFT daemon, snapshot the
account, build the 5m brain cron" sequence. Solidified after a real handoff
where the agent had to (a) resurrect a stopped HFT daemon and (b) stand up a
5-minute autonomous trading-cron without double-trading.

## The 8-step boot sequence (verified live)
1. **Read DNA first** (highest priority). Always read in this order:
   - `/home/layman/.hermes/quantumedge_analysis/AI_CORE_MEMORY.md`  (living AI memory)
   - `/home/layman/.hermes/quantumedge_analysis/HERMES_DISTILLED_SOUL.md`  (role + DNA v5.0)
   - `/home/layman/.hermes/quantumedge_analysis/FULL_SYSTEM_CONTEXT.txt`
   - `/home/layman/.hermes/quantumedge_analysis/RULES.md`
   - `/home/layman/.hermes/quantumedge_analysis/SESSION_DISTILL.md`  **READ THIS FIRST after any reboot** — it carries the current mode (PAUSED vs LIVE), margin state, and any owner reverse-signals ("do nothing / distill only").
2. **Resolve mode conflicts.** A fresh owner prompt ("get to work / start now") overrides an older SESSION_DISTILL reverse-signal ("do nothing"). State explicitly which wins and why before acting.
3. **Check HFT daemon status — cleanly** (see Pitfall A). If not running, launch it.
4. **Read-only market sweep** (no orders):
   `cd /home/layman/.hermes/quantumedge_analysis && \
    ./venv/bin/python3 macro_data.py && \
    ./venv/bin/python3 _agy_now.py && \
    ./venv/bin/python3 market_analysis.py`
   `_agy_now.py` prints a clean live BingX snapshot (balance, 5 positions, tickers).
5. **Compute free-margin %** = free/total. If < 10% → MARGIN LOCK: HOLD only, no new directional entries (per RULES.md / HERMES_DISTILLED_SOUL Sacred Rule 3).
6. **Launch the HFT daemon** as a tracked background process (Pitfall B).
7. **Stand up the 5m cron** (see below) — do NOT hand-run the loop; let the scheduler own it.
8. **Deconflict double-trading.** Only ONE brain should issue orders. If a stale `agy` / `hermes_live.sh` / `hermes_self_cycle.sh` process exists from a prior session, kill it before starting a new autonomous cycle (see SESSION_DISTILL §5).

## Starting the HFT daemon (CORRECT way)
Use the tool's native background mode — do NOT use shell `nohup ... &` / `disown` in a
foreground `terminal()` call; the runtime rejects shell-level background wrappers.
```
terminal(background=true,
  command="cd /home/layman/.hermes/quantumedge_analysis && ./venv/bin/python3 tools/xrp_hft_daemon.py")
```
Then confirm: `pgrep -af "python3.*xrp_hft_daemon" | grep -v pgrep`
(Expected log line: `Starting XRP HFT Grid Daemon (Center: ..., Step: ..., Qty: ..., Levels: ...)`)

## Standing up the 5m brain cron
```
cronjob(action="create",
  name="QE Hermes 5m Trading Brain",
  schedule="*/5 * * * *",
  skills=["crypto-trading-system-ops","quantumedge-ops"],
  deliver="local",
  prompt="... full supervisor prompt: read DNA, sweep market, AI-sovereignty analysis,
          margin guard (<10% => HOLD), no 100% loss realization, ROI gates
          (SOL>=30%, XRP/BTC/ETH>=1.5%), BTC hybrid-lock, delegate execution to
          agy/2T+ via `agy --print \"...\" --dangerously-skip-permissions` or
          ./venv/bin/python3 tools/qe_trade.py (guardrails), LIMIT orders only
          (zero slippage), HFT XRP watchdog, 1-2 line TG-style report ...")
```
Note: `deliver="local"` means output is saved (cronjob action=list) but NOT
pushed into a CLI terminal. TG reporting is handled separately by
`tools/telegram_reporter.py` (15m). Cron jobs run in a FRESH session with no
chat context — the prompt MUST be fully self-contained (embed every rule).

## Pitfall A — pgrep self-match / shell-snapshot noise
A bare `pgrep -af xrp_hft_daemon` inside a `bash -c '...'` wrapper returns the
wrapper's OWN command line (it contains the search string), giving a false
"RUNNING". Two reliable fixes:
  - Anchor the pattern: `pgrep -af "python3.*xrp_hft_daemon"` (the launcher's
    argv is `python3 tools/xrp_hft_daemon.py` — the literal string
    `xrp_hft_daemon` only appears in the real daemon, not in `bash -c`).
  - Or pipe through `grep -v pgrep` to drop the self-match.
  - Best: use `pgrep -af xrp_hft_daemon | grep -v pgrep` for a clean boolean.

## Pitfall B — background process tooling
`terminal(background=true)` is the ONLY supported way to run a long-lived
daemon. Shell `nohup ... &`, `setsid`, `disown` inside a foreground
`terminal()` call are rejected with: "Foreground command uses shell-level
background wrappers ... Use terminal(background=true)".

## Pitfall C — stale / phantom open orders
`tools/qe_trade.py snapshot` (note: the script is in `tools/`, NOT the repo
root) may show many OPEN orders including SELL market orders with status
"open" (markets should fill instantly) and PARTIALLYFILLED limits. Treat these
as suspicious leftovers from prior sessions. Audit before placing new orders;
cancel stragglers via `tools/qe_trade.py cancel <id>` only after the owner
sanctions it (No-Loss / Margin rules still apply).

## Pitfall D — liquidation-distance is WRONG for hedged positions
Two independent sources lie about liquidation price on this account:
- `tools/check_liquidation_safety.py` computes `liq` PER LEG and ignores the
  opposite hedge side. On a hedged lock it returns absurd numbers:
  BTC liq ≈ 528,980 (mark 63,900), SOL liq ≈ 2,021 (mark 73.7),
  ETH liq = 0.0. **Do NOT trust its `dist_pct` for any symbol that has both a
  long and short open.** Only the single unhedged leg (XRP LONG, ~2.2% to liq)
  is valid there.
- BingX testnet via ccxt: `fetch_positions()` returns `liquidationPrice = 0.0`
  for every leg (API limitation on VST). So you cannot read real liq-distance
  from the exchange directly either.
**Correct approach:** compute liq-distance by hand per side using entry, mark,
leverage, and margin; OR treat the hedged pair as a net position (long+short
cancel toward a lock) whose effective liq is far safer than the per-leg tool
shows. Always sanity-check: if a reported liq price is orders of magnitude off
the mark, it is the hedge-ignoring bug, not a real margin call.

## Iron rule (owner, 2026-07-31) — embed in every decision
Never close a position that is underwater (uPnL < 0). Allowed only:
average down (limit DCA), open an opposite hedge leg, or wait out the drawdown
— provided margin-to-liquidation is not critical. Closing 100% of a red
position is forbidden; partial cuts (≤50%) only from a PROFITABLE hedge leg.
Current account state: XRP LONG is the only unhedged leg (~2.2% to liq) and is
under watch, not action.

## Margin math quick-ref (from live 07:50 UTC snapshot)
Total 514,307 VST | Free 184,685 VST | Used 329,623 VST => free margin 35.91%.
Positions seen: XRP LONG 50x, BTC LONG 50x (−107k uPnL) hedged by BTC SHORT 50x
(+38k), SOL SHORT 50x (+185), ETH LONG 50x (−387, isolated 1000 VST cap).
BTC is effectively a hedged LOCK => do not flip direction without explicit owner order.
