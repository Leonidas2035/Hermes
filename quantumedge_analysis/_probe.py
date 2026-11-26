import asyncio, os, sys
sys.path.insert(0, "/home/layman/.hermes/quantumedge_analysis")
from dotenv import load_dotenv
load_dotenv()
import ccxt.async_support as ccxt
async def main():
    ak=os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY","")
    sc=os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET","")
    ex=ccxt.bingx({"apiKey":ak,"secret":sc,"options":{"defaultType":"swap"},"timeout":30000})
    ex.set_sandbox_mode(True)
    await ex.load_markets()
    # 1) UNFILTERED
    allp=await ex.fetch_positions()
    shorts=[p for p in allp if p.get("info",{}).get("positionSide")=="SHORT" and float(p.get("contracts") or 0)!=0]
    longs=[p for p in allp if p.get("info",{}).get("positionSide")=="LONG" and float(p.get("contracts") or 0)!=0]
    print("UNFILTERED -> LONG nonzero:", len(longs), "SHORT nonzero:", len(shorts))
    for p in shorts: print("   SHORT",p.get("symbol"),p.get("contracts"),"entry",p.get("entryPrice"))
    # 2) FILTERED by symbols for a symbol that earlier had a short (BTC)
    try:
        fp=await ex.fetch_positions(symbols=["BTC/USDT:USDT"])
        print("BTC FILTERED nonzero:",[(p.get('info',{}).get('positionSide'),p.get('contracts')) for p in fp if float(p.get('contracts') or 0)!=0])
    except Exception as e:
        print("BTC filtered ERR",e)
    await ex.close()
asyncio.run(main())
