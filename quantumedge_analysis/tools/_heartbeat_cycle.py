from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "trader_journal.jsonl"
record = {
    "action": "HEARTBEAT",
    "symbol": "XRPUSDT",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "price": 1.077,
    "verdict": "NEUTRAL",
    "conviction": 0.50,
    "stoch5m": 26.5,
    "note": "No sanctioned action: sigtest/confluence absent; liqmap gate not confirmed for XRP; no positions. XRP range 1.0746-1.0803. BTC correction zone 63.6-64.5k, wait sweep.",
    "next_5_15m": "Monitor StochRSI <20 at bid wall for LONG DCA or >80 at ask wall for reduce-only SHORT; do not chase.",
}
with path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
print(json.dumps(record, ensure_ascii=False))
