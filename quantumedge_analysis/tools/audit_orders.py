import asyncio
import os
import ccxt.async_support as ccxt
from dotenv import load_dotenv

load_dotenv()
USE_TESTNET = str(os.getenv("USE_TESTNET", "1")).lower() in {"1","true","t"}

async def main():
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    ex = ccxt.bingx({"apiKey":ak, "secret":sc, "options":{"defaultType":"swap"}})
    if USE_TESTNET: ex.set_sandbox_mode(True)
    
    orders = await ex.fetch_open_orders("XRP/USDT:USDT")
    print(f"Total open orders: {len(orders)}")
    prices = [o.get("price") for o in orders if o.get("price") is not None]
    if prices:
        print(f"Prices range: min {min(prices)} to max {max(prices)}")
    else:
        print("No prices found")
    await ex.close()

asyncio.run(main())
