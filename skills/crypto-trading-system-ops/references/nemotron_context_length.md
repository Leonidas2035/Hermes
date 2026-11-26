# Model Context Length Configuration — Nemotron 3 Ultra on OpenRouter

**Session:** 2026-07-31  
**Issue:** User noticed discrepancy between Hermes config `context_length: 65536` and Nemotron 3 Ultra's true context window.

## Configuration in `~/.hermes/config.yaml`
```yaml
model:
  default: nvidia/nemotron-3-ultra-550b-a55b:free
  provider: openrouter
  context_length: 65536      # ← Hermes agent cap (64K tokens)
  ollama_num_ctx: 65536
```

## Reality Check

| Layer | Context Limit | Notes |
|-------|--------------|-------|
| **Hermes Agent (config)** | **65,536 tokens** | Hard cap enforced by agent when building request payload. Truncates history/tools if exceeded. |
| **Nemotron 3 Ultra (model)** | **~128K–256K+** | Actual model capacity on NVIDIA/OpenRouter. |
| **OpenRouter API** | Varies by model | May enforce its own limit; returns `400 Context length exceeded` if breached. |

## Why 64K Default?
- **Cost control** — larger context = more tokens = higher API cost
- **Latency** — bigger prompts = slower first token
- **Safety margin** — leaves room for tool outputs, system prompts, response tokens
- **Most tasks fit** — trading cycles, code review, analysis all fit comfortably in 64K

## When to Increase
Only if you hit **actual truncation symptoms**:
- Agent "forgets" earlier in conversation
- Tool outputs get cut mid-stream
- Explicit `context_length_exceeded` error from API

## How to Change
```bash
# Option 1: CLI
hermes config set model.context_length 131072

# Option 2: Edit ~/.hermes/config.yaml directly
# context_length: 131072  # 128K
```

## Recommendation for QuantumEdge
**Keep at 65536.** The 5m trading cycle (macro + _agy_now + market_analysis + latest.json + decision) uses ~15-20K tokens. 64K gives 3x headroom. Increasing risks hitting OpenRouter's actual limit and getting 400 errors.

## Related Files
- `~/.hermes/config.yaml` — main config
- `skills/crypto-trading-system-ops/references/hermes_dna_v3.md` — initialization sequence that reads this config