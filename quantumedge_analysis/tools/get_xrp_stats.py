import asyncio
import datetime
import sys
sys.path.append("/home/layman/.hermes/quantumedge_analysis/tools")
from qe_trade import make_ex

async def calc_pnl():
    ex = make_ex()
    try:
        # Fetch up to 1000 recent closed orders for XRP
        orders = await ex.fetch_closed_orders("XRP/USDT:USDT", limit=1000)
        total_pnl = 0.0
        closed_count = 0
        first_ts = None
        last_ts = None
        
        for o in sorted(orders, key=lambda x: x['timestamp']):
            info = o.get("info", {})
            profit = info.get("profit")
            if profit and float(profit) != 0:
                if first_ts is None:
                    first_ts = o['timestamp']
                last_ts = o['timestamp']
                total_pnl += float(profit)
                closed_count += 1
                
        print(f"XRP Orders Closed: {closed_count}")
        print(f"XRP Total Realized PnL: {total_pnl:.4f} VST")
        
        if first_ts and last_ts:
            dt_first = datetime.datetime.fromtimestamp(first_ts/1000, tz=datetime.timezone.utc)
            dt_now = datetime.datetime.now(tz=datetime.timezone.utc)
            diff = dt_now - dt_first
            hours = diff.total_seconds() / 3600
            print(f"First trade: {dt_first.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"Hours since first trade: {hours:.2f}")
    except Exception as e:
        print("Error:", e)
    finally:
        await ex.close()

if __name__ == "__main__":
    asyncio.run(calc_pnl())
