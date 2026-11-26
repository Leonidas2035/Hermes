import asyncio, os, sys, time, json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from qe_trade import make_ex

async def main():
    ex = make_ex()
    try:
        # last 10 hours
        since_ts = int((time.time() - 10 * 3600) * 1000)
        current_since = since_ts
        trades = []
        while True:
            orders = await ex.fetch_closed_orders("XRP/USDT:USDT", since=current_since, limit=100)
            if not orders:
                break
            for o in orders:
                info = o.get("info", {})
                profit = float(info.get("profit") or 0)
                if profit != 0:
                    trades.append(o)
            last_ts = orders[-1]['timestamp']
            if last_ts > current_since:
                current_since = last_ts + 1
            else:
                break
        
        print(f"Total trades in last 10h: {len(trades)}")
        if trades:
            print("Last 10 trades:")
            for o in trades[-10:]:
                info = o.get("info", {})
                profit = float(info.get("profit") or 0)
                print(f"ID: {o['id']} | {info.get('side')} {info.get('positionSide')} | Profit: {profit}")
            
            total_long_profit = sum(float(t.get("info",{}).get("profit", 0)) for t in trades if t.get("info",{}).get("positionSide") == "LONG")
            total_short_profit = sum(float(t.get("info",{}).get("profit", 0)) for t in trades if t.get("info",{}).get("positionSide") == "SHORT")
            
            print(f"Total LONG Profit: {total_long_profit:.4f}")
            print(f"Total SHORT Profit: {total_short_profit:.4f}")
    finally:
        await ex.close()

asyncio.run(main())
