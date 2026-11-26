import asyncio, os
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

import ccxt.async_support as ccxt

async def set_eth_tp():
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
    # Create Take Profit Sell Limit Order @ 1926.30 for 7.00 ETH (Full position, +100 VST)
    try:
        order = await ex.create_order(
            symbol=symbol,
            type="limit",
            side="sell",
            amount=7.00,
            price=1926.30,
            params={"positionSide": "LONG"}
        )
        print(f"[ETH TP SET] Successfully placed SELL LIMIT 7.00 ETH @ $1,926.30! Order ID: {order.get('id')}")
    except Exception as e:
        print(f"[ETH TP ERROR] Could not place TP limit order: {e}")

    await ex.close()

if __name__ == "__main__":
    asyncio.run(set_eth_tp())
