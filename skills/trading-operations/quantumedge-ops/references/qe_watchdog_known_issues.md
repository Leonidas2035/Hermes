# QE Agent Architecture — Known Issues & Fixes (2026-07-21)

## 1. Watchdog `vol_index` always 0.0
**Symptom:** `runtime/watchdog_signal.json` shows `"vol_index": 0.0` every tick.
**Cause:** `tools/watchdog.py` used `import ccxt` (SYNC module) and called
`ex.fetch_ohlcv(SYMBOL,"5m",limit=30)` WITHOUT `await`. In ccxt 4.5.64 the sync
module's `fetch_ohlcv` is a coroutine → returned a coroutine object, not a list
→ `get_vol_index` got a non-iterable → returned 0.0.
**Fix:** `import ccxt.async_support as ccxt` and `ohlcv = await ex.fetch_ohlcv(...)`.
Verify: run `python3 tools/watchdog.py` → `vol_index` should be >0 (e.g. 0.3–0.6).
**Lesson:** under `ccxt.async_support` 4.5.64, `fetch_ohlcv`/`fetch_ticker` ARE
awaitable in THIS env (contrary to older notes). Always 1-line diag before looping:
`async def t(): r=await ex.fetch_ohlcv(s,'5m',5); print(type(r))`.

## 2. Hermes cron dies with 429 on a free model despite `model=hy3`
**Symptom:** cron `last_status: error`, request dump shows
`RateLimitError 429 free-models-per-day` and `"model": "google/gemma-4-31b-it:free"`.
**Cause:** `cronjob update`/`create` with `model=hy3` did NOT override the model
in the actual API request. Hermes cron falls back to `config.yaml →
fallback_model.model`, which was the free model.
**Fix:** `hermes config set fallback_model.model tencent/hy3`. Gateway must
reload (may need `hermes gateway restart` — REQUIRES USER consent, never self-approve).
**Verify real model:** `ls -t ~/.hermes/sessions/request_dump_cron_<ID>_* | head -1`
then grep `\"model\":`. Should show hy3, not *:free.
**Lesson:** if a cron keeps 429-ing on a free model, check `fallback_model` in
config.yaml, not just the cron's declared model.

## 3. Watchdog runs as systemd daemon (NOT a Hermes cron)
Watchdog runs as `~/.config/systemd/user/watchdog.service`
(`ExecStart=.../venv/bin/python3 tools/watchdog.py`, `Restart=always`).
`while True` + `sleep_until_next_5m()` syncs to 5m boundaries. Do NOT also run it
as a Hermes cron (double execution). Check: `systemctl --user is-active
watchdog.service`, `pgrep -af watchdog.py`.
