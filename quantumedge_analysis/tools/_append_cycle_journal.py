from datetime import datetime, timezone
import json
from pathlib import Path

path = Path('/home/layman/.hermes/quantumedge_analysis/trader_journal.jsonl')
now = datetime.now(timezone.utc).isoformat()
rows = [
    {
        'action': 'CANCEL_INVALID_SHORT_LIMITS',
        'symbol': 'XRPUSDT',
        'timestamp_utc': now,
        'result': '14 original + 13 regenerated SHORT limit orders cancelled; xrp_hft_daemon stopped to prevent non-reduce-only shorts without a LONG leg.',
        'price': 1.0755,
        'legs': [],
        'open_orders_count': 0,
    },
    {
        'action': 'HEARTBEAT',
        'symbol': 'XRPUSDT',
        'timestamp_utc': now,
        'price': 1.0755,
        'verdict': 'NEUTRAL',
        'conviction': 0.5,
        'note': 'BTC 63928.1 remains in 63.6-64.5k correction zone; XRP below VWAP but MACD/BB and StochRSI/sigtest/liqmap confluence is absent. No positions, no open orders, free margin 100%.',
        'next_5_15m': 'No entry. Recheck fresh snapshot and wait for StochRSI <20 at support with sigtest + liqmap <=2%; do not restart HFT daemon until its short path is reduce-only against an existing LONG.',
    },
]
with path.open('a', encoding='utf-8') as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
print(json.dumps({'appended': len(rows), 'path': str(path)}, ensure_ascii=False))
CYCLE_JOURNAL_APPEND_OK = True
