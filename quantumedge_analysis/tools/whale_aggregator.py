"""
QuantumEdge Trading System - Whale Orderbook Aggregator
Path: /home/layman/.hermes/quantumedge_analysis/tools/whale_aggregator.py
"""

import asyncio
import json
import os
import sys
from collections import defaultdict
import ccxt.async_support as ccxt

# Threshold Settings
WHALE_MIN_BTC = 20.0
PRICE_BUCKET_STEP = 10.0  # Bucket size $10


def _resolve_symbol(symbol: str) -> str:
    if not symbol or "USDT" not in symbol.upper():
        return "BTC/USDT:USDT"
    base = symbol.upper().replace("/USDT:USDT", "").replace("/USDT", "").replace("USDT", "").replace(":", "").strip()
    return f"{base}/USDT:USDT"


async def fetch_aggregated_book(symbol="BTC/USDT:USDT", limit=1000, min_vol=WHALE_MIN_BTC, step=PRICE_BUCKET_STEP):
    """Fetches deep orderbook and aggregates liquidity clusters >= min_vol."""
    ccxt_symbol = _resolve_symbol(symbol)
    base_asset = ccxt_symbol.split("/")[0]
    
    use_testnet = str(os.getenv("USE_TESTNET", "1")).lower() in {"1", "true", "t"}
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    
    exchange = ccxt.bingx({
        "apiKey": ak,
        "secret": sc,
        "options": {"defaultType": "swap"},
        "enableRateLimit": True,
        "timeout": 25000
    })
    if use_testnet:
        exchange.set_sandbox_mode(True)
        
    try:
        orderbook = await exchange.fetch_order_book(ccxt_symbol, limit=limit)
        
        whale_bids = []
        whale_asks = []
        
        # Aggregate Bids (Buy support)
        bid_clusters = defaultdict(float)
        for price, vol in orderbook.get("bids", []):
            bucket = round(price / step) * step
            bid_clusters[bucket] += vol
            
        for price, vol in sorted(bid_clusters.items(), reverse=True):
            if vol >= min_vol:
                whale_bids.append({"price": round(price, 1), "vol": round(vol, 2)})
                
        # Aggregate Asks (Sell resistance)
        ask_clusters = defaultdict(float)
        for price, vol in orderbook.get("asks", []):
            bucket = round(price / step) * step
            ask_clusters[bucket] += vol
            
        for price, vol in sorted(ask_clusters.items()):
            if vol >= min_vol:
                whale_asks.append({"price": round(price, 1), "vol": round(vol, 2)})

        result = {
            "symbol": ccxt_symbol,
            "base_asset": base_asset,
            "bucket_size_usd": step,
            "min_whale_vol": min_vol,
            "whale_bids": whale_bids[:5],  # Top 5 nearest support shields
            "whale_asks": whale_asks[:5]   # Top 5 nearest resistance shields
        }
        
        return result

    except Exception as e:
        return {"error": str(e)}
    finally:
        try:
            await exchange.close()
        except Exception:
            pass


async def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT:USDT"
    min_vol = float(sys.argv[2]) if len(sys.argv) > 2 else WHALE_MIN_BTC
    res = await fetch_aggregated_book(sym, limit=1000, min_vol=min_vol)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
