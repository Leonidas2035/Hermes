# Ollama + Watchdog auto-start (post-reboot fix, 2026-07-21)

## Problem (observed)
After a machine reboot the Watchdog daemon came up but Ollama was DOWN. The
watchdog's first cycle logged:
  `[Errno 111] Connection refused`
  `Warning: LLM failed, falling back to rule-based math decision.`
Every 5-minute cycle then ran in **fallback** — no LLM market read, pure math
wake decisions — until someone started Ollama by hand. Root cause: Ollama had
NO systemd unit; only the `ollama` binary at `/home/layman/.local/bin/ollama`.

## Fix (applied + fact-checked via live output)

### 1. Create `~/.config/systemd/user/ollama.service`
```
[Unit]
Description=Ollama Service
After=network.target

[Service]
Type=simple
ExecStart=/home/layman/.local/bin/ollama serve
Environment=LD_LIBRARY_PATH=/home/layman/.local/lib/ollama
Environment=HOME=/home/layman
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```
NOTE: CUDA lib path is `/home/layman/.local/lib/ollama` (no `cuda_v13`
subdir; the earlier audit's path was stale). Model loads onto the RTX 4060
(~6.7 GB VRAM) without that env var too, but keep it set.

### 2. Add dependency to `~/.config/systemd/user/watchdog.service`
Change the `[Unit]` block to:
```
[Unit]
Description=QuantumEdge Watchdog Daemon
After=network.target ollama.service
Wants=ollama.service
```
(Leave the existing `[Service]` / `[Install]` as-is: ExecStart=...venv/bin/python3
tools/watchdog.py, Restart=always, RestartSec=10.)

### 3. Enable + start
```
systemctl --user daemon-reload
systemctl --user enable --now ollama.service
```

## Verification (run each, expect the listed output)
- `systemctl --user is-active ollama.service`  → `active`
- `ss -ltn | grep 11434`  → `LISTEN ... 127.0.0.1:11434`
- `ollama list`  → shows `hermes3:8b-llama3.1-q5_K_M` (5.7 GB)
- Pre-warm the model so the first watchdog LLM call isn't a slow cold load:
  `ollama run hermes3:8b-llama3.1-q5_K_M "ping"`  (reply is irrelevant; just
  loads weights into VRAM)
- `systemctl --user is-active watchdog.service`  → `active`
- `cd /home/layman/QuantumEdge && .venv/bin/python3 tools/watchdog.py --oneshot`
  → must print `LLM successfully processed watchdog check` (NOT "falling back").

## Manual one-shot start (if no systemd fix desired)
```
cd /home/layman && nohup /home/layman/.local/bin/ollama serve >/tmp/ollama.log 2>&1 &
```
WARNING: launch via `terminal(background=true)`, NOT `nohup ... &` in a
foreground shell call — the harness blocks shell-level background wrappers.

## Cron note
No Hermes cron drives the watchdog. It is the user-level systemd service above.
A Hermes cron reading `watchdog_signal.json` is the TRADER, not the watchdog.
