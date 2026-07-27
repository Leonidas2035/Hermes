# 🚀 ARCHITECTURAL MIGRATION PLAN: AGY CLI TO NATIVE GOOGLE GENAI SDK

> **Author:** Senior AI Migration Architect (Hermes Project)  
> **Target:** Seamless transition from CLI subprocessing (`agy`) to direct Python SDK (`google-genai`) integration.

---

## 🎯 1. ARCHITECTURAL OVERVIEW & MOTIVATION

Currently, `trader.py` and `hermes_live.sh` invoke the Antigravity engine by launching an external shell subprocess:
```python
subprocess.run(["agy", "--model", "Gemini 3.6 Flash (High)", "--print", prompt])
```
While functional, CLI wrapper execution introduces overhead, dependency on external binary flags (e.g. `--conversation` flag changes), and parsing risk.

**Native API Migration Objectives:**
1. **Zero External Binary Dependencies:** Native execution directly via `pip install google-genai`.
2. **Sub-second Latency:** Direct async HTTP/gRPC calls to Gemini API.
3. **Robust State Persistence:** In-memory + JSON history storage (`runtime/native_session_history.json`).
4. **Structured JSON Output:** Native Pydantic / Schema enforcement for trading commands.

---

## 🏗️ 2. COMPONENT AUDIT & MIGRATION STRATEGY

| Component | Current State | Migrated Native State |
| :--- | :--- | :--- |
| **Orchestrator** | `trader.py` (subprocess `agy`) | `trader_native.py` (`google.genai.Client`) |
| **Market Brain** | `market_analysis.py` | Kept intact (generates `latest.json`) |
| **Execution Toolkit** | `tools/qe_trade.py` | Kept intact (enforces hardware guardrails) |
| **Live Loop** | `hermes_live.sh` | `hermes_live_native.py` or updated shell loop |
| **Session Memory** | `agy` CLI SQLite | `runtime/native_session_history.json` |

---

## 💻 3. IMPLEMENTATION SPECIFICATION (`trader_native.py`)

### A. Environment Configuration (`.env`)
```bash
GEMINI_API_KEY="AIzaSy..."
GEMINI_MODEL="gemini-2.5-flash"  # or gemini-2.5-pro
USE_TESTNET="1"
```

### B. Core Python Code Snippet (`trader_native.py`)
```python
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# 1. Initialize Native Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SOUL_PATH = Path("/home/layman/.hermes/quantumedge_analysis/HERMES_DISTILLED_SOUL.md")
HISTORY_PATH = Path("/home/layman/.hermes/quantumedge_analysis/runtime/native_session_history.json")

def load_system_soul() -> str:
    return SOUL_PATH.read_text() if SOUL_PATH.exists() else "You are Hermes Quant Trader."

def run_native_cycle(market_snapshot: dict) -> dict:
    system_instruction = load_system_soul()
    
    # 2. Build User Prompt
    prompt = f"""[MARKET TRIGGER CYCLE]:
Current Market Snapshot:
{json.dumps(market_snapshot, indent=2)}

Analyze indicators and orderbook. Apply Hermes Trading DNA rules.
Output execution commands in a JSON array:
[
  ["place", "buy", "LONG", 150.0, 75.95, "SOL"],
  ["place", "sell", "SHORT", 100000.0, 1.1105, "XRP"]
]
If no action, output: []
"""
    
    # 3. Call Native API
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            response_mime_type="application/json"
        )
    )
    
    return json.loads(response.text)
```

---

## 📅 4. STEP-BY-STEP MIGRATION ROADMAP

1. **Dependencies Setup:**
   ```bash
   /home/layman/.hermes/quantumedge_analysis/venv/bin/pip install google-genai pydantic
   ```
2. **Deploy `trader_native.py`:** Create and validate native trader script alongside `trader.py`.
3. **Update Cron Script (`cron_5m_native.sh`):** Replace `agy` CLI command with `/home/layman/.hermes/quantumedge_analysis/venv/bin/python3 trader_native.py`.
4. **Validation Test:** Run single test cycle and inspect `runtime/trade_journal.jsonl`.
