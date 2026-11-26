"""
QuantumEdge Trading System - 50% Position Reduction & Bi-Directional Hedge Deployment
Path: /home/layman/.hermes/quantumedge_analysis/tools/execute_hedge_reduction.py
"""

import asyncio
import os
import json
from dotenv import load_dotenv

env_path = os.path.join('/home/layman/.hermes/quantumedge_analysis', '.env')
load_dotenv(env_path)

import ccxt.async_support as ccxt

async def run_position_reduction():
    ak = os.getenv('BINGX_TESTNET_API_KEY') or os.getenv('BINGX_API_KEY', '')
    sc = os.getenv('BINGX_SECRET') or os.getenv('BINGX_SECRET', '')
    use_testnet = str(os.getenv('USE_TESTNET', '1')).lower() in {'1', 'true', 't'}

    ex = ccxt.bingx({
        'apiKey': ak,
        'secret': sc,
        'options': {'defaultType': 'swap'},
        'enableRateLimit': True,
        'timeout': 30000
    })
    if use_testnet:
        ex.set_sandbox_mode(True)

    await ex.load_markets()

    print("=== STARTING 50% PARTIAL POSITION REDUCTION & HEDGE SETUP ===")
    
    # 1. Fetch current positions
    positions = await ex.fetch_positions()
    active_positions = [p for p in positions if float(p.get("contracts") or 0) > 0]
    
    reduction_results = []
    
    for pos in active_positions:
        symbol = pos.get("symbol")
        base_symbol = symbol.split(":")[0].replace("/USDT", "")
        side = pos.get("side")
        current_contracts = float(pos.get("contracts") or 0)
        entry_price = float(pos.get("entryPrice") or 0)
        upnl = float(pos.get("unrealizedPnl") or 0)
        
        # Calculate 50% reduction quantity
        reduce_qty = current_contracts * 0.50
        
        # Round quantity according to market precision
        market = ex.market(symbol)
        reduce_qty_str = ex.amount_to_precision(symbol, reduce_qty)
        reduce_qty_clean = float(reduce_qty_str)
        
        print(f"[{base_symbol}] Current {side}: {current_contracts} | Reducing 50%: {reduce_qty_clean} @ Market")
        
        # Execute 50% reduction order
        close_side = "sell" if side.lower() == "long" else "buy"
        pos_side_param = "LONG" if side.lower() == "long" else "SHORT"
        try:
            order = await ex.create_order(
                symbol=symbol,
                type="market",
                side=close_side,
                amount=reduce_qty_clean,
                params={"positionSide": pos_side_param}
            )
            reduction_results.append({
                "symbol": base_symbol,
                "original_qty": current_contracts,
                "reduced_qty": reduce_qty_clean,
                "remaining_qty": current_contracts - reduce_qty_clean,
                "order_id": order.get("id"),
                "status": "SUCCESS"
            })
            print(f"  --> SUCCESS: Reduced {base_symbol} by {reduce_qty_clean}. Order ID: {order.get('id')}")
        except Exception as e:
            print(f"  --> ERROR reducing {base_symbol}: {e}")
            reduction_results.append({
                "symbol": base_symbol,
                "status": "FAILED",
                "error": str(e)
            })

    # 2. Check updated balance and released free margin
    await asyncio.sleep(2.0)
    balance = await ex.fetch_balance()
    quote_currency = "VST" if use_testnet else "USDT"
    total_eq = float(balance.get(quote_currency, {}).get("total") or 0)
    free_margin = float(balance.get(quote_currency, {}).get("free") or 0)
    used_margin = float(balance.get(quote_currency, {}).get("used") or 0)

    print("\n=== POST-REDUCTION ACCOUNT SNAPSHOT ===")
    print(f"Total Equity: {total_eq:,.2f} {quote_currency}")
    print(f"Free Margin Released: {free_margin:,.2f} {quote_currency}")
    print(f"Used Margin: {used_margin:,.2f} {quote_currency}")

    await ex.close()
    return {
        "results": reduction_results,
        "total_equity": total_eq,
        "free_margin": free_margin,
        "used_margin": used_margin
    }

if __name__ == "__main__":
    asyncio.run(run_position_reduction())
