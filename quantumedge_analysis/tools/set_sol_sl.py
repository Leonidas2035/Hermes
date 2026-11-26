import asyncio, os
from dotenv import load_dotenv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
import ccxt.async_support as ccxt

async def place_sl():
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    use_testnet = str(os.getenv("USE_TESTNET", "1")).lower() in {"1", "true", "t"}
    ex = ccxt.bingx({"apiKey": ak, "secret": sc, "options": {"defaultType": "swap"}})
    if use_testnet: ex.set_sandbox_mode(True)
    await ex.load_markets()
    
    try:
        await ex.create_order(
            symbol="SOL/USDT:USDT", type="STOP_MARKET", side="sell", amount=3356.34,
            params={"positionSide": "LONG", "triggerPrice": 74.263}
        )
        print("SL placed for SOL Swing Long.")
    except Exception as e:
        print(f"Error: {e}")
    await ex.close()

if __name__ == "__main__":
    asyncio.run(place_sl())
