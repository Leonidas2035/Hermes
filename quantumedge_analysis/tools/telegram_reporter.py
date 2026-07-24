import asyncio
import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
import ccxt.async_support as ccxt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(ROOT, "runtime", "telegram_state.json")
JOURNAL = os.path.join(ROOT, "runtime", "trade_journal.jsonl")


def send_tg_msg(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID") or os.getenv("TELEGRAM_ALLOWED_USERS")
    if not token or not chat_id:
        print("[TG_REPORTER] Missing credentials")
        return
    if "," in chat_id:
        chat_id = chat_id.split(",")[0].strip()
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print("[TG_REPORTER] Report sent successfully.")
    except Exception as e:
        print(f"[TG_REPORTER] Error sending Telegram report: {e}")


def load_prev_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"orders": {}, "timestamp": 0}


def save_current_state(orders_dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"orders": orders_dict, "timestamp": time.time()}, f, indent=2)


async def fetch_recent_filled_trades(ex, symbols, minutes=15):
    since_ts = (time.time() - (minutes * 60 + 30)) * 1000  # 15.5 mins ago in ms
    filled_trades = []
    seen_ids = set()
    
    for s in symbols:
        try:
            closed_orders = await ex.fetch_closed_orders(s, since=int(since_ts))
            for o in closed_orders:
                oid = str(o.get("id"))
                status = str(o.get("status", "")).lower()
                filled_qty = float(o.get("filled") or o.get("amount") or 0)
                
                # Only include executed/filled trades (ignore cancelled without fill)
                if status in ("closed", "filled") and filled_qty > 0 and oid not in seen_ids:
                    seen_ids.add(oid)
                    sym_base = s.split(":")[0].replace("/USDT", "")
                    side_raw = str(o.get("side", "")).lower()
                    side_ukr = "Купівля" if side_raw == "buy" else "Продаж"
                    avg_price = float(o.get("average") or o.get("price") or 0)
                    info = o.get("info", {})
                    profit_raw = info.get("profit")
                    pnl = float(profit_raw) if profit_raw is not None and str(profit_raw).strip() != "" and str(profit_raw) != "0.0000" else None
                    
                    filled_trades.append({
                        "id": oid,
                        "symbol": sym_base,
                        "side_ukr": side_ukr,
                        "qty": filled_qty,
                        "price": avg_price,
                        "pnl": pnl,
                        "ts": o.get("datetime")
                    })
        except Exception as e:
            print(f"[TG_REPORTER] Error fetching closed orders for {s}: {e}")

    # Cross-reference with trade_journal.jsonl for exact realized PnL
    since_str = datetime.fromtimestamp(time.time() - (minutes * 60 + 30), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if os.path.exists(JOURNAL):
        try:
            with open(JOURNAL, "r") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        if d.get("ts", "") >= since_str and d.get("act") == "close":
                            oid = str(d.get("id"))
                            r_pnl = d.get("realized_pnl")
                            for ft in filled_trades:
                                if ft["id"] == oid and r_pnl is not None:
                                    ft["pnl"] = float(r_pnl)
                    except Exception:
                        pass
        except Exception:
            pass
            
    return filled_trades


async def main():
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    use_testnet = str(os.getenv("USE_TESTNET", "1")).lower() in {"1", "true", "t"}

    ex = ccxt.bingx({
        "apiKey": ak,
        "secret": sc,
        "options": {"defaultType": "swap"},
        "enableRateLimit": True
    })
    if use_testnet:
        ex.set_sandbox_mode(True)
    
    await ex.load_markets()

    # 1. Balance
    bal = await ex.fetch_balance()
    q = bal.get("VST" if use_testnet else "USDT", {})
    total_bal = q.get("total", 0)
    free_bal = q.get("free", 0)
    used_bal = q.get("used", 0)

    # 2. Positions
    symbols = ["BTC/USDT:USDT", "XRP/USDT:USDT", "SOL/USDT:USDT"]
    positions = await ex.fetch_positions(symbols)
    active_legs = []
    for p in positions:
        contracts = float(p.get("contracts") or 0)
        if contracts > 0:
            sym_base = (p.get("symbol") or "").split(":")[0].replace("/USDT", "").strip()
            side = str(p.get("side") or "").upper()
            entry = float(p.get("entryPrice") or 0)
            mark = float(p.get("markPrice") or 0)
            upnl = float(p.get("unrealizedPnl") or 0)
            lev = float(p.get("leverage") or 1)
            margin = (entry * contracts) / lev if lev > 0 else 0
            roi = (upnl / margin * 100) if margin > 0 else 0

            active_legs.append({
                "symbol": sym_base,
                "side": side,
                "size": contracts,
                "entry": entry,
                "mark": mark,
                "upnl": upnl,
                "lev": lev,
                "roi": roi
            })

    # 3. Open Orders
    all_orders = []
    curr_orders_dict = {}
    for s in symbols:
        try:
            oo = await ex.fetch_open_orders(s)
            for o in oo:
                oid = str(o.get("id"))
                sym_base = s.split(":")[0].replace("/USDT", "")
                side = o.get("side")
                price = float(o.get("price") or 0)
                amt = float(o.get("amount") or 0)
                pos_side = o.get("info", {}).get("positionSide", "")

                curr_orders_dict[oid] = {
                    "symbol": sym_base,
                    "side": side,
                    "pos_side": pos_side,
                    "price": price,
                    "amount": amt
                }
                all_orders.append({
                    "id": oid,
                    "symbol": sym_base,
                    "side": side,
                    "pos_side": pos_side,
                    "price": price,
                    "amount": amt
                })
        except Exception as e:
            print(f"[TG_REPORTER] Error fetching orders for {s}: {e}")

    # 4. Fetch executed/filled trades in last 15 mins
    filled_trades = await fetch_recent_filled_trades(ex, symbols, minutes=15)

    await ex.close()

    # 5. Format HTML message
    now_str = datetime.now(timezone.utc).strftime("%H:%M UTC")

    msg = f"📊 <b>HERMES TRADING SHARK — 15M REPORT</b>\n"
    msg += f"<i>🕒 {now_str} | Автономна сесія</i>\n\n"
    msg += f"💰 <b>Баланс та Маржа:</b>\n"
    msg += f"• Total: <b>{total_bal:,.2f} VST</b>\n"
    msg += f"• Free: <b>{free_bal:,.2f} VST</b> ({(free_bal/total_bal*100 if total_bal else 0):.1f}%)\n"
    msg += f"• Used: <b>{used_bal:,.2f} VST</b> ({(used_bal/total_bal*100 if total_bal else 0):.1f}%)\n\n"
    
    msg += f"📈 <b>Відкриті Позиції ({len(active_legs)}):</b>\n"
    for leg in active_legs:
        pnl_str = f"<b>+${leg['upnl']:,.2f} VST</b>" if leg['upnl'] >= 0 else f"<code>-${abs(leg['upnl']):,.2f} VST</code>"
        roi_str = f"({leg['roi']:+.1f}% ROI)"
        msg += f"• <b>{leg['symbol']} {leg['side']}</b>: {leg['size']:,.2f} @ ${leg['entry']:,.4f}\n  Марк: ${leg['mark']:,.4f} | uPnL: {pnl_str} {roi_str}\n"
    
    msg += f"\n🎯 <b>Активні Ордери в стакані ({len(all_orders)}):</b>\n"
    sym_counts = {}
    for o in all_orders:
        sym = o['symbol']
        sym_counts[sym] = sym_counts.get(sym, 0) + 1
    
    for sym, cnt in sym_counts.items():
        msg += f"• <b>{sym}</b>: {cnt} ордер(ів)\n"
    
    if filled_trades:
        msg += f"\n⚡ <b>Спрацьовані ордери за 15хв ({len(filled_trades)}):</b>\n"
        for ft in filled_trades:
            pnl_text = ""
            if ft["pnl"] is not None and ft["pnl"] != 0:
                if ft["pnl"] > 0:
                    pnl_text = f" | профіт: <b>+${ft['pnl']:,.2f} VST</b>"
                else:
                    pnl_text = f" | профіт: <code>-${abs(ft['pnl']):,.2f} VST</code>"
            
            msg += f"• <b>{ft['side_ukr']}</b> {ft['qty']:,.2f} <b>{ft['symbol']}</b> за ціною <b>${ft['price']:,.4f}</b>{pnl_text}\n"
    else:
        msg += f"\nℹ️ <i>Спрацьованих ордерів за останні 15хв немає.</i>\n"

    save_current_state(curr_orders_dict)
    send_tg_msg(msg)

if __name__ == "__main__":
    asyncio.run(main())
