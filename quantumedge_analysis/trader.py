"""
================================================================
QuantumEdge — AUTONOMOUS TRADER (Hermes Market-Maker brain)
================================================================
Це мій мозок. Запускається з cron кожні 5 хв (торгівля) та 15 хв (глибокий план).
НЕ питає власника. Сам аналізує (market_analysis.py), сам приймає рішення,
сам ставить РЕАЛЬНІ ордери через qe_trade.py.

ПРАВИЛА ВЛАСНИКА (священні):
  1. НЕ закривати збиткові позиції.
  2. Збиткову скорочувати ЛИШЕ прибутком протилежної (харвест).
  3. Індикатори в лонг → додавати; рух видихся → фіксація + шорт.
  4. Високий ризик → хедж + чекати.
  5. Авто-стоп ВИМКНЕНО — захист через аналіз + цей контур.
  6. Шорт уперся в ліміт нотіоналу (ccxt 101209) — шорт ЛИШЕ скорочувати.

РЕЖИМ: демо (BingX VST). Реальні ордери на рахунку VST.
================================================================
"""
from __future__ import annotations
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

QE = Path("/home/layman/.hermes/quantumedge_analysis")
VENV = QE / "venv" / "bin" / "python3"
ANALYSIS_DIR = Path("/home/layman/.hermes/quantumedge_analysis")
JOURNAL = ANALYSIS_DIR / "trader_journal.jsonl"
STATE = ANALYSIS_DIR / "trader_state.json"

sys.path.insert(0, str(ANALYSIS_DIR))
from market_analysis import run as analyze, save as save_analysis


def jlog(entry: dict):
    entry["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def qe(args: list) -> dict:
    """Викликає qe_trade.py і повертає JSON-результат."""
    r = subprocess.run(
        [str(VENV), str(QE / "tools" / "qe_trade.py"), *args],
        capture_output=True, text=True, timeout=120, cwd=str(QE),
    )
    out = (r.stdout or "").strip()
    try:
        return json.loads(out)
    except Exception:
        return {"error": out[:500], "stderr": (r.stderr or "")[:300]}


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {"cycle": 0, "realized_pnl": 0.0, "trades": 0, "wins": 0,
                "last_bias": None, "grid_active": False, "last_grid_lo": None, "last_grid_hi": None}


def save_state(s: dict):
    STATE.write_text(json.dumps(s, indent=2, default=str))


# =====================================================================
# SKILLS-BASED SIGNAL (інтеграція liqmap + sigtest)
# Правило власника: 3 індикатори в один бік + ліквідність карти в тому ж
# напрямку -> сигнал. Вхід з ТП+СЛ, трейлінг до BE при безпечній відстані.
# =====================================================================
import numpy as np
import pandas as pd
import ccxt as _ccxt

def _load_market_state(symbol: str = "BTC/USDT:USDT", limit: int = 200) -> dict:
    """Живі OHLCV + поточна ціна з BingX (публічні)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    ex = _ccxt.bingx({"enableRateLimit": True})
    ohlcv = ex.fetch_ohlcv(symbol, "1h", limit=limit)
    ticker = ex.fetch_ticker(symbol)
    return {"ohlcv": ohlcv, "last": float(ticker["last"])}


def skills_signal(symbol: str = "BTC/USDT:USDT") -> dict:
    """Синтез сигналу за скілами. Повертає bias + близьку зону + впевненість."""
    try:
        sys.path.insert(0, str(QE / "tools"))
        from sigtest.indicators import enrich
        from liqmap.model import build_heatmap, _extract_zones

        st = _load_market_state(symbol)
        ohlcv = st["ohlcv"]
        last = st["last"]
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        df = enrich(df)
        r = df.iloc[-1]

        # --- 3+ індикатори в один бік ---
        long_votes = short_votes = 0
        if r.ema9 > r.ema21 > r.ema50: long_votes += 1
        elif r.ema9 < r.ema21 < r.ema50: short_votes += 1
        if r.macd_hist > 0: long_votes += 1
        else: short_votes += 1
        if r.rsi > 55: long_votes += 1
        elif r.rsi < 45: short_votes += 1
        if r.obv_slope > 0: long_votes += 1
        else: short_votes += 1
        ind_bias = "LONG" if long_votes >= 3 else ("SHORT" if short_votes >= 3 else "NEUTRAL")

        # --- карта ліквідацій: близька зона <=2% ---
        heat = build_heatmap(ohlcv, price_bins=140)
        prof = np.array(heat["grid"])[:, -1]
        cen = np.array(heat["price_levels"])
        zones = _extract_zones(prof, cen, last, top=8)
        near = [z for z in zones if abs(z["dist_pct"]) <= 2.0]
        long_z = [z for z in near if z["side"] == "LONG_LIQ"]
        short_z = [z for z in near if z["side"] == "SHORT_LIQ"]

        # сигнал: індикатори + ліквідність в тому ж боці
        target = None
        if ind_bias == "SHORT" and long_z:
            z = min(long_z, key=lambda x: abs(x["dist_pct"]))
            target = {"side": "SHORT", "entry_bias": "short", "tp": z["price"], "zone_dist": z["dist_pct"]}
        elif ind_bias == "LONG" and short_z:
            z = min(short_z, key=lambda x: abs(x["dist_pct"]))
            target = {"side": "LONG", "entry_bias": "long", "tp": z["price"], "zone_dist": z["dist_pct"]}

        return {
            "ind_bias": ind_bias, "long_votes": long_votes, "short_votes": short_votes,
            "near_zones": near, "target": target, "price": last,
            "exit_rules": {
                "long": {"rsi": 70, "macd_hist": 0},
                "short": {"rsi": 30, "macd_hist": 0}
            },
            "indicators": {
                "rsi": float(r.rsi) if hasattr(r, "rsi") and not pd.isna(r.rsi) else 50.0,
                "macd_hist": float(r.macd_hist) if hasattr(r, "macd_hist") and not pd.isna(r.macd_hist) else 0.0
            }
        }
    except Exception as e:
        return {
            "error": str(e)[:200],
            "ind_bias": "NEUTRAL",
            "exit_rules": {
                "long": {"rsi": 70, "macd_hist": 0},
                "short": {"rsi": 30, "macd_hist": 0}
            },
            "indicators": {
                "rsi": 50.0,
                "macd_hist": 0.0
            }
        }


# --- SMART STOP-LOSS CONFIGURATION ---
TRAIL_TRIGGER_PCT = 0.3
TRAIL_DIST_PCT = 0.5
BE_PROFIT_PCT = 0.05
SL_TIGHTEN_ON_REVERSAL = True

def get_raw_open_orders() -> list:
    import os
    from dotenv import load_dotenv
    load_dotenv(Path("/home/layman/QuantumEdge/.env"))
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    ex = _ccxt.bingx({
        "apiKey": ak,
        "secret": sc,
        "options": {"defaultType": "swap"},
        "enableRateLimit": True,
        "timeout": 30000
    })
    if str(os.getenv("USE_TESTNET", "1")).lower() in {"1", "true", "t"}:
        ex.set_sandbox_mode(True)
    try:
        symbol = os.getenv("MARKET_DATA_SYMBOLS", "XRPUSDT").split(",")[0]
        base = symbol.replace("USDT","")
        ccxt_symbol = f"{base}/USDT:USDT"
        orders = ex.fetch_open_orders(ccxt_symbol)
        return orders
    except Exception as e:
        print(f"[TRADER] Failed to fetch raw open orders: {e}")
        return []
    finally:
        try:
            ex.close()
        except Exception:
            pass

def smart_stop_loss(snap, price, indicators: dict = None, book: dict = None, manip: dict = None, conviction: float = 1.0):
    try:
        actions = []
        raw_orders = get_raw_open_orders()
        for leg in snap.get("legs", []):
            if leg["size"] <= 0:
                continue
            entry = leg["entry"]
            if not entry:
                continue
            u = leg["uPnL"]
            if u <= 0:
                continue
                
            pos_side = leg["side"]
            if pos_side == "long":
                base_sl = entry * (1.0 + BE_PROFIT_PCT / 100.0)
                move_pct = (price - entry) / entry * 100.0
            else:
                base_sl = entry * (1.0 - BE_PROFIT_PCT / 100.0)
                move_pct = (entry - price) / entry * 100.0
                
            reversal = False
            if SL_TIGHTEN_ON_REVERSAL and indicators:
                rsi = indicators.get("rsi")
                macd_hist = indicators.get("macd_hist")
                if pos_side == "long":
                    if rsi is not None and rsi > 70 and macd_hist is not None and macd_hist < 0:
                        reversal = True
                else:
                    if rsi is not None and rsi < 30 and macd_hist is not None and macd_hist > 0:
                        reversal = True
            
            manip_hold = False
            if manip and manip.get("severity") == "HIGH" and conviction < 0.6:
                manip_hold = True
                
            new_sl = base_sl
            if reversal:
                new_sl = base_sl
            elif manip_hold:
                new_sl = base_sl
            elif move_pct >= TRAIL_TRIGGER_PCT:
                if pos_side == "long":
                    trail_sl = price * (1.0 - TRAIL_DIST_PCT / 100.0)
                    new_sl = max(base_sl, trail_sl)
                else:
                    trail_sl = price * (1.0 + TRAIL_DIST_PCT / 100.0)
                    new_sl = min(base_sl, trail_sl)
                    
            existing_sls = []
            for o in raw_orders:
                info = o.get("info", {})
                is_sl = False
                if o.get("type") in ("stop", "trigger") or o.get("stopLossPrice") is not None or o.get("triggerPrice") is not None:
                    is_sl = True
                elif info.get("stopLossPrice") or info.get("triggerPrice") or info.get("stopPrice") or info.get("type") == "STOP_MARKET":
                    is_sl = True
                
                pos_side_info = info.get("positionSide", "").upper()
                if is_sl and pos_side_info == pos_side.upper():
                    trig = o.get("stopLossPrice") or info.get("stopPrice")
                    if trig is not None:
                        try:
                            trig = float(trig)
                        except ValueError:
                            pass
                    existing_sls.append((o.get("id"), trig))
                    
            new_sl_rounded = round(new_sl, 4)
            if len(existing_sls) == 1:
                curr_id, curr_trig = existing_sls[0]
                if curr_trig is not None and abs(curr_trig - new_sl_rounded) < 0.0001:
                    continue
                    
            qe(["modify_sl", pos_side, str(new_sl_rounded)])
        return {"ok": True}
    except Exception as e:
        return {"modified": False, "error": str(e)}




# =====================================================================
# РІШЕННЯ ТРЕЙДЕРА
# =====================================================================
def decide_and_act(report: dict, state: dict, deep: bool = False) -> dict:
    """
    Делегує прийняття рішень великій моделі Antigravity (2T+) через agy CLI.
    Отримує перелік торгових команд у форматі JSON, парсить їх та виконує.
    """
    import re
    import os
    
    verdict = report["verdict"]
    tech = report["technicals"]
    levels = report["levels"]
    manip = report["manipulation"]
    trend = report["trend_shift"]
    book = report["order_book"]
    price = levels["price"]
    bias = verdict["bias"]
    conviction = verdict["conviction"]

    actions = []
    
    # 1. Отримуємо поточний snapshot
    snap = qe(["snapshot"])
    if "error" in snap:
        print(f"[TRADER] Snapshot error: {snap['error']}")
        return {"error": snap["error"], "actions": []}
        
    open_orders_count = int(snap.get("open_orders_count") or 0)
    legs = snap.get("legs", [])
    open_orders = snap.get("open_orders", [])
    balance = snap.get("balance", {})
    free_balance = float(balance.get("free") or 0)
    
    # 2. Отримуємо макро-контекст по крос-парам (BTC/SOL, BTC/XRP)

    btc_ctx = report.get("btc") or {}
    btc_price = btc_ctx.get("btc_last") or 0.0
    sol_price = btc_ctx.get("sol_last") or 0.0
    xrp_price = btc_ctx.get("xrp_last") or snap.get("mark_price") or price
    btc_sol_ratio = btc_ctx.get("btc_sol_ratio") or 0.0
    btc_xrp_ratio = btc_ctx.get("btc_xrp_ratio") or 0.0
    
    # Розрахунок запасу маржі та Агресивний режим для Американської сесії (DEMO AGGRESSIVE MODE)
    total_balance = float(balance.get("total") or 1.0)
    free_pct = (free_balance / total_balance) * 100.0 if total_balance > 0 else 100.0
    margin_rule = "⚡ DEMO AGGRESSIVE MODE ACTIVE (US SESSION): The owner has TEMPORARILY REMOVED the 30% margin restriction! You are EXPLICITLY PERMITTED and EXPECTED to trade aggressively: place market/limit BUY (LONG) or counter SHORT orders, capture momentum breakouts (especially on SOL and BTC), scale into grids, and generate active realized PnL!"


    # Liqmap дані для Front-running TP
    liq_map = report.get("liq_map") or {}

    # 3. Будуємо промпт для Antigravity з HERMES TRADING DNA v2.0
    prompt = f"""You are the 2T+ Antigravity Trading Brain operating under HERMES TRADING DNA v2.0.
You must analyze the multi-asset market state (XRP, BTC, SOL) and output precise execution commands.

### ACTIVE TRADING PAIRS:
- XRPUSDT
- BTCUSDT
- SOLUSDT

### CROSS-PAIR RATIOS & PRICES:
- BTC/USDT: {btc_price} (24h: {btc_ctx.get('btc_change24')}%)
- SOL/USDT: {sol_price} (24h: {btc_ctx.get('sol_change24')}%)
- XRP/USDT: {xrp_price} (24h: {btc_ctx.get('xrp_change24')}%)
- BTC/SOL Ratio: {btc_sol_ratio}
- BTC/XRP Ratio: {btc_xrp_ratio}

### LIQUIDATION MAP MAGNETS (LIQMAP FRONT-RUNNING):
- Data: {json.dumps(liq_map, indent=2, default=str)}
- Target Rule: Place Take-Profit orders 0.1% BEFORE major short liquidation magnets or Ask Walls to ensure guaranteed fill before liquidity exhaustion.

### MARGIN STATUS & DECAY RULE:
- Total Balance: {total_balance:.2f} VST | Free Balance: {free_balance:.2f} VST ({free_pct:.1f}% free)
{margin_rule}

### HERMES TRADING DNA v2.0 RULES:
1. PARTIAL REDUCTION & RE-ACCUMULATION PROTOCOL (NEW): Never close a losing position completely. However, you ARE ALLOWED to partially reduce/trim a losing leg (e.g. 20%-40%) near key resistance/support or momentum exhaustion to mitigate drawdown, PROVIDED you immediately place a re-entry DCA grid at a better price (lower for LONG, higher for SHORT). The profit from the re-accumulated position MUST offset the initial reduction loss and bring the total leg into net positive PnL!
2. Auto-stop is OFF.

3. Order TTL (Time-to-Live): Cancel any limit order if price moved > 2.0% away from the order price.
4. Breakeven Lock: When Unrealized PnL reaches >= +1.0%, lock profit by target stop at entry * 1.001.
5. Counter-Trade Permission: Opening counter SHORT positions on rallies is ALLOWED near Ask Walls / Resistance / RSI > 70. Set active Take-Profit targets (+1.0% to +1.5%). Avoid dead 1-to-1 locks.
6. BingX Hedge Mode Bug Protection: All short/sell closing commands execute with reduceOnly=True automatically.

### SOLANA (SOL) SMART DCA STRATEGY (MOMENTUM BREAKOUT):
- Allocation Split (25% Market Entry / 75% Dynamic Limit DCA):
  1. Immediate Market Entry (25% size, e.g. 5.0 to 10.0 SOL): Execute `["market", "buy", "LONG", qty, "SOL"]` on strong momentum.
  2. Dynamic Limit DCA Grid (75% size, e.g. 15.0 to 35.0 SOL): Place `["place", "buy", "LONG", qty, price, "SOL"]` limit orders at 0.5 * ATR and 1.0 * ATR below price.

### HEDGED LOCK ("ЗАМОК") RESOLUTION PROTOCOL:
- Unlock open LONG and SHORT legs step-by-step near key Support/Resistance via profit harvesting (net PnL >= 0).

### CURRENT POSITIONS SNAPSHOT (ALL COINS):
{json.dumps(legs, indent=2, default=str)}

### OPEN ORDERS LIST:
{json.dumps(open_orders, indent=2, default=str)}

### MARKET INDICATORS & BIAS:
- Indicator Bias: {bias} (Conviction: {conviction * 100:.1f}%)
- Technical indicators: {json.dumps(tech, default=str)}
- Order Book walls & imbalance: {json.dumps(book, default=str)}

### TASK:
1. Write a very brief analysis of the market and cross-pair trends (in Ukrainian, max 3 lines).
2. Define exact ccxt/qe_trade execution commands.
3. Output the commands ONLY in a ```json code block at the very end of your response.

Valid commands format (JSON array of arrays):
```json
[
  ["place", "buy"|"sell", "LONG"|"SHORT", qty, price, "XRP"|"BTC"|"SOL"],
  ["market", "buy"|"sell", "LONG"|"SHORT", qty, "XRP"|"BTC"|"SOL"],
  ["cancel", "order_id"]
]
```
If no action is required, output: `[]`.
"""

    
    print("[TRADER] Invoking Antigravity for trading decision...")
    
    # 4. Визначаємо модель та викликаємо agy CLI
    agy_model = os.getenv("AGY_MODEL")
    agy_cmd = ["agy", "--dangerously-skip-permissions", "--print", prompt]
    if agy_model:
        agy_cmd = ["agy", "--model", agy_model, "--dangerously-skip-permissions", "--print", prompt]
        print(f"[TRADER] Using custom model: {agy_model}")
    else:
        print("[TRADER] Using default agy model")
        
    try:
        r = subprocess.run(
            agy_cmd,
            capture_output=True, text=True, timeout=120
        )
        if r.returncode != 0:
            print(f"[TRADER] agy CLI error: {r.stderr}")
            return {"error": f"agy CLI returned {r.returncode}", "actions": []}
            
        response = r.stdout or ""
        print("\n=== ANTIGRAVITY DECISION & PLAN ===")
        print(response)
        print("===================================\n")
        
        # 5. Парсимо JSON команди з відповіді
        cmd_block = []
        m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response, re.DOTALL)
        if m:
            try:
                cmd_block = json.loads(m.group(1))
            except Exception as e:
                print(f"[TRADER] JSON block parse error: {e}")
        else:
            m2 = re.search(r"(\[.*?\])", response, re.DOTALL)
            if m2:
                try:
                    cmd_block = json.loads(m2.group(1))
                except Exception:
                    pass
                    
        # 6. Виконуємо команди
        for cmd in cmd_block:
            if not isinstance(cmd, list) or not cmd:
                continue
            action_type = cmd[0]
            
            # Конвертуємо всі аргументи команди у строки для сумісності з subprocess.run
            cmd_args = []
            for arg in cmd[1:]:
                if arg is None:
                    cmd_args.append("none")
                else:
                    cmd_args.append(str(arg))
            
            # Видаляємо кінцеві "none" або "null" аргументи
            while cmd_args and cmd_args[-1].lower() in ("none", "null"):
                cmd_args.pop()
                
            print(f"[TRADER] Executing command: {[action_type] + cmd_args}")
            res = qe([action_type] + cmd_args)
            
            # Логування дії
            act_entry = {"act": f"AG_{action_type.upper()}", "cmd": [action_type] + cmd_args, "result": res}
            actions.append(act_entry)
            
            log_entry = {"act": f"AG_{action_type.upper()}", "args": cmd_args, "result": (res.get("error") or res.get("id") or "ok")}
            jlog(log_entry)
            
    except subprocess.TimeoutExpired:
        print("[TRADER] Antigravity invocation timed out.")
        return {"error": "Antigravity timeout", "actions": []}
    except Exception as e:
        print(f"[TRADER] Exception during Antigravity execution: {e}")
        return {"error": str(e), "actions": []}
        
    decision = "ACT" if actions else "HOLD"
    jlog({"act": "CYCLE", "decision": decision, "bias": bias,
          "conviction": conviction, "actions_count": len(actions)})
          
    return {
        "decision": decision,
        "bias": bias,
        "conviction": conviction,
        "price": price,
        "notes": verdict.get("notes", []),
        "actions": actions,
        "raw_response": response
    }


def send_telegram_report(msg: str):
    """Надсилає повідомлення безпосередньо у Telegram через Bot API."""
    import os
    import urllib.request
    import urllib.parse
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID") or os.getenv("TELEGRAM_ALLOWED_USERS")
    if not token or not chat_id:
        print("[TRADER] Telegram credentials missing, skipping report.")
        return
    if "," in chat_id:
        chat_id = chat_id.split(",")[0].strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=15) as response:
            response.read()
        print("[TRADER] Telegram report sent successfully.")
    except Exception as e:
        print(f"[TRADER] Failed to send Telegram report: {e}")


# =====================================================================
# MAIN
# =====================================================================
def main(deep: bool = False):
    mode = "DEEP(15m)" if deep else "TRADE(5m)"
    print(f"[TRADER] {mode} cycle start {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")

    # 1. Аналіз
    report = analyze()
    save_analysis(report)

    # 2. Рішення + дія
    state = load_state()
    state["cycle"] += 1
    state["last_bias"] = report["verdict"]["bias"]

    result = decide_and_act(report, state, deep=deep)
    save_state(state)

    # 3. Звіт у консоль
    print(f"[TRADER] bias={result.get('bias')} conv={result.get('conviction')} "
          f"decision={result.get('decision')} actions={len(result.get('actions', []))}")
    for a in result.get("actions", []):
        print(f"   - {a['act']}: {a.get('qty', a.get('price', ''))}")

    # 4. Підсумок PnL з журналу
    try:
        realized = 0.0
        wins = 0
        closed = 0
        for line in open(JOURNAL):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("act") == "close" and d.get("realized_pnl") is not None:
                closed += 1
                realized += float(d["realized_pnl"])
                if float(d["realized_pnl"]) > 0:
                    wins += 1
        state["realized_pnl"] = round(realized, 2)
        state["trades"] = closed
        state["wins"] = wins
        save_state(state)
    except Exception as e:
        print(f"[TRADER] pnl read warn: {e}")

    # 5. Надсилаємо КОРОТКИЙ звіт у Telegram
    try:
        snap = qe(["snapshot"])
        legs = snap.get("legs", [])

        btc_ctx = report.get("btc") or {}
        btc_price = btc_ctx.get("btc_last") or 0.0
        sol_price = btc_ctx.get("sol_last") or 0.0
        xrp_price = btc_ctx.get("xrp_last") or snap.get("mark_price") or 0.0
        btc_sol = btc_ctx.get("btc_sol_ratio") or 0.0
        btc_xrp = btc_ctx.get("btc_xrp_ratio") or 0.0

        balance_total = float(snap.get("balance", {}).get("total") or 0.0)
        balance_free = float(snap.get("balance", {}).get("free") or 0.0)

        def fmt_pos(sym):
            p_long = next((l for l in legs if (l.get("symbol") or "").upper() == sym and l["side"] == "long"), None)
            p_short = next((l for l in legs if (l.get("symbol") or "").upper() == sym and l["side"] == "short"), None)
            parts = []
            if p_long:
                parts.append(f"🟢L: <code>{p_long['size']:,.1f}</code> ({p_long['uPnL']:+.1f})")
            if p_short:
                parts.append(f"🔴S: <code>{p_short['size']:,.1f}</code> ({p_short['uPnL']:+.1f})")
            return " | ".join(parts) if parts else "Немає"

        xrp_pos = fmt_pos("XRP")
        btc_pos = fmt_pos("BTC")
        sol_pos = fmt_pos("SOL")

        import html
        raw_resp = result.get("raw_response") or ""
        m_lines = []
        for line in raw_resp.split("\n"):
            line = line.strip()
            if not line or line.startswith("```"):
                continue
            m_lines.append(line)
            if len(m_lines) >= 3:
                break
        analysis_text = html.escape("\n".join(m_lines))


        tg_msg = (
            f"<b>📊 QuantumEdge Multi-Asset | Цикл #{state['cycle']}</b>\n"
            f"🪙 <b>BTC:</b> <code>{btc_price:,.1f}</code> | <b>SOL:</b> <code>{sol_price:,.2f}</code> | <b>XRP:</b> <code>{xrp_price:.4f}</code>\n"
            f"📊 <b>Крос-пари:</b> BTC/SOL: <code>{btc_sol}</code> | BTC/XRP: <code>{btc_xrp}</code>\n\n"
            f"<b>🔒 Позиції («Замок»):</b>\n"
            f"• <b>XRP:</b> {xrp_pos}\n"
            f"• <b>BTC:</b> {btc_pos}\n"
            f"• <b>SOL:</b> {sol_pos}\n\n"
            f"<b>💳 Баланс:</b> <code>{balance_total:,.0f} VST</code> (Вільний: <code>{balance_free:,.0f}</code>)\n"
            f"⚡ <b>Вердикт:</b> <b>{result.get('decision')}</b> ({result.get('bias')})\n"
        )

        if analysis_text:
            tg_msg += f"\n<i>{analysis_text}</i>\n"

        if result.get("actions"):
            tg_msg += "\n<b>🛠 Ордери:</b>\n"
            for a in result["actions"]:
                cmd = a["cmd"]
                tg_msg += f"• <code>{' '.join(cmd[:5])}</code>\n"

        send_telegram_report(tg_msg)
    except Exception as te:
        print(f"[TRADER] Telegram send exception: {te}")

    print(f"[TRADER] cycle {state['cycle']} done.")


if __name__ == "__main__":
    deep_flag = "--deep" in sys.argv
    main(deep=deep_flag)

