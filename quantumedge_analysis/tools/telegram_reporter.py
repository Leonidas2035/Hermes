import asyncio, json, os, time, urllib.request, urllib.parse
from datetime import datetime, timezone
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

import ccxt.async_support as ccxt

STATE_FILE = os.path.join(ROOT, "runtime", "telegram_state.json")
JOURNAL = os.path.join(ROOT, "runtime", "trade_journal.jsonl")

def send_tg_msg(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID") or os.getenv("TELEGRAM_ALLOWED_USERS")
    if not token or not chat_id:
        print(f"[TG_REPORTER] Error: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID. token={bool(token)}, chat_id={bool(chat_id)}")
        return
    if "," in chat_id:
        chat_id = chat_id.split(",")[0].strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=15) as resp:
            print("[TG_REPORTER] Message sent successfully to Telegram!")
    except Exception as e:
        print(f"[TG_REPORTER] Send error: {e}")

async def fetch_recent_filled_trades(ex, symbols, minutes=15):
    since_ts = (time.time() - (minutes * 60 + 30)) * 1000
    filled_trades = []
    seen_ids = set()
    for s in symbols:
        try:
            closed_orders = await ex.fetch_closed_orders(s, since=int(since_ts))
            for o in closed_orders:
                oid = str(o.get("id"))
                status = str(o.get("status", "")).lower()
                filled_qty = float(o.get("filled") or o.get("amount") or 0)
                if status in ("closed", "filled") and filled_qty > 0 and oid not in seen_ids:
                    seen_ids.add(oid)
                    sym_base = s.split(":")[0].replace("/USDT", "")
                    side_raw = str(o.get("side", "")).lower()
                    pos_side = str(o.get("info", {}).get("positionSide", "")).upper()
                    side_ukr = "Купівля" if side_raw == "buy" else "Продаж"
                    avg_price = float(o.get("average") or o.get("price") or 0)
                    info = o.get("info", {})
                    profit_raw = info.get("profit")
                    pnl = float(profit_raw) if profit_raw is not None and str(profit_raw).strip() not in ("", "0.0000") else None
                    
                    action_exp = "🟢 [Вхід в позицію / Сітка]"
                    if side_raw == "sell" and pos_side == "LONG":
                        action_exp = "🎯 [Фіксація прибутку TP]" if (pnl and pnl > 0) else "🔻 [Часткове скорочення]"
                    elif side_raw == "buy" and pos_side == "LONG":
                        action_exp = "🟢 [Вхід в позицію / DCA]"
                    elif side_raw == "sell" and pos_side == "SHORT":
                        action_exp = "🔴 [Вхід у Шорт-скальп]"
                    elif side_raw == "buy" and pos_side == "SHORT":
                        action_exp = "🎯 [Викуп Шорту TP]"

                    filled_trades.append({
                        "id": oid, "symbol": sym_base, "side_ukr": side_ukr,
                        "qty": filled_qty, "price": avg_price, "pnl": pnl,
                        "action_exp": action_exp, "ts": o.get("datetime")
                    })
        except Exception:
            pass
    if os.path.exists(JOURNAL):
        try:
            with open(JOURNAL, "r") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        if d.get("act") in ("close", "open", "grid"):
                            oid = str(d.get("id"))
                            r_pnl = d.get("realized_pnl")
                            for ft in filled_trades:
                                if ft["id"] == oid:
                                    if r_pnl is not None: ft["pnl"] = float(r_pnl)
                                    if d.get("act") == "close":
                                        ft["action_exp"] = "🎯 [Фіксація TP]" if float(r_pnl or 0) >= 0 else "🔻 [Часткове скорочення]"
                                    elif d.get("act") in ("open", "grid"):
                                        ft["action_exp"] = "🟢 [Відкриття / Сіткове додавання]"
                    except Exception:
                        pass
        except Exception:
            pass
    return filled_trades

async def main():
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    use_testnet = str(os.getenv("USE_TESTNET", "1")).lower() in {"1", "true", "t"}
    ex = ccxt.bingx({"apiKey": ak, "secret": sc, "options": {"defaultType": "swap"}, "enableRateLimit": True})
    if use_testnet: ex.set_sandbox_mode(True)
    await ex.load_markets()

    bal = await ex.fetch_balance()
    q = bal.get("VST" if use_testnet else "USDT", {})
    total_bal = float(q.get("total") or 0)
    free_bal = float(q.get("free") or 0)
    used_bal = float(q.get("used") or 0)

    symbols = ["BTC/USDT:USDT", "XRP/USDT:USDT", "SOL/USDT:USDT", "ETH/USDT:USDT"]
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
            active_legs.append({"symbol": sym_base, "side": side, "size": contracts, "entry": entry, "mark": mark, "upnl": upnl, "lev": lev, "roi": roi})

    all_orders = []
    for s in symbols:
        try:
            oo = await ex.fetch_open_orders(s)
            for o in oo:
                oid = str(o.get("id"))
                sym_base = s.split(":")[0].replace("/USDT", "")
                all_orders.append({"id": oid, "symbol": sym_base, "side": o.get("side"), "price": float(o.get("price") or 0), "amount": float(o.get("amount") or 0)})
        except Exception:
            pass

    filled_trades = await fetch_recent_filled_trades(ex, symbols, minutes=15)
    await ex.close()

    now_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
    msg = f"📊 <b>HERMES TRADING SHARK — 15M REPORT</b>\n"
    msg += f"<i>🕒 {now_str} | Автономна квант-сесія</i>\n\n"
    msg += f"💰 <b>Баланс та Маржа:</b>\n"
    msg += f"• Total Equity: <b>{total_bal:,.2f} VST</b>\n"
    msg += f"• Free Margin:  <b>{free_bal:,.2f} VST</b> ({(free_bal/total_bal*100 if total_bal else 0):.1f}%)\n"
    msg += f"• Used Margin:  <b>{used_bal:,.2f} VST</b> ({(used_bal/total_bal*100 if total_bal else 0):.1f}%)\n\n"

    eth_pos = next((l for l in active_legs if l["symbol"] == "ETH"), None)
    eth_pnl = eth_pos["upnl"] if eth_pos else 0.0
    eth_pnl_pct = (eth_pnl / 1000.0) * 100.0
    msg += f"💎 <b>ETH 50x Capital Tracker (1,000 VST Cap):</b>\n"
    msg += f"• Депозит ETH: <b>1,000.00 VST</b> (50x)\n"
    msg += f"• Накопичений PnL: <b>{eth_pnl:+.2f} VST</b> (<b>{eth_pnl_pct:+.2f}%</b>)\n\n"

    msg += f"📈 <b>Відкриті Позиції ({len(active_legs)}):</b>\n"
    for leg in active_legs:
        pnl_str = f"<b>+${leg['upnl']:,.2f} VST</b>" if leg['upnl'] >= 0 else f"<code>-${abs(leg['upnl']):,.2f} VST</code>"
        roi_str = f"({leg['roi']:+.1f}% ROI)"
        msg += f"• <b>{leg['symbol']} {leg['side']} ({leg['lev']:.0f}x)</b>: {leg['size']:,.2f} @ ${leg['entry']:,.4f}\n  Марк: ${leg['mark']:,.4f} | uPnL: {pnl_str} {roi_str}\n"

    msg += f"\n🎯 <b>Активні Ордери в стакані ({len(all_orders)}):</b>\n"
    sym_counts = {}
    for o in all_orders:
        sym = o['symbol']
        sym_counts[sym] = sym_counts.get(sym, 0) + 1
    for sym, cnt in sym_counts.items():
        msg += f"• <b>{sym}</b>: {cnt} ордер(ів)\n"

    if filled_trades:
        msg += f"\n⚡ <b>Спрацьовані ордери за 15хв ({len(filled_trades)}):</b>\n"
        xrp_trades = [ft for ft in filled_trades if ft['symbol'] == 'XRP']
        other_trades = [ft for ft in filled_trades if ft['symbol'] != 'XRP']
        
        if xrp_trades:
            total_xrp_pnl = sum((ft['pnl'] or 0) for ft in xrp_trades)
            margin_est = 32.5 # Approximate margin for 1500 XRP at 50x
            roi_est = (total_xrp_pnl / margin_est * 100) if margin_est > 0 else 0
            pnl_sign = "+" if total_xrp_pnl >= 0 else ""
            msg += f"• <b>XRP</b> — {len(xrp_trades)} ордерів | <b>{pnl_sign}${total_xrp_pnl:,.2f} VST</b> (ROI ~{pnl_sign}{roi_est:.1f}%)\n"
            
        for ft in other_trades:
            pnl_text = f" | профіт: <b>+${ft['pnl']:,.2f} VST</b>" if (ft["pnl"] and ft["pnl"] > 0) else (f" | профіт: <code>-${abs(ft['pnl']):,.2f} VST</code>" if ft["pnl"] else "")
            exp_text = f" — <i>{ft['action_exp']}</i>" if ft.get("action_exp") else ""
            msg += f"• <b>{ft['side_ukr']}</b> {ft['qty']:,.2f} <b>{ft['symbol']}</b> за ${ft['price']:,.4f}{pnl_text}{exp_text}\n"
    else:
        msg += f"\nℹ️ <i>Спрацьованих ордерів за останні 15хв немає.</i>\n"

    send_tg_msg(msg)

if __name__ == "__main__":
    asyncio.run(main())
