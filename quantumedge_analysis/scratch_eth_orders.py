import asyncio, os
import ccxt.async_support as ccxt
from dotenv import load_dotenv
load_dotenv("/home/layman/.hermes/quantumedge_analysis/.env")

async def get_ex():
    ak = os.getenv("BINGX_TESTNET_API_KEY")
    sc = os.getenv("BINGX_TESTNET_SECRET")
    ex = ccxt.bingx({"apiKey": ak, "secret": sc, "options": {"defaultType": "swap"}, "enableRateLimit": True})
    ex.set_sandbox_mode(True)
    await ex.load_markets()
    orders = await ex.fetch_open_orders("ETH/USDT:USDT")
    print(f"Open ETH Orders ({len(orders)}):")
    for o in orders:
        info = o.get("info", {})
        print(f"Side: {o['side']}, PosSide: {info.get('positionSide')}, Price: {o['price']}, Trigger: {info.get('triggerPrice')}, Qty: {o['amount']}, Type: {info.get('type')}")
    await ex.close()
asyncio.run(get_ex())
