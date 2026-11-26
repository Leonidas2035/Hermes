import asyncio
import os
import sys
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from qe_trade import make_ex

async def report():
    ex = make_ex()
    try:
        # last 16 hours
        since_ts = int((time.time() - 16 * 3600) * 1000)
        
        pairs = ["XRP/USDT:USDT", "SOL/USDT:USDT", "ETH/USDT:USDT", "BTC/USDT:USDT"]
        
        total_pnl = 0.0
        stats = {}
        
        for pair in pairs:
            # We'll fetch multiple pages if necessary by moving since_ts forward
            current_since = since_ts
            pair_pnl = 0.0
            pair_trades = 0
            
            while True:
                orders = await ex.fetch_closed_orders(pair, since=current_since, limit=100)
                if not orders:
                    break
                
                for o in orders:
                    # check if the order actually realized profit
                    profit = o.get("info", {}).get("profit")
                    if profit and float(profit) != 0:
                        pair_pnl += float(profit)
                        pair_trades += 1
                        
                # prepare for next page
                last_ts = orders[-1]['timestamp']
                if last_ts > current_since:
                    current_since = last_ts + 1
                else:
                    break
                # small sleep to avoid rate limit
                await asyncio.sleep(0.1)
                
            stats[pair] = {"pnl": pair_pnl, "trades": pair_trades}
            total_pnl += pair_pnl
            
        print("=== ТОРГОВИЙ ЗВІТ (за останні 16 годин) ===")
        for pair, data in stats.items():
            print(f"{pair}: Угод = {data['trades']}, Прибуток = {data['pnl']:.4f} VST")
        print(f"=============================================")
        print(f"ЗАГАЛЬНИЙ ПРИБУТОК: {total_pnl:.4f} VST")
        print(f"=============================================")
    except Exception as e:
        print("Error:", e)
    finally:
        await ex.close()

if __name__ == "__main__":
    asyncio.run(report())
