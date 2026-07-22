# Night Autopilot pattern (QuantumEdge autopilot)

The user may delegate the Supervisor/Orchestrator role to the agent for
unattended trading (e.g. "go to sleep, you're in charge, report in the
morning"). This is DELEGATED AUTONOMY mode — different from the default
per-action-authorization mode. Build it so it is safe to run with no human
in the loop.

## Canonical artifact (this project)
`/home/layman/QuantumEdge/tools/night_autopilot.py` — headless engine that:
- every 5 min: reads market/book/balance/positions, decides, executes.
- on each 15m candle close: re-runs TradingView scrape + full re-analysis.
- writes `runtime/autopilot_state.json` (ledger) + `runtime/autopilot_journal.jsonl`.

Cron wrapper (must live in `~/.hermes/scripts/` — cron scripts can't use
absolute/project paths):
```bash
#!/bin/bash
cd /home/layman/QuantumEdge || exit 1
AP_LIVE=1 /home/layman/QuantumEdge/.venv/bin/python3 tools/night_autopilot.py 2>&1 \
  | grep -v -E "RuntimeWarning|await |client_session|connector|Unclosed|tracemalloc|deque|aiohttp"
```
Register: `cronjob create` schedule `*/5 * * * *` script `run_autopilot.sh`
`no_agent=true` deliver `local` (script-only watchdog = silent unless it errors).

## Why a state ledger is mandatory
Each cron tick is a FRESH session — no memory of prior ticks. Without a
disk-backed ledger the bot will (a) re-place the same order repeatedly and
(b) conflict with itself. The ledger (`runtime/autopilot_state.json`)
must persist at least: `actions_taken`, `last_action_ts`, `last_15m_bucket`,
`last_decision`, `last_tv`. Bump `last_action_ts` on every live order and
gate new orders on `now - last_action_ts >= COOLDOWN`.

## Guardrail knobs (env, all tunable)
- `AP_LIVE` (0/1) — master switch. 0 = dry-run (logs what it WOULD do,
  places nothing). ALWAYS smoke-test with `AP_LIVE=0` before flipping live.
- `AP_BASE_ORDER_XRP` — unit trade size (default 5000).
- `AP_MAX_ACTIONS` — hard cap per night (default 12).
- `AP_COOLDOWN_SEC` — min seconds between live orders (~780 = 13 min).
- `AP_RANGE_HI` / `AP_RANGE_LO` — breakout triggers (1.1168 / 1.1154 for XRP).
- `AP_DAY_HI` / `AP_DAY_LO` — danger thresholds for re-hedge rule.

## Opportunity-seeking decision ladder (don't hide behind risks)
Order matters — check top-down. Find the TRADE, act on clear triggers,
otherwise OBSERVE. Never bail on mere uncertainty; bail only on genuine
danger (big net-short + price at day-high + zero free margin).
1. Breakout up (`price > RANGE_HI`) + bullish signal -> ADD_LONG.
2. Breakout down (`price < RANGE_LO`) + bearish signal -> ADD_SHORT.
3. Long leg in profit + sellers taking over (book imbalance < -0.2) ->
   HARVEST_LONG_REDUCE_SHORT (Rule 2: trim losing short with winning leg).
4. RANGE SCALP: book imbalance `<= -0.18` in upper half -> ADD_SHORT toward
   range low; `>= 0.18` in lower half -> ADD_LONG toward range high.
   (User softened threshold from +/-0.25 to +/-0.18 for more entries overnight.)
5. Opportunistic harvest: winning leg in profit + losing leg in loss ->
   harvest winning, shrink losing.

## Lock-unwinding rules (user's standing strategy — embed verbatim intent)
- Rule 1: NEVER close a losing position.
- Rule 2: a losing leg MAY be reduced using profit from the opposite
  (winning) leg. (Impossible while BOTH legs are in loss — then wait.)
- Rule 3: indicators long -> add long; when the move exhausts -> take profit,
  add short.
- Rule 4: high risk -> re-hedge and wait until the market is predictable.

## Critical reality check before going live
Read the LIVE journal, not assumptions. In one session the user believed a
lock was "long in profit / short in loss" but the live book showed BOTH
legs had flipped to loss (long had been averaged up to a higher entry,
leverage had doubled to 10x). When both legs are in loss, Rule 2 is
physically impossible — the bot must not invent a harvest. Adjust the plan
to reality, then trade.

## Pitfall: stateless cron + duplicate orders
If you skip the ledger, every 5-min tick re-enters. The ledger + cooldown is
the fix. Also reset `runtime/autopilot_state.json` between test runs so a
dry-run doesn't inflate the night's action count.
