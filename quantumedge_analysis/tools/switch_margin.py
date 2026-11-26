import asyncio, os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from qe_trade import make_ex

async def main():
    ex = make_ex()
    try:
        # fetch position
        pos = await ex.fetch_positions(['XRP/USDT:USDT'])
        for p in pos:
            if float(p.get("contracts") or 0) > 0:
                print(f"Current XRP position margin mode: {p.get('marginMode')}")
                
        # Switch to cross margin
        try:
            print("Attempting to switch to cross margin...")
            await ex.set_margin_mode("cross", "XRP/USDT:USDT")
            print("Successfully switched to Cross Margin!")
        except Exception as e:
            print(f"Failed to switch to Cross: {e}")
            
    finally:
        await ex.close()

asyncio.run(main())
