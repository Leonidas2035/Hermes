import asyncio
from qe_trade import make_ex
import json

async def main():
    ex = make_ex()
    try:
        # Fetch open trigger orders if possible, or just open orders with params
        orders = await ex.fetch_open_orders("XRP/USDT:USDT")
        trigger_orders = [o for o in orders if o['type'] in ['stop', 'stopMarket', 'takeProfit', 'takeProfitMarket', 'trigger'] or o['info'].get('type') in ['STOP_MARKET', 'TAKE_PROFIT_MARKET', 'TRIGGER']]
        print(f"Total open orders: {len(orders)}")
        print(f"Trigger orders: {len(trigger_orders)}")
        for o in trigger_orders[:5]:
            print(f"ID: {o['id']}, Side: {o['side']}, Qty: {o['amount']}, Price: {o.get('price')}, Stop: {o['info'].get('stopPrice')}, Type: {o['info'].get('type')}")
    except Exception as e:
        print(e)
    finally:
        await ex.close()

if __name__ == "__main__":
    asyncio.run(main())
