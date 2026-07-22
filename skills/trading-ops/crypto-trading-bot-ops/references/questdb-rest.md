# QuestDB REST querying

## Endpoint
HTTP REST on port 9000:
`http://127.0.0.1:9000/exec?query=<urlencoded SQL>`

Response:
`{"columns":[{"name":..,"type":..}],"dataset":[[..],[..]],"count":N}`
or on error `{"query":..,"error":"<msg>","position":N}`.

Call from Python via curl/subprocess:
```python
import subprocess, urllib.parse
q = ("SELECT close, volume FROM klines_1m "
     "WHERE symbol='XRPUSDT' AND timestamp > dateadd('m', -60, now()) "
     "ORDER BY timestamp DESC LIMIT 60")
url = "http://127.0.0.1:9000/exec?query=" + urllib.parse.quote(q)
out = subprocess.run(["curl","-s",url], capture_output=True, text=True, timeout=15)
data = json.loads(out.stdout)
if "dataset" in data:
    closes = [row[0] for row in data["dataset"]]
```

## CRITICAL: timestamp column is `timestamp`, NOT `ts`
`ORDER BY ts` / `WHERE ts > ...` → `Invalid column: ts`.
Designated timestamp column in this schema is `timestamp`. Always use it.

## Tables (this schema)
- `klines_1m` — symbol, open, high, low, close, volume, trades_count, timestamp
- `microstructure_v1` — symbol, best_bid/ask px+qty, ofi_raw, ofi_z, ofi_ma5, spread_bps, top_qty_sum, trade_rate_1s, volume_1s, ts_event, timestamp
- `market_features` — symbol, mid_price, spread, ofi_raw, volume_delta, timestamp
- `trades`, `portfolio_state`, `realized_trades`, `orderbook_snapshots`, `bot_telemetry`

## Notes
- `SHOW TABLES` lists all tables.
- A symbol may have huge history (XRPUSDT ~188k rows) even if a `LIMIT 5` sample
  shows only other symbols — always filter by `symbol='...'` and don't infer
  "no history" from a small ungrouped LIMIT.
