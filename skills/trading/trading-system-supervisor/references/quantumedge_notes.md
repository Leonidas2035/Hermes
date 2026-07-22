# QuantumEdge deployment notes (project-specific)

Path: `/home/layman/QuantumEdge`. Local HFT orchestration system.

## Component map (ZMQ ports)

- MarketDataHub — ZMQ PUB :5555 (also IPC `/tmp/quantum_market_data.ipc`)
- SupervisorAgent — :5558 (policy), :5559 (command), :8765 (HTTP heartbeat)
- AI Scalper — telemetry :5557, policy :5559, command bus :5562
- DynDCA — telemetry :5567
- LockBotBTC — :5577 / :5578 / :5561
- QuestDB (Docker) — :9000 / :9009 / :8812
- Orchestrator daemon (QuantumEdge.py) — JSON-RPC :5560

## Known issues (from audit + this session)

1. Orchestrator `status` can FALSE-REPORT `ai_scalper=TERMINATED` while the
   process is alive (heartbeat desync). Trust `ps aux | grep run_bot` + live
   log + exchange probe.
2. Port 5559 conflict: Supervisor publishes commands, AI Scalper does
   `bind()` on same port (should `connect()`). Historical; verify before fix.
3. `config/risk.yaml`: `risk_management_enabled: false` — NO drawdown/loss
   protection. Flag to user; recommend enabling.
4. LLM moderation circuit breaker can be OPEN (policy `reason` shows
   `LLM_CB_OPEN`) → LLM market risk eval inactive.
5. Two venvs (`.venv`, `venv`) historically; current run uses `.venv/bin/python3`.
6. `config/quantumedge_testnet.yaml` historically says `ETHUSDT` but live
   system runs `XRPUSDT` — check actual env vars (`/proc/<pid>/environ`), not
   the stale yaml.

## Logs

- AI Scalper main: `bot.log` and `/home/layman/logs/processes/ai_scalper_bot.log`
- Orchestrator/supervisor: `logs/supervisor.log`, `logs/quantum_edge.log`
  (note: `quantum_edge.log` tail is DynDCA telemetry, not the scalper)
- Behavior heartbeat: `ai_scalper_behavior.log`

## Safety

- BingX keys are in `/proc/<pid>/environ` (readable). Testnet, but tighten
  `.env` perms (`chmod 600`) regardless.
- Execute modes: `paper | bingx | binance`. `EXECUTION_MODE=bingx`,
  `USE_TESTNET=true` = BingX VST demo (no real money).
