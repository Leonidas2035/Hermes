import asyncio
from qe_trade import make_ex

async def main():
    ex = make_ex()
    try:
        # Place limit sell at 1.15 with a Limit TP at 1.10
        params = {
            "positionSide": "SHORT",
            "hedged": True,
            "takeProfit": {
                "triggerPrice": 1.10,
                "price": 1.10,
                "type": "limit"
            }
        }
        order = await ex.create_order("XRP/USDT:USDT", "limit", "sell", 100, 1.15, params)
        print("Success:", order['id'])
        # Clean up
        await ex.cancel_order(order['id'], "XRP/USDT:USDT")
    except Exception as e:
        print("Error:", e)
    finally:
        await ex.close()

asyncio.run(main())
