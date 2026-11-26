import asyncio, os, sys, time, json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from qe_trade import make_ex

async def main():
    ex = make_ex()
    try:
        since_ts = int((time.time() - 16 * 3600) * 1000)
        orders = await ex.fetch_closed_orders("XRP/USDT:USDT", since=since_ts, limit=50)
        print("Останні закриті ордери по XRP:")
        count = 0
        total = 0
        for o in orders:
            info = o.get("info", {})
            profit = float(info.get("profit") or 0)
            status = info.get("status")
            side = info.get("side")
            pos_side = info.get("positionSide")
            qty = o.get("filled")
            price = o.get("average")
            if profit != 0:
                print(f"ID: {o['id']} | {side} {pos_side} | Qty: {qty} | Price: {price} | Profit: {profit}")
                total += profit
                count += 1
        print(f"Total shown: {count}, Sum Profit: {total}")
    finally:
        await ex.close()

asyncio.run(main())
