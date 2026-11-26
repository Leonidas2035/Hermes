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
        orders = await ex.fetch_closed_orders("XRP/USDT:USDT", since=since_ts, limit=100)
        total_pnl = 0.0
        for o in orders:
            profit = o.get("info", {}).get("profit")
            if profit and float(profit) != 0:
                total_pnl += float(profit)
        print(f"5M_PROFIT: {total_pnl:.4f}")
    except Exception as e:
        print("Error:", e)
    finally:
        await ex.close()

if __name__ == "__main__":
    asyncio.run(check())
