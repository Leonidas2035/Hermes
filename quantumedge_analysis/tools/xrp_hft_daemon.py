import os
import time
import json
import asyncio
from datetime import datetime
import ccxt.async_support as ccxt
import json
from dotenv import load_dotenv

load_dotenv()

SYMBOL = "XRP/USDT:USDT"
BASE = "XRPUSDT"
STEP = 0.0006
QTY = 1500
LEVELS = 14
CENTER = 1.0877

USE_TESTNET = str(os.getenv("USE_TESTNET", "1")).lower() in {"1","true","t"}

def log_to_journal(entry):
    journal_path = os.path.join(os.path.dirname(__file__), "..", "trader_journal.jsonl")
    entry["timestamp_local"] = datetime.now().isoformat()
    try:
        with open(journal_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print("Journal error:", e)

async def get_ex():
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    ex = ccxt.bingx({"apiKey":ak, "secret":sc, "options":{"defaultType":"swap"}, "enableRateLimit":True})
    if USE_TESTNET:
        ex.set_sandbox_mode(True)
    await ex.load_markets()
    return ex

async def sync_grid():
    ex = await get_ex()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting XRP HFT Grid Daemon (Center: {CENTER}, Step: {STEP}, Qty: {QTY}, Levels: {LEVELS})")
    
    last_closed_check = int(time.time() * 1000) - 1000
    
    while True:
        try:
            # 0. Fetch closed orders for journal
            try:
                closed_orders = await ex.fetch_closed_orders(SYMBOL, since=last_closed_check)
                if closed_orders:
                    max_ts = last_closed_check
                    for o in closed_orders:
                        info = o.get("info", {})
                        profit = info.get("profit", 0)
                        log_to_journal({
                            "action": "CLOSED_ORDER",
                            "symbol": SYMBOL,
                            "side": str(o.get("side", "")).upper(),
                            "positionSide": str(info.get("positionSide", "")).upper(),
                            "price": o.get("price"),
                            "amount": o.get("amount"),
                            "profit": profit
                        })
                        ts = o.get("timestamp")
                        if ts and ts > max_ts:
                            max_ts = ts
                    last_closed_check = max_ts + 1
            except Exception as e:
                print("Error fetching closed orders for journal:", e)

            # 1. Fetch current price
            ob = await ex.fetch_order_book(SYMBOL, limit=5)
            if not ob['bids']:
                await asyncio.sleep(2)
                continue
            curr = (ob['bids'][0][0] + ob['asks'][0][0]) / 2.0
            
            # 2. Fetch Open Orders
            open_orders = await ex.fetch_open_orders(SYMBOL)
            
            # 3. Create sets of active prices
            active_long_entries = set()
            active_short_entries = set()
            active_long_tps = set()
            active_short_tps = set()
            
            for o in open_orders:
                info = o.get("info", {})
                price = float(o.get("price") or 0)
                pos_side = info.get("positionSide", "").upper()
                side = str(o.get("side", "")).upper()
                
                # 3a. Entry orders
                if pos_side == "LONG" and side == "BUY":
                    active_long_entries.add(round(price, 4))
                elif pos_side == "SHORT" and side == "SELL":
                    active_short_entries.add(round(price, 4))
                
                # 3b. Attached TPs inside limit orders
                tp_obj = info.get("takeProfit", {})
                if tp_obj and isinstance(tp_obj, dict):
                    tp_price = float(tp_obj.get("stopPrice", 0))
                    if tp_price > 0:
                        if pos_side == "LONG":
                            active_long_tps.add(round(tp_price, 4))
                        else:
                            active_short_tps.add(round(tp_price, 4))
                            
            # 3c. Standalone Trigger TP orders (if limit order filled)
            for o in open_orders:
                info = o.get("info", {})
                stop_price = float(info.get("stopPrice") or 0)
                if stop_price == 0:
                    stop_price = float(o.get("price") or 0)
                
                pos_side = info.get("positionSide", "").upper()
                side = str(o.get("side", "")).upper()
                
                # Trigger TP orders for LONG are SELL orders
                if pos_side == "LONG" and side == "SELL":
                    active_long_tps.add(round(stop_price, 4))
                # Trigger TP orders for SHORT are BUY orders
                elif pos_side == "SHORT" and side == "BUY":
                    active_short_tps.add(round(stop_price, 4))
            
            placed_count = 0
            
            # 4. Generate ideal grid & replenish
            for i in range(1, LEVELS + 1):
                # --- LONG GRID ---
                target_long = round(CENTER - i * STEP, 4)
                tp_long = round(target_long + STEP, 4)
                
                # If neither the entry nor the TP exists, the slot is empty
                if target_long not in active_long_entries and tp_long not in active_long_tps:
                    if target_long < curr:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Replenishing LONG: {target_long} -> TP {tp_long}")
                        params = {"positionSide": "LONG", "hedged": True, "takeProfit": {"triggerPrice": tp_long, "price": tp_long, "type": "TAKE_PROFIT"}}
                        try:
                            await ex.create_order(symbol=SYMBOL, type="limit", side="buy", amount=QTY, price=target_long, params=params)
                            placed_count += 1
                            log_to_journal({
                                "action": "OPEN_ORDER",
                                "symbol": SYMBOL,
                                "side": "BUY",
                                "positionSide": "LONG",
                                "price": target_long,
                                "amount": QTY
                            })
                        except Exception as e:
                            print(f"Error placing LONG at {target_long}: {e}")
                        await asyncio.sleep(0.3)

                # --- SHORT GRID ---
                target_short = round(CENTER + i * STEP, 4)
                tp_short = round(target_short - STEP, 4)
                
                if target_short not in active_short_entries and tp_short not in active_short_tps:
                    if target_short > curr:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Replenishing SHORT: {target_short} -> TP {tp_short}")
                        params = {"positionSide": "SHORT", "hedged": True, "takeProfit": {"triggerPrice": tp_short, "price": tp_short, "type": "TAKE_PROFIT"}}
                        try:
                            await ex.create_order(symbol=SYMBOL, type="limit", side="sell", amount=QTY, price=target_short, params=params)
                            placed_count += 1
                            log_to_journal({
                                "action": "OPEN_ORDER",
                                "symbol": SYMBOL,
                                "side": "SELL",
                                "positionSide": "SHORT",
                                "price": target_short,
                                "amount": QTY
                            })
                        except Exception as e:
                            print(f"Error placing SHORT at {target_short}: {e}")
                        await asyncio.sleep(0.3)
                        
            if placed_count > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Replenished {placed_count} grid slots.")
                
            # Sleep 15 seconds before next cycle (HFT pacing)
            await asyncio.sleep(15)
            
        except Exception as e:
            print(f"Error in grid loop: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(15)

if __name__ == "__main__":
    asyncio.run(sync_grid())
