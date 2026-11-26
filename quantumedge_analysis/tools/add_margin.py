import asyncio, os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from qe_trade import make_ex

async def main():
    ex = make_ex()
    try:
        print("Adding 800 VST to XRP LONG isolated margin...")
        res = await ex.add_margin("XRP/USDT:USDT", 800, params={"positionSide": "LONG"})
        print("Success:", res)
    except Exception as e:
        print("Error adding margin:", e)
    finally:
        await ex.close()

asyncio.run(main())
