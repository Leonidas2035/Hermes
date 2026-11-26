# Watchdog removal and supervisor-loop cleanup

## When to use
Use when the owner says the QuantumEdge Watchdog is unreliable and wants it removed, rather than repaired.

## Verified removal sequence
1. Search the project, Hermes cron store, user systemd units, and helper scripts for `watchdog.py`, `watchdog_signal`, `watchdog.service`, and `ollama.service`.
2. Distinguish the trading Watchdog from unrelated dependencies/tests. In this environment, `venv/site-packages/watchdog` and Hermes test files are unrelated; do not remove them.
3. Stop and disable the user service first:
   `systemctl --user disable --now watchdog.service`
   then `systemctl --user daemon-reload`.
4. Remove only the confirmed QuantumEdge runtime components: `tools/watchdog.py`, the wrapper script, the user service unit, and generated `watchdog_signal.json` / `watchdog_state.json`.
5. Remove or update Hermes cron jobs whose prompts explicitly consume the Watchdog signal. Do not remove the main analysis cycle merely because it runs every 5 minutes; inspect its prompt and retain it if it is Watchdog-independent.
6. Verify with all of: `systemctl --user is-active watchdog.service` → inactive/not-found, no `watchdog.py` process, no Watchdog service references in active systemd units, no Watchdog signal references in active cron prompts, and the remaining cron inventory.

## Important pitfalls
- Search results may include the Python `watchdog` package and unrelated tests; these are not the QuantumEdge Watchdog.
- Historical cron output and skill documentation can still contain the word Watchdog. Treat them as archived records, not active configuration, unless the owner explicitly requests historical cleanup.
- Do not delete the general-purpose `Hermes 5m Market Cycle` if its current prompt no longer references Watchdog.
- Use the actual configured job IDs from `cronjob action=list`; never infer IDs from old notes.
