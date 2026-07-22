# QuestDB REST queries (QuantumEdge)

## Endpoint
- HTTP REST: `GET http://127.0.0.1:9000/exec?query=<URL-encoded SQL>`  (port 9000)
- pgwire (psql protocol): port 8812 — not used for ad-hoc curl.

URL-encode the SQL (e.g. `urllib.parse.quote(query)`).

Response shape: `{"columns":[...],"dataset":[[...]],"count":N}` or
`{"error":"table does not exist [table=...]","position":N}`.

## Tables present (QuantumEdge instance)
trades, bot_telemetry, orderbook_snapshots, klines_1m, realized_trades,
market_features, portfolio_state.

## Gotchas
- **A symbol may not be stored yet.** `klines_1m` had ONLY `BTCUSDT` in one session;
  `XRPUSDT` was absent → "table does not exist" is really "no rows for that symbol".
  Always `SHOW TABLES` first, and guard the analysis when a symbol has no history.
- Table names differ from docs: real table is `klines_1m` (docs referenced
  `bars_1m` / `microstructure_v1` which did NOT exist). Trust `SHOW TABLES`.

## Examples
```sql
SHOW TABLES;

SELECT close FROM klines_1m
WHERE symbol='XRPUSDT' AND ts > dateadd('m', -60, now())
ORDER BY ts DESC LIMIT 60;

SELECT symbol FROM klines_1m LIMIT 5;   -- see which symbols exist
```
