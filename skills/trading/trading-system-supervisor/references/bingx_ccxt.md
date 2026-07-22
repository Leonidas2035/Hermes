# BingX ccxt connection recipe (VST / testnet)

Verified working on: `ccxt 4.5.64`, `python 3.12`, QuantumEdge deployment.

## Minimal connect (READ-ONLY)

```python
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
import ccxt.async_support as ccxt   # MUST be async_support, not sync ccxt

SYMBOL = os.getenv("MARKET_DATA_SYMBOLS", "XRPUSDT").split(",")[0]
USE_TESTNET = str(os.getenv("USE_TESTNET", os.getenv("BINANCE_TESTNET", "1"))).lower() in {"1","true","t"}
BASE = SYMBOL.replace("USDT", "")
CCXT_SYMBOL = f"{BASE}/USDT:USDT"   # swap/perp format

async def probe():
    api_key = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    secret  = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    ex = ccxt.bingx({"apiKey": api_key, "secret": secret,
                     "options": {"defaultType": "swap"}, "enableRateLimit": True, "timeout": 30000})
    if USE_TESTNET:
        ex.set_sandbox_mode(True)
    await ex.load_markets()
    ex.options["defaultType"] = "swap"          # balance is on swap account in VST
    bal = await ex.fetch_balance()
    quote = "VST" if USE_TESTNET else "USDT"     # VST, not USDT, in testnet swap
    print("free", bal.get(quote, {}).get("free"), "used", bal.get(quote, {}).get("used"))
    pos = await ex.fetch_positions(symbols=[CCXT_SYMBOL])
    orders = await ex.fetch_open_orders(symbol=CCXT_SYMBOL)
    # ...print...
    ex.close()   # NOTE: returns None in 4.5 — do NOT `await` it
```

## Gotchas

- **Sync import**: `import ccxt` → methods return dicts; `await load_markets()`
  raises `object dict can't be used in 'await' expression`. Use `async_support`.
- **Quote asset**: testnet swap uses `VST`, mainnet uses `USDT`.
- **Symbol**: swap = `XRP/USDT:USDT`. Spot = `XRP/USDT`.
- **close()**: returns `None`; call without `await`, wrap in try/except.
- **Hedge mode close**: to reduce a SHORT, `create_order(..., side="buy",
  params={"positionSide": "SHORT"})`.

## Exchange errors seen

- `101204 "Insufficient margin"` — account 100% margin-locked (free=0). New
  orders rejected. NOT a code bug; fix by freeing margin (cancel stale orders
  + partial close), then bots resume automatically.
