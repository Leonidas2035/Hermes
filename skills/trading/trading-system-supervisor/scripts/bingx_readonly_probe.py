"""
Supervisor READ-ONLY probe: connect to BingX (testnet/VST) and report
balance, open positions, and open orders for the configured symbol.

NO orders are placed. Strictly read-only.
Usage: .venv/bin/python3 scripts/bingx_readonly_probe.py
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
import ccxt.async_support as ccxt

SYMBOL = os.getenv("MARKET_DATA_SYMBOLS", "XRPUSDT").split(",")[0]
USE_TESTNET = str(os.getenv("USE_TESTNET", os.getenv("BINANCE_TESTNET", "1"))).lower() in {"1", "true", "t"}
BASE = SYMBOL.replace("USDT", "")
CCXT_SYMBOL = f"{BASE}/USDT:USDT"


async def main():
    print(f"[PROBE] symbol={SYMBOL} ccxt={CCXT_SYMBOL} testnet={USE_TESTNET}")
    api_key = (os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")) if USE_TESTNET \
        else os.getenv("BINGX_API_KEY", "")
    secret = (os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")) if USE_TESTNET \
        else os.getenv("BINGX_SECRET", "")
    if not api_key or not secret:
        print("[PROBE] no API creds in env; abort (read-only).")
        return
    ex = ccxt.bingx({"apiKey": api_key, "secret": secret,
                     "options": {"defaultType": "swap"}, "enableRateLimit": True, "timeout": 30000})
    if USE_TESTNET:
        ex.set_sandbox_mode(True)
        print("[PROBE] VST (DEMO) MODE — read-only")
    try:
        await ex.load_markets()
        ex.options["defaultType"] = "swap"
        bal = await ex.fetch_balance()
        quote = "VST" if USE_TESTNET else "USDT"
        q = bal.get(quote, {})
        print(f"\n=== BALANCE (swap/{quote}) ===")
        print(f"  total={q.get('total')} free={q.get('free')} used={q.get('used')}")
        print(f"\n=== POSITIONS ({CCXT_SYMBOL}) ===")
        pos = await ex.fetch_positions(symbols=[CCXT_SYMBOL])
        open_pos = [p for p in pos if float(p.get('contracts') or p.get('size') or 0) != 0]
        if not open_pos:
            print("  (no open positions)")
        for p in open_pos:
            print(f"  {p.get('symbol')} side={p.get('side')} size={p.get('contracts')} "
                  f"entry={p.get('entryPrice')} uPnL={p.get('unrealizedPnl')} lev={p.get('leverage')}")
        print(f"\n=== OPEN ORDERS ({CCXT_SYMBOL}) ===")
        orders = await ex.fetch_open_orders(symbol=CCXT_SYMBOL)
        if not orders:
            print("  (none — exchange likely blocking new orders due to drawdown)")
        for o in orders[:30]:
            print(f"  id={o.get('id')} {o.get('side')} {o.get('type')} amt={o.get('amount')} @ {o.get('price')} {o.get('status')}")
        if len(orders) > 30:
            print(f"  ...+{len(orders)-30} more")
    except Exception as e:
        print(f"[PROBE] error: {e}")
    finally:
        try:
            ex.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
