"""
Supervisor SAFE ACTIONS — user-sanctioned ONLY. Executes:
  B) Cancel ALL open orders for symbol (does NOT close positions).
  C) Partial close of SHORT (buy-to-cover, hedge mode) to free margin.
Set SUPERVISOR_SHORT_CLOSE_QTY env to control C volume (default 425000).
Usage: .venv/bin/python3 scripts/bingx_safe_actions.py
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
SHORT_CLOSE_QTY = float(os.getenv("SUPERVISOR_SHORT_CLOSE_QTY", "425000"))


async def main():
    api_key = (os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")) if USE_TESTNET \
        else os.getenv("BINGX_API_KEY", "")
    secret = (os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")) if USE_TESTNET \
        else os.getenv("BINGX_SECRET", "")
    ex = ccxt.bingx({"apiKey": api_key, "secret": secret,
                     "options": {"defaultType": "swap"}, "enableRateLimit": True, "timeout": 30000})
    if USE_TESTNET:
        ex.set_sandbox_mode(True)
        print("[ACTION] VST (DEMO) MODE")
    try:
        print(f"\n=== B) CANCEL ALL OPEN ORDERS ({CCXT_SYMBOL}) ===")
        try:
            cancelled = await ex.cancel_all_orders(symbol=CCXT_SYMBOL)
            print(f"  cancelled; count={len(cancelled) if isinstance(cancelled, list) else 'n/a'}")
        except Exception as e:
            print(f"  cancel error: {e}")
        print(f"\n=== C) PARTIAL CLOSE SHORT ({SHORT_CLOSE_QTY} contracts, buy/SHORT) ===")
        try:
            order = await ex.create_order(symbol=CCXT_SYMBOL, type="market", side="buy",
                                          amount=SHORT_CLOSE_QTY, params={"positionSide": "SHORT"})
            print(f"  placed id={order.get('id')} status={order.get('status')}")
        except Exception as e:
            print(f"  close error: {e}")
        print(f"\n=== VERIFY POSITIONS ({CCXT_SYMBOL}) ===")
        await ex.load_markets()
        pos = await ex.fetch_positions(symbols=[CCXT_SYMBOL])
        for p in [p for p in pos if float(p.get('contracts') or p.get('size') or 0) != 0]:
            print(f"  {p.get('side')} size={p.get('contracts')} entry={p.get('entryPrice')} uPnL={p.get('unrealizedPnl')}")
        print(f"\n=== VERIFY OPEN ORDERS ({CCXT_SYMBOL}) ===")
        orders = await ex.fetch_open_orders(symbol=CCXT_SYMBOL)
        print(f"  remaining open orders: {len(orders)}")
    except Exception as e:
        print(f"[ACTION] fatal: {e}")
    finally:
        try:
            ex.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
