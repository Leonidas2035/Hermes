"""
QuantumEdge Trading Toolkit — CLI helpers with HARDWARE RISK GUARDRAILS.

Subcommands:
  snapshot
  book <depth>
  place <side> <posSide> <qty> <price> [symbol] [tp] [sl]
  market <side> <posSide> <qty> [symbol]
  cancel <id>
  cancel_all
  set_leverage <symbol> <leverage> [posSide]
  modify_sl <posSide> <new_sl> [symbol]
  recovery_target <symbol>
  grid <lo> <hi> <n_side> <qty>
  trades <hours>
"""
import asyncio, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
import ccxt.async_support as ccxt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ASSET_STRATEGIES, GLOBAL_LIMITS
from recovery_ledger import record_partial_loss, get_recovery_target, get_accumulated_loss

SYMBOL = os.getenv("MARKET_DATA_SYMBOLS", "XRPUSDT").split(",")[0]
USE_TESTNET = str(os.getenv("USE_TESTNET", "1")).lower() in {"1","true","t"}
BASE = SYMBOL.replace("USDT","")
CCXT_SYMBOL = f"{BASE}/USDT:USDT"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOURNAL = os.path.join(ROOT, "runtime", "trade_journal.jsonl")


def jlog(entry):
    entry["ts"] = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    with open(JOURNAL, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def trading_session():
    h = datetime.now(timezone.utc).hour
    if 13 <= h < 21:
        return "US"
    if 7 <= h < 13:
        return "EU"
    if 0 <= h < 7 or h >= 22:
        return "ASIA"
    return "EU_US_OVERLAP"


def make_ex():
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY","")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET","")
    ex = ccxt.bingx({"apiKey":ak,"secret":sc,"options":{"defaultType":"swap"},
                     "enableRateLimit":True,"timeout":30000})
    if USE_TESTNET:
        ex.set_sandbox_mode(True)
    return ex


def walls(levels, n=5):
    s = sorted(levels, key=lambda x: x[1], reverse=True)[:n]
    return [[round(p,4), round(v,1)] for p, v in s]


def _resolve_symbol(sym: str | None) -> str:
    if not sym or str(sym).lower() in ("none", "null", ""):
        return CCXT_SYMBOL
    base = str(sym).upper().replace("/USDT:USDT", "").replace("/USDT", "").replace("USDT", "").replace(":", "").strip()
    return f"{base}/USDT:USDT"


def _get_asset_base(sym: str) -> str:
    return str(sym).upper().replace("/USDT:USDT", "").replace("/USDT", "").replace("USDT", "").replace(":", "").strip()


async def snapshot(ex):
    await ex.load_markets()
    out = {"symbol": SYMBOL, "session": trading_session(),
           "utc": datetime.now(timezone.utc).strftime("%H:%M UTC")}
    try:
        fr = await ex.fetch_funding_rate(CCXT_SYMBOL)
        out["mark_price"] = float(fr.get("markPrice") or 0)
        out["funding_rate"] = fr.get("fundingRate")
    except Exception as e:
        out["funding_error"] = str(e)
    try:
        ob = await ex.fetch_order_book(CCXT_SYMBOL, limit=20)
        bids, asks = ob.get("bids",[]), ob.get("asks",[])
        bv = sum(b[1] for b in bids[:10]); av = sum(a[1] for a in asks[:10])
        out["book"] = {
            "best_bid": bids[0][0] if bids else None,
            "best_ask": asks[0][0] if asks else None,
            "bid_vol10": round(bv,1), "ask_vol10": round(av,1),
            "imbalance": round((bv-av)/(bv+av),3) if (bv+av) else 0,
            "bid_walls": walls(bids), "ask_walls": walls(asks),
        }
        if not out.get("mark_price") and bids and asks:
            out["mark_price"] = (bids[0][0]+asks[0][0])/2
    except Exception as e:
        out["book_error"] = str(e)
    try:
        bal = await ex.fetch_balance()
        q = bal.get("VST" if USE_TESTNET else "USDT", {})
        out["balance"] = {"total": q.get("total"), "free": q.get("free"), "used": q.get("used")}
    except Exception as e:
        out["balance_error"] = str(e)
    try:
        ps = await ex.fetch_positions()
        out["legs"] = [{
            "symbol": (p.get("symbol") or "").split(":")[0].replace("/USDT", ""),
            "side": p.get("side"),
            "size": float(p.get("contracts") or 0),
            "entry": float(p.get("entryPrice") or 0),
            "uPnL": float(p.get("unrealizedPnl") or 0),
            "lev": p.get("leverage")
        } for p in ps if float(p.get("contracts") or 0) != 0]
    except Exception as e:
        out["positions_error"] = str(e)
    try:
        oo = await ex.fetch_open_orders(CCXT_SYMBOL)
        out["open_orders_count"] = len(oo)
        out["open_orders"] = [{"id":o.get("id"),"side":o.get("side"),"type":o.get("type"),
                               "amt":o.get("amount"),"price":o.get("price"),"status":o.get("status")} for o in oo[:40]]
    except Exception as e:
        out["orders_error"] = str(e)
    return out


async def _check_margin_lock(ex, target_symbol: str, side: str, pos_side: str):
    """Guardrail 1: Check if free margin < 10%. Block new directional positions unless counter-position."""
    is_opening = (side.lower() == "buy" and pos_side.upper() == "LONG") or (side.lower() == "sell" and pos_side.upper() == "SHORT")
    if not is_opening:
        return
    
    bal = await ex.fetch_balance()
    q = bal.get("VST" if USE_TESTNET else "USDT", {})
    total = float(q.get("total") or 0)
    free = float(q.get("free") or 0)
    
    if total > 0 and (free / total) < GLOBAL_LIMITS["MIN_FREE_MARGIN_PCT"]:
        ps = await ex.fetch_positions(symbols=[target_symbol])
        opposite_side = "SHORT" if pos_side.upper() == "LONG" else "LONG"
        has_counter = any(p.get("side", "").upper() == opposite_side and float(p.get("contracts") or 0) > 0 for p in ps)
        
        if not has_counter:
            raise ValueError(f"MARGIN_PROTECTION_TRIGGERED: Free margin ratio {round(free/total*100, 2)}% < required {GLOBAL_LIMITS['MIN_FREE_MARGIN_PCT']*100}%. Directional opening blocked.")


async def place(ex, side, pos_side, qty, price, tp=None, sl=None, symbol=None):
    target_symbol = _resolve_symbol(symbol)
    base_asset = _get_asset_base(target_symbol)
    
    await _check_margin_lock(ex, target_symbol, side, pos_side)
    
    is_closing = (side.lower() == "sell" and pos_side.upper() == "LONG") or (side.lower() == "buy" and pos_side.upper() == "SHORT")
    if is_closing:
        ps = await ex.fetch_positions(symbols=[target_symbol])
        pos = next((p for p in ps if p.get("side", "").upper() == pos_side.upper() and float(p.get("contracts") or 0) > 0), None)
        if pos:
            entry = float(pos.get("entryPrice") or 0)
            lev = float(pos.get("leverage") or 50)
            contracts = float(pos.get("contracts") or 0)
            if entry > 0 and contracts > 0:
                init_margin = (entry * contracts) / max(lev, 1.0)
                price_f = float(price)
                expected_pnl = ((price_f - entry) * contracts) if pos_side.upper() == "LONG" else ((entry - price_f) * contracts)
                expected_roi = expected_pnl / init_margin
                min_roi = ASSET_STRATEGIES.get(base_asset, {"min_roi": 0.015})["min_roi"]
                if expected_roi < min_roi and expected_pnl > 0:
                    raise ValueError(f"ROI_GATE_DENIED: Target limit price {price} yields ROI {round(expected_roi*100, 2)}% < required {min_roi*100}% for {base_asset}.")

    params = {"positionSide": pos_side.upper(), "hedged": True}
    if is_closing:
        params["reduceOnly"] = True

    if tp is not None and str(tp).lower() not in ("none", "null", ""):
        params["takeProfit"] = {"triggerPrice": float(tp)}
    if sl is not None and str(sl).lower() not in ("none", "null", ""):
        params["stopLoss"] = {"triggerPrice": float(sl)}
    o = await ex.create_order(symbol=target_symbol, type="limit", side=side.lower(),
                               amount=float(qty), price=float(price), params=params)
    jlog({"act":"place","symbol":target_symbol,"side":side,"pos":pos_side,"qty":qty,"price":price,"tp":tp,"sl":sl,"id":o.get("id")})
    return {"id":o.get("id"),"symbol":target_symbol,"side":o.get("side"),"amount":o.get("amount"),"price":o.get("price"),"status":o.get("status"),"intended_tp":tp,"intended_sl":sl}


async def market(ex, side, pos_side, qty, symbol=None):
    target_symbol = _resolve_symbol(symbol)
    base_asset = _get_asset_base(target_symbol)
    
    is_closing = (side.lower() == "sell" and pos_side.upper() == "LONG") or (side.lower() == "buy" and pos_side.upper() == "SHORT")
    
    if not is_closing:
        await _check_margin_lock(ex, target_symbol, side, pos_side)
    else:
        ps = await ex.fetch_positions(symbols=[target_symbol])
        pos = next((p for p in ps if p.get("side", "").upper() == pos_side.upper() and float(p.get("contracts") or 0) > 0), None)
        if pos:
            contracts = float(pos.get("contracts") or 0)
            uPnL = float(pos.get("unrealizedPnl") or 0)
            entry = float(pos.get("entryPrice") or 0)
            lev = float(pos.get("leverage") or 50)
            req_qty = float(qty)
            
            if uPnL < 0:
                if req_qty >= contracts * 0.999:
                    raise ValueError(f"FULL_LOSS_REALIZATION_DENIED: Closing 100% of loss-making position is prohibited. uPnL: {round(uPnL, 2)} USDT.")
                max_allowed = contracts * GLOBAL_LIMITS["MAX_PARTIAL_LOSS_REDUCTION_PCT"]
                if req_qty > max_allowed * 1.001:
                    raise ValueError(f"PARTIAL_LOSS_REDUCTION_EXCEEDED: Requested {req_qty} exceeds max allowed 50% ({round(max_allowed, 4)}).")
            elif uPnL > 0:
                init_margin = (entry * contracts) / max(lev, 1.0)
                roi = uPnL / init_margin
                min_roi = ASSET_STRATEGIES.get(base_asset, {"min_roi": 0.015})["min_roi"]
                if roi < min_roi:
                    raise ValueError(f"ROI_GATE_DENIED: Current ROI {round(roi*100, 2)}% < required {min_roi*100}% for {base_asset}.")

    entry = None; mark = None
    try:
        await ex.load_markets()
        ps = await ex.fetch_positions(symbols=[target_symbol])
        for p in ps:
            if str(p.get("side","")).upper() == pos_side.upper() and float(p.get("contracts") or 0)!=0:
                entry = float(p.get("entryPrice") or 0)
        ob = await ex.fetch_order_book(target_symbol, limit=5)
        bids, asks = ob.get("bids",[]), ob.get("asks",[])
        mark = (bids[0][0]+asks[0][0])/2 if bids and asks else None
    except Exception:
        pass

    params = {"positionSide": pos_side.upper()}
    if is_closing:
        params["reduceOnly"] = True

    o = await ex.create_order(symbol=target_symbol, type="market", side=side,
                               amount=float(qty), params=params)
    
    realized = None
    if entry and mark:
        if pos_side.upper()=="LONG":
            realized = round((mark-entry)*float(qty), 4)
        else:
            realized = round((entry-mark)*float(qty), 4)
            
    if is_closing and realized is not None and realized < 0:
        record_partial_loss(base_asset, abs(realized))

    rec = {"act":"close" if is_closing else "open","symbol":target_symbol,"side":side,"pos":pos_side,"qty":float(qty),
           "entry":entry,"exit":mark,"realized_pnl":realized,"id":o.get("id")}
    jlog(rec)
    return {"id":o.get("id"),"symbol":target_symbol,"side":o.get("side"),"amount":o.get("amount"),
            "status":o.get("status"),"entry":entry,"exit":mark,"realized_pnl":realized}


async def set_sl(ex, pos_side, new_sl, symbol=None):
    target_symbol = _resolve_symbol(symbol)
    try:
        await ex.load_markets()
        ps = await ex.fetch_positions(symbols=[target_symbol])
        pos = next((p for p in ps if p.get("side", "").upper() == pos_side.upper() and float(p.get("contracts") or 0) > 0), None)
        if not pos:
            return {"modified": False, "error": f"no open position found for side {pos_side}"}
        qty = float(pos["contracts"])

        oo = await ex.fetch_open_orders(target_symbol)
        cancelled_count = 0
        for o in oo:
            info = o.get("info", {})
            is_sl = False
            if o.get("type") in ("stop", "trigger"):
                is_sl = True
            elif info.get("stopLossPrice") or info.get("triggerPrice"):
                is_sl = True
                
            pos_side_info = info.get("positionSide", "").upper()
            if is_sl and pos_side_info == pos_side.upper():
                try:
                    await ex.cancel_order(o["id"], target_symbol)
                    cancelled_count += 1
                    jlog({"act": "cancel_sl_order", "id": o["id"], "pos": pos_side})
                except Exception:
                    pass

        sl_side = "sell" if pos_side.upper() == "LONG" else "buy"
        params = {
            "positionSide": pos_side.upper(),
            "stopLossPrice": float(new_sl)
        }
        o = await ex.create_order(
            symbol=target_symbol,
            type="market",
            side=sl_side,
            amount=qty,
            price=None,
            params=params
        )
        jlog({"act": "modify_sl", "symbol": target_symbol, "pos": pos_side, "new_sl": new_sl, "qty": qty, "cancelled_old": cancelled_count, "ok": True})
        return {
            "modified": True,
            "new_sl": new_sl,
            "qty": qty,
            "cancelled_old": cancelled_count,
            "id": o.get("id"),
            "status": o.get("status")
        }
    except Exception as e:
        jlog({"act": "modify_sl", "pos": pos_side, "new_sl": new_sl, "ok": False, "err": str(e)[:200]})
        return {"modified": False, "error": str(e)[:300]}


async def change_leverage(ex, symbol, leverage, pos_side="LONG"):
    target_symbol = _resolve_symbol(symbol)
    await ex.load_markets()
    r = await ex.set_leverage(int(leverage), target_symbol, params={"side": pos_side.upper()})
    jlog({"act": "set_leverage", "symbol": target_symbol, "leverage": leverage, "pos_side": pos_side})
    return {"symbol": target_symbol, "leverage": leverage, "pos_side": pos_side, "result": r}


async def cancel_all(ex):
    r = await ex.cancel_all_orders(symbol=CCXT_SYMBOL)
    jlog({"act":"cancel_all"})
    return {"cancelled": len(r) if isinstance(r,list) else "ok"}


async def cancel_one(ex, oid):
    r = await ex.cancel_order(oid, CCXT_SYMBOL)
    jlog({"act":"cancel","id":oid})
    return {"cancelled": oid}


async def fetch_recovery_target_cli(ex, symbol):
    target_symbol = _resolve_symbol(symbol)
    base_asset = _get_asset_base(target_symbol)
    ps = await ex.fetch_positions(symbols=[target_symbol])
    pos = next((p for p in ps if float(p.get("contracts") or 0) > 0), None)
    entry = float(pos.get("entryPrice") or 0) if pos else 0.0
    size = float(pos.get("contracts") or 0) if pos else 0.0
    side = pos.get("side", "LONG").upper() if pos else "LONG"
    lev = float(pos.get("leverage") or 50) if pos else 50.0
    return get_recovery_target(base_asset, entry, size, side=side, leverage=lev)


async def grid(ex, lo, hi, n_side, qty):
    await ex.load_markets()
    lo, hi, n_side, qty = float(lo), float(hi), int(n_side), float(qty)
    mid = (lo+hi)/2
    placed = []
    step_dn = (mid - lo) / n_side
    for i in range(1, n_side+1):
        p = round(mid - step_dn*i, 4)
        tp = round(p*1.002, 4)
        try:
            o = await place(ex, "buy", "LONG", qty, p, tp); placed.append(o)
        except Exception as e:
            placed.append({"err":str(e),"price":p})
    step_up = (hi - mid) / n_side
    for i in range(1, n_side+1):
        p = round(mid + step_up*i, 4)
        tp = round(p*0.998, 4)
        try:
            o = await place(ex, "sell", "SHORT", qty, p, tp); placed.append(o)
        except Exception as e:
            placed.append({"err":str(e),"price":p})
    for k in (1,2):
        pu = round(hi + step_up*k, 4); pdn = round(lo - step_dn*k, 4)
        try: placed.append(await place(ex, "buy", "LONG", qty, pu, round(pu*1.002,4)))
        except Exception as e: placed.append({"err":str(e),"price":pu})
        try: placed.append(await place(ex, "sell", "SHORT", qty, pdn, round(pdn*0.998,4)))
        except Exception as e: placed.append({"err":str(e),"price":pdn})
    jlog({"act":"grid","lo":lo,"hi":hi,"n_side":n_side,"qty":qty,"count":len(placed)})
    return {"placed": len(placed), "orders": placed}


async def trades(ex, hours):
    since = time.time() - float(hours)*3600
    closed=0; wins=0; realized=0.0; detail=[]
    try:
        for line in open(JOURNAL):
            try: d=json.loads(line)
            except: continue
            if d.get("act")!="close": continue
            ts=d.get("ts","")
            try:
                import datetime as _dt
                t=_dt.datetime.strptime(ts,"%Y-%m-%d %H:%M:%S").timestamp()
            except: t=since
            if t<since: continue
            r=d.get("realized_pnl")
            if r is None: continue
            closed+=1; realized+=r
            if r>0: wins+=1
            detail.append({"ts":ts,"pos":d.get("pos"),"qty":d.get("qty"),"entry":d.get("entry"),"exit":d.get("exit"),"pnl":round(r,4)})
    except FileNotFoundError:
        pass
    return {"closed_with_pnl":closed,"winning":wins,"realized_pnl":round(realized,4),"detail":detail[-20:]}


async def run():
    cmd = sys.argv[1] if len(sys.argv)>1 else "snapshot"
    ex = make_ex()
    try:
        if cmd == "snapshot":
            print(json.dumps(await snapshot(ex), default=str))
        elif cmd == "place":
            side,pos,qty,price = sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5]
            symbol = sys.argv[6] if len(sys.argv)>6 else None
            tp = sys.argv[7] if len(sys.argv)>7 else None
            sl = sys.argv[8] if len(sys.argv)>8 else None
            print(json.dumps(await place(ex,side,pos,qty,price,tp,sl,symbol=symbol)))
        elif cmd == "set_leverage":
            symbol = sys.argv[2]
            leverage = sys.argv[3]
            pos_side = sys.argv[4] if len(sys.argv)>4 else "LONG"
            print(json.dumps(await change_leverage(ex, symbol, leverage, pos_side), default=str))
        elif cmd == "modify_sl":
            pos_side = sys.argv[2]
            new_sl = sys.argv[3]
            symbol = sys.argv[4] if len(sys.argv)>4 else None
            print(json.dumps(await set_sl(ex, pos_side, new_sl, symbol=symbol)))
        elif cmd == "market":
            side,pos,qty = sys.argv[2],sys.argv[3],sys.argv[4]
            symbol = sys.argv[5] if len(sys.argv)>5 else None
            print(json.dumps(await market(ex,side,pos,qty,symbol=symbol)))
        elif cmd == "cancel_all":
            print(json.dumps(await cancel_all(ex)))
        elif cmd == "cancel":
            print(json.dumps(await cancel_one(ex,sys.argv[2])))
        elif cmd == "recovery_target":
            symbol = sys.argv[2] if len(sys.argv)>2 else "XRP"
            print(json.dumps(await fetch_recovery_target_cli(ex, symbol)))
        elif cmd == "grid":
            print(json.dumps(await grid(ex,sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5]), default=str))
        elif cmd == "trades":
            print(json.dumps(await trades(ex, sys.argv[2] if len(sys.argv)>2 else 9), default=str))
        else:
            print(json.dumps({"error":f"unknown cmd {cmd}"}))
    except Exception as e:
        print(json.dumps({"error":str(e)}))
    finally:
        try: await ex.close()
        except: pass

if __name__ == "__main__":
    asyncio.run(run())
