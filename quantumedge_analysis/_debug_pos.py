import asyncio, os, json, sys
sys.path.insert(0, "/home/layman/.hermes/quantumedge_analysis")
from dotenv import load_dotenv
load_dotenv()
import ccxt.async_support as ccxt
async def main():
    ak=os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY","")
    sc=os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET","")
    ex=ccxt.bingx({"apiKey":ak,"secret":sc,"options":{"defaultType":"swap"},"enableRateLimit":True,"timeout":30000})
    ex.set_sandbox_mode(True)
    await ex.load_markets()
    allp=await ex.fetch_positions()
    print("NONZERO POSITIONS NOW:")
    for p in allp:
        if float(p.get("contracts") or 0)!=0:
            print(" ",p.get("symbol"),"side=",p.get("side"),"posSide=",p.get("info",{}).get("positionSide"),"contracts=",p.get("contracts"),"entry=",p.get("entryPrice"),"uPnL=",p.get("unrealizedPnl"))
    try:
        sp=await ex.fetch_positions(symbols=["SOL/USDT:USDT"])
        print("SOL filtered fetch nonzero:", [(p.get('side'),p.get('contracts')) for p in sp if float(p.get('contracts') or 0)!=0])
    except Exception as e:
        print("SOL filtered ERR",e)
    await ex.close()
asyncio.run(main())
