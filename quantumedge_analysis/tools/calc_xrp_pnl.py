import asyncio
import time
from qe_trade import make_ex

async def calc_pnl():
    ex = make_ex()
    try:
        since_ts = (time.time() - 3600 * 2) * 1000 # Last 2 hours
        orders = await ex.fetch_closed_orders("XRP/USDT:USDT", since=int(since_ts))
        total_pnl = 0.0
        for o in orders:
            # Check timestamp against 15:00 local (which is 12:00 UTC)
            # time.time() is UTC based. Let's just sum it all up for today.
            info = o.get("info", {})
            profit = info.get("profit")
            if profit and float(profit) != 0:
                # bingx returns realized pnl in profit field for closing orders
                total_pnl += float(profit)
        print(f"XRP Total Realized PnL: {total_pnl:.4f} VST")
    except Exception as e:
        print("Error:", e)
    finally:
        await ex.close()

asyncio.run(calc_pnl())
