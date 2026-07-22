# Safe daemon restart (orchestrator)

## Use the project venv
Start the orchestrator with the project's venv interpreter, NOT system python:
```
.venv/bin/python3 QuantumEdge.py start      # ✓ (xgboost etc. available)
python3 QuantumEdge.py start                 # ✗ ModuleNotFoundError: No module named 'xgboost'
```
Bot deps (xgboost, ccxt, ...) live in the venv. System `python3` lacks them →
component crashes at import.

## Sequence
1. Snapshot exchange state (read-only): balance, open positions, open orders.
2. `python3 QuantumEdge.py stop` (or `.venv/bin/python3 ... stop`) → SYSTEM_HALT.
3. Confirm control port free (`ss -ltn | grep 5560`).
4. Start via venv (background). Bootstrap takes ~30s (zmq guard cleanup kills
   old procs on critical ports, then relaunches hub→supervisor→bots).
5. Verify: `status` shows all RUNNING; tail bot log for live strategy decisions.
6. Re-snapshot exchange state — positions must be unchanged (shutdown does not
   close positions).

## Why positions survive
Orchestrator ZMQ guard cleanup kills processes on ports, causing a brief trading
gap, but open exchange positions are server-side and persist. Only the bot
process dies/restarts.

## Monitoring false-positive fix
If the orchestrator only tracks self-spawned procs (`self.processes`), an
externally-started bot reports `TERMINATED` even while alive. In the telemetry
report, when a component's proc is dead, re-detect a live external instance:
```python
import psutil
def _find_external_process(self, name):
    sig = {"ai_scalper": ("ai_scalper_bot","run_bot"), "dyndca": ("dyn_dca_bot",),
           "lockbotbtc": ("lock_bot",), "supervisor": ("supervisor",),
           "hub": ("market_data","hub")}.get(name)
    if not sig: return None
    for proc in psutil.process_iter(["pid","cmdline","name"]):
        try: cl = " ".join(proc.info.get("cmdline") or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied): continue
        if all(t in cl for t in sig) and proc.is_running():
            return proc
    return None
```
Call it both as a fallback for missing keys AND to override a dead self-spawned
entry (so a re-detected live instance flips TERMINATED → RUNNING).
