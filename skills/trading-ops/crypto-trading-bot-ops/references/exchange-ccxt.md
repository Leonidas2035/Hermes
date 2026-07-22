# ccxt async + BingX VST recipes

## The async pitfall
In asyncio code ALWAYS: `import ccxt.async_support as ccxt`
Sync `import ccxt` + `await ex.load_markets()` →
`TypeError: object dict can't be used in 'await' expression`
(sync methods return dicts, not coroutines).

## BingX init
```python
ex = ccxt.bingx({
    "apiKey": ak, "secret": sc,
    "options": {"defaultType": "swap"},
    "enableRateLimit": True, "timeout": 30000,
})
if use_testnet:
    ex.set_sandbox_mode(True)   # VST demo mode
```

## Symbol formats
- Swap/perp: `XRP/USDT:USDT`
- Spot:       `XRP/USDT`

## Read-only (safe) calls
- `await ex.fetch_balance()` → `bal['VST']['free'|'total'|'used']` (swap account)
- `await ex.fetch_positions(symbols=[sym])` → each pos: `contracts`(size), `entryPrice`, `unrealizedPnl`, `side`, `leverage`
- `await ex.fetch_open_orders(symbol=sym)` → list of orders

## Derivatives
- Funding: `r = await ex.fetch_funding_rate(sym)` → `r['fundingRate']`, `r['markPrice']`, `r['indexPrice']`
  - positive funding → longs pay shorts → mild bull tilt
- Open Interest: `r = await ex.fetch_open_interest(sym)` → `r['openInterestValue']` (USD notional)

## Actions (place trades — use with sanction)
- Cancel ALL open orders (does NOT close positions): `await ex.cancel_all_orders(sym)`
- Hedge-mode partial close of SHORT (buy-to-cover):
  `await ex.create_order(sym, "market", "buy", qty, params={"positionSide": "SHORT"})`
- Normal order: `await ex.create_order(sym, "limit", side, amount, price, params={"positionSide": "LONG"})`

## Closing
`ex.close()` is SYNC in ccxt 4.5 (returns None). Call `ex.close()`, do NOT `await ex.close()`
(would warn "coroutine 'Exchange.close' was never awaited").

## BingX error codes seen
- `101204 Insufficient margin` — free margin is 0; new orders blocked (drawdown/over-exposure).
- `109429 over 20 error code:101204 ... within 480000 ms` — rate-limit escalation; back off.

## Env for read-only probe
`USE_TESTNET=true`, `BINGX_TESTNET_API_KEY` / `BINGX_TESTNET_SECRET`
(fall back to `BINGX_API_KEY` / `BINGX_SECRET` for mainnet — NEVER use mainnet without explicit sanction).
