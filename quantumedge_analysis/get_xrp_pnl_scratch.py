import asyncio
import datetime
import sys
sys.path.append("/home/layman/.hermes/quantumedge_analysis/tools")
from qe_trade import make_ex

async def calc_pnl():
    ex = make_ex()
    try:
        # UTC time for 2026-07-30 15:00:00
        dt = datetime.datetime(2026, 7, 30, 15, 0, 0, tzinfo=datetime.timezone.utc)
        since_ts = int(dt.timestamp() * 1000)
        orders = await ex.fetch_closed_orders("XRP/USDT:USDT", since=since_ts, limit=1000)
        total_pnl = 0.0
        closed_count = 0
        for o in orders:
            info = o.get("info", {})
            profit = info.get("profit")
            if profit and float(profit) != 0:
                total_pnl += float(profit)
                closed_count += 1
        print(f"XRP Orders Closed Since 15:00 UTC: {closed_count}")
        print(f"XRP Total Realized PnL Since 15:00 UTC: {total_pnl:.4f} VST")
    except Exception as e:
        print("Error:", e)
    finally:
        await ex.close()

asyncio.run(calc_pnl())
