#!/usr/bin/env bash
# HERMES QuantumEdge Initialization Sequence
# Runs Phase 1-5 of the mandatory initialization protocol
# Usage: ./scripts/hermes_init.sh

set -euo pipefail

QE_DIR="/home/layman/.hermes/quantumedge_analysis"
VENV_PY="$QE_DIR/venv/bin/python3"

echo "=========================================="
echo "🧬 HERMES QUANTUMEDGE INITIALIZATION v3.0"
echo "=========================================="

# Phase 1: Read DNA (informational - agent reads these)
echo "📖 Phase 1: DNA Files (agent reads these)"
ls -la "$QE_DIR/AI_CORE_MEMORY.md" "$QE_DIR/HERMES_DISTILLED_SOUL.md" "$QE_DIR/FULL_SYSTEM_CONTEXT.txt" "$QE_DIR/RULES.md"

# Phase 2: HFT Daemon Check/Start
echo ""
echo "⚡ Phase 2: HFT XRP Daemon"
if pgrep -f "xrp_hft_daemon.py" > /dev/null; then
    echo "  ✅ Already running (PIDs: $(pgrep -f xrp_hft_daemon.py | tr '\n' ' '))"
else
    echo "  🚀 Starting daemon..."
    cd "$QE_DIR"
    nohup "$VENV_PY" tools/xrp_hft_daemon.py > /tmp/xrp_hft.log 2>&1 &
    sleep 3
    if pgrep -f "xrp_hft_daemon.py" > /dev/null; then
        echo "  ✅ Started (PIDs: $(pgrep -f xrp_hft_daemon.py | tr '\n' ' '))"
    else
        echo "  ❌ FAILED to start! Check /tmp/xrp_hft.log"
        exit 1
    fi
fi

# Phase 3: Market Snapshot
echo ""
echo "📊 Phase 3: Market Snapshot Sequence"
cd "$QE_DIR"
echo "  1/3 macro_data.py..."
"$VENV_PY" macro_data.py
echo "  2/3 _agy_now.py..."
"$VENV_PY" _agy_now.py
echo "  3/3 market_analysis.py..."
"$VENV_PY" market_analysis.py

# Phase 4: Verify latest.json exists
echo ""
echo "🤖 Phase 4: AI Analysis Ready"
if [[ -f "$QE_DIR/latest.json" ]]; then
    echo "  ✅ latest.json generated ($(stat -c%s "$QE_DIR/latest.json") bytes)"
    echo "  📍 Key levels: $(jq -r '.levels | "\(.entry_zone) / \(.tp1) / \(.tp2) / \(.stop_loss)"' "$QE_DIR/latest.json" 2>/dev/null || echo "parse error")"
else
    echo "  ❌ latest.json NOT FOUND!"
    exit 1
fi

# Phase 5: Cron Job (informational - agent creates this via tool)
echo ""
echo "⏰ Phase 5: 5m Cron Cycle"
echo "  → Agent will create via cronjob tool with schedule '*/5 * * * *'"
echo "  → Workdir: $QE_DIR"
echo "  → Toolsets: terminal, file"

echo ""
echo "=========================================="
echo "✅ INITIALIZATION COMPLETE — Hermes Active"
echo "=========================================="