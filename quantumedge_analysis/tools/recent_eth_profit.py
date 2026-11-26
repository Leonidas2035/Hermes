import asyncio
import os
import sys
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from qe_trade import make_ex

async def check():
    ex = make_ex()
    try:
        # last 5 minutes
        since_ts = int((time.time() - 300) * 1000)
        orders = await ex.fetch_closed_orders("ETH/USDT:USDT", since=since_ts, limit=10)
        for o in orders:
            profit = o.get("info", {}).get("profit")
            if profit and float(profit) != 0:
                print(f"ETH_PROFIT: {profit}")
    except Exception as e:
        print("Error:", e)
    finally:
        await ex.close()

if __name__ == "__main__":
    asyncio.run(check())
