# BingX via ccxt — quick reference

QuantumEdge `.venv` ships `ccxt 4.5.64`.

## Critical
- Use `import ccxt.async_support as ccxt` (NOT `import ccxt`) when awaiting calls.
- `ex.close()` is SYNC in 4.5 — call `ex.close()` not `await ex.close()`.

## Init (testnet / VST)
```python
import ccxt.async_support as ccxt
ex = ccxt.bingx({
    "apiKey": os.getenv("BINGX_TESTNET_API_KEY"),
    "secret": os.getenv("BINGX_TESTNET_SECRET"),
    "options": {"defaultType": "swap"},
    "enableRateLimit": True, "timeout": 30000,
})
ex.set_sandbox_mode(True)   # VST demo
```

## Symbol format
- Spot: `XRP/USDT`  |  Swap/perp: `XRP/USDT:USDT`  (base/USDT:USDT)

## Read calls
- `await ex.fetch_balance()` → swap account; on testnet the quote key is **`VST`**
  (not `USDT`): `bal.get("VST", {}).get("free")`.
- `await ex.fetch_positions(symbols=[sym])` → list; nonzero `contracts` = open.
  Fields: `side`, `contracts`, `entryPrice`, `unrealizedPnl`, `leverage`.
- `await ex.fetch_open_orders(symbol=sym)` → list of resting orders.
- `await ex.fetch_funding_rate(sym)` → `fundingRate`, `markPrice`, `indexPrice`.
- `await ex.fetch_open_interest(sym)` → `openInterestValue` (USD notional).

## Write calls (NEED explicit user sanction)
- `await ex.cancel_all_orders(symbol=sym)` → list. Idempotent & safe (does NOT
  close positions). Use to clear dead resting orders.
- `await ex.create_order(symbol, "market", "buy", qty,
   params={"positionSide": "SHORT"})` → buy-to-cover to reduce a SHORT in hedge
  mode. This is a REAL position-reducing action — confirm volume first.

## Error to expect
- `{"code":101204,"msg":"Insufficient margin"}` → free margin is 0 (over-exposed /
  drawdown). Exchange blocks new orders until margin frees up. Not a code bug.
