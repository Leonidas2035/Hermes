import asyncio
from qe_trade import make_ex
import time

async def main():
    ex = make_ex()
    since = int((time.time() - 24*3600) * 1000)
    try:
        trades = await ex.fetch_my_trades("XRP/USDT:USDT", since=since)
        pnl = sum(float(t['info'].get('realizedPnl', 0)) for t in trades)
        
        # Alternatively, check closed orders for PnL
        orders = await ex.fetch_closed_orders("XRP/USDT:USDT", since=since)
        order_pnl = sum(float(o['info'].get('realizedPnl', o['info'].get('profit', 0))) for o in orders)
        
        print(f"Trades count: {len(trades)}")
        print(f"Trades PnL: {pnl}")
        print(f"Closed Orders count: {len(orders)}")
        print(f"Closed Orders PnL: {order_pnl}")
        
    except Exception as e:
        print(e)
    finally:
        await ex.close()

if __name__ == "__main__":
    asyncio.run(main())
