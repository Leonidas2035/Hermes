Agy quota exhausted ~43h24m. User instructed not to use until reset. Do not spawn agy tasks. Error ID: a676d1c4c34b4d76955827ba3d747845.
§
QuantumEdge project at /home/korben/QuantumEdge-main/ — LIVE. DynDCA standalone: PYTHONPATH=src .venv/bin/python -m quantum_edge_core.dyn_dca_bot.main (needs Hub on 5555, telemetry 5567). ai_scalper standalone: QE_BOT_POLICY_PORT=5559 via module quantum_edge_core.ai_scalper_bot.run_bot. QuantumEdge.py status unreliable; cross-check with ps/ss/netstat.
§
Session pattern for subscription bugs: commands sent to bot but never applied because `cmd_sub.connect()` was used instead of `bind()`. Bot must bind SUB on policy port, supervisor connects PUB. Verified with `ss -tlnp | grep <port>` and ZMQ multistep send test.
§
QE config alignment: `.env` + `config/processes.yaml` must match `QE_BOT_ID` and `QE_BOT_POLICY_PORT`; mismatches cause silent policy delivery failures. `QE_BOT_ID` sets ZMQ topic `command.<id>`. `reporter.py` falls back `trading_mode` but not `buy_zone_max`/`risk_multiplier`, causing asymmetric partial policy propagation.
§
Prefer config/secrets.local.env for DynDCA secrets in live deployment; validate live state with startup logs and exchange HTTP 200 OK, not only status wrappers; when telemetry is stale, use ps/ss/logs over terminal status outputs.
§
BingX Hedge mode API quirks: limit sell on LONG fails for very large single orders (observed >15 BTC, but works for ≤10 BTC). Use chunked limit sells of ≤10 BTC. Market buy on LONG for opening works. Market sell on LONG executes immediately (acts like immediate close). Short TP (limit buy) may fail with "available amount insufficient" when many orders exist or under rate pressure; retry later. Avoid concurrently running multiple trading cron jobs on same account.
§
Manual supervision mode: DCA/entries disabled. 15-min watchdog cron fd3e9d0fa646 runs qe_monitor.py. User wants manual analysis + decisions. Key levels from BB upper + RSI>60 on 1h. Partial TP +0.5%, hedge -8%, unwind +0.3%. CCXT API > bot telemetry.