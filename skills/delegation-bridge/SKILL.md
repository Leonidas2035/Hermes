---
name: delegation-bridge
description: "Delegation Bridge: delegate complex tasks to the advanced Antigravity analyst agent via the real `agy` CLI on this host (NOT the deprecated JSON-queue script)."
version: 1.1.0
author: Antigravity AI (updated for local `agy` CLI)
license: MIT
platforms: [linux, macos]
---

# Delegation Bridge

Use this skill when the user asks for complex coding, trading strategy development,
server management, or deep analysis that is beyond the scope of a fast model, OR
when the user explicitly says to delegate (e.g. "відправ кодеру", "agy", "Antigravity").

## The REAL delegation path: `agy` CLI

The working tool on this host is the **`agy` (Antigravity) CLI** at
`/home/layman/.local/bin/agy` (v1.1.5). The old `scripts/delegate.py` queue
mechanism is DEPRECATED/non-functional — it wrote to a JSON queue the agent never
reliably picked up (weak-model attempts failed). Use `agy` directly.

`agy` is a large, capable model but with a LIMITED token budget. Use it ONLY for:
- complex / long-running coding tasks (multi-file refactors, debugging deep bugs)
- heavy market analysis requiring live API pulls + indicator math
- system/PC state introspection that needs long reasoning
Do NOT use it for trivial one-shot questions you can answer yourself.

## Usage (real, verified 2026-07-21)

```bash
# Non-interactive single prompt, auto-approve perms, high reasoning, give dirs:
agy --dangerously-skip-permissions --effort high \
    --add-dir /home/layman/QuantumEdge \
    --add-dir /home/layman/.hermes/quantumedge_analysis \
    --print "Детальне завдання українською..." > /tmp/agy_out.txt 2>&1
echo "EXIT=$?"
```

Flags that matter:
- `--dangerously-skip-permissions` — auto-approve tool calls. Owner confirmed this
  is the intended invocation (needed so `agy` can read files / run scripts / hit API).
- `--effort high|medium|low` — reasoning depth (use `high` for analysis/coding).
- `--add-dir <path>` — mount a workspace dir so `agy` can see files/keys/scripts
  (repeatable; give the relevant project dirs + any dir holding API keys, e.g.
  `/home/layman/QuantumEdge` for BingX VST `.env`, and
  `/home/layman/.hermes/quantumedge_analysis` for the agent's analysis contour).
- `--print` (`-p`) — run the prompt once, non-interactively, print to stdout.
- `--model <m>` — override model if needed.

## Operating pattern (verified this session)
1. Run `agy ... --print "prompt" > out.txt 2>&1` as a **background** terminal
   process for long tasks (`background=true`, `notify_on_complete=true`).
2. Poll/wait, then `read_file(out.txt)` — `agy` thinks in steps and streams a
   plan into the file before the final answer; the content is usually complete
   even while the process is still finalizing.
3. `agy` reads API keys from the mounted dirs' `.env` (e.g. BingX VST keys in
   `/home/layman/QuantumEdge/.env`) and runs the project `.venv` python — so
   delegated market analysis can pull REAL exchange data, not fabricate it.
4. Verify any numbers `agy` reports with a real tool call yourself (same
   "verify-don't-trust-coder" discipline as quantumedge-backtesting).

## Legacy
`scripts/delegate.py` is kept for reference only — it pushes to a JSON queue that
is no longer the active path. Do not rely on it.

## Delegation prompts for coding fixes
When delegating a coding fix (e.g. QuantumEdge `trader.py`), the prompt should:
name the exact file, describe the bug with a reproduction/evidence, state the
desired new behavior, preserve all owner lock-rules, and demand a REAL run as
verification (not just syntax check). See
`~/.hermes/skills/trading/liq-zone-trading/references/CODER_TASK_smart_sl.md`
for a worked example (smart SL fix for the trader brain).
