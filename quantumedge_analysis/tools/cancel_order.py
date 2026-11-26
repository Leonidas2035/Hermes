import asyncio, os
from dotenv import load_dotenv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
import ccxt.async_support as ccxt

async def cancel():
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    use_testnet = str(os.getenv("USE_TESTNET", "1")).lower() in {"1", "true", "t"}
    ex = ccxt.bingx({"apiKey": ak, "secret": sc, "options": {"defaultType": "swap"}})
    if use_testnet: ex.set_sandbox_mode(True)
    await ex.load_markets()
    try:
        await ex.cancel_order("2082926173987278848", "ETH/USDT:USDT")
        print("Canceled user manual short order 2082926173987278848.")
    except Exception as e:
        print(e)
    await ex.close()

if __name__ == "__main__":
    asyncio.run(cancel())
