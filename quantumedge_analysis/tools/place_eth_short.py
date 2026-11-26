import asyncio, os
from dotenv import load_dotenv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
import ccxt.async_support as ccxt

async def place_order():
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    use_testnet = str(os.getenv("USE_TESTNET", "1")).lower() in {"1", "true", "t"}

    ex = ccxt.bingx({
        "apiKey": ak, "secret": sc,
        "options": {"defaultType": "swap"},
        "enableRateLimit": True
    })
    if use_testnet: ex.set_sandbox_mode(True)
    await ex.load_markets()

    symbol = "ETH/USDT:USDT"
    try:
        order = await ex.create_order(
            symbol=symbol,
            type="limit",
            side="sell",
            amount=10.0,
            price=1925.25,
            params={"positionSide": "SHORT"}
        )
        print(f"[ETH SHORT] Placed LIMIT SELL (Open Short) 10 ETH @ 1925.25. Order ID: {order.get('id')}")
    except Exception as e:
        print(f"[ERROR] {e}")

    await ex.close()

if __name__ == "__main__":
    asyncio.run(place_order())
