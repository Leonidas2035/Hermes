import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from qe_trade import make_ex

async def check():
    ex = make_ex()
    try:
        orders = await ex.fetch_closed_orders("XRP/USDT:USDT", limit=10)
        # Find the most recent order with profit > 0 or profit < 0
        for o in sorted(orders, key=lambda x: x['timestamp'], reverse=True):
            profit = o.get("info", {}).get("profit")
            if profit and float(profit) != 0:
                print(f"LAST_PROFIT: {profit}")
                break
    except Exception as e:
        print("Error:", e)
    finally:
        await ex.close()

if __name__ == "__main__":
    asyncio.run(check())
