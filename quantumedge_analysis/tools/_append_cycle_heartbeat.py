import json
from datetime import datetime, timezone
from pathlib import Path

payload = {
    "action": "HEARTBEAT",
    "symbol": "XRPUSDT",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "price": 1.0755,
    "verdict": "HOLD",
    "conviction": 0.67,
    "positions": 0,
    "open_orders": 0,
    "free_margin_pct": 100.0,
    "note": "Fresh snapshot: no positions/orders. MACD bullish but StochRSI 63.93 neutral, TV Strong Sell, BTC 64002.2 in 63.6-64.5k correction zone; sigtest/liqmap gate not confirmed. No trade.",
    "next_5_15m": "Wait for StochRSI <20 near support 1.0744/1.0709 plus sigtest and liqmap <=2%; no SHORT without existing LONG."
}
path = Path(__file__).resolve().parents[1] / "trader_journal.jsonl"
with path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
print(json.dumps(payload, ensure_ascii=False))
