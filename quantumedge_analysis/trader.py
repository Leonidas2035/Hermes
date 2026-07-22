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
    """Розумний алгоритм SL (замість плоського BE).
    
    1. Прибрати стекінг: перед новим SL скасовувати старий (cancel по ID + ідемпотентність).
    2. Розумний SL замість плоского BE: breakeven + крихта як мінімум; трейлінг по ATR/ціні;
       не рухати при HIGH-маніпуляції; тісніший SL при розвороті (RSI>70 + MACD_hist<0 або пробій bid-wall);
       запас від entry проти гепу.
    """
    actions = []
    
    # Отримуємо всі сирі відкриті ордери від CCXT, щоб мати точні stopLossPrice
    raw_orders = get_raw_open_orders()
    
    for leg in snap.get("legs", []):
        if leg["size"] <= 0:
            continue
        entry = leg["entry"]
        if not entry:
            continue
        u = leg["uPnL"]
        if u <= 0:
            continue  # лише профітні позиції
            
        pos_side = leg["side"]
        
        # Визначаємо базовий SL (breakeven + крихта)
        # Для LONG: entry * (1 + BE_PROFIT_PCT / 100)
        # Для SHORT: entry * (1 - BE_PROFIT_PCT / 100)
        if pos_side == "long":
            base_sl = entry * (1.0 + BE_PROFIT_PCT / 100.0)
        else:
            base_sl = entry * (1.0 - BE_PROFIT_PCT / 100.0)
            
        # Розраховуємо зміну ціни у відсотках від входу
        if pos_side == "long":
            move_pct = (price - entry) / entry * 100.0
        else:
            move_pct = (entry - price) / entry * 100.0
            
        # Перевірка на розворот
        reversal = False
        reversal_reason = ""
        if SL_TIGHTEN_ON_REVERSAL and indicators:
            rsi = indicators.get("rsi")
            macd_hist = indicators.get("macd_hist")
            
            if pos_side == "long":
                # Умова розвороту для LONG: RSI > 70 ТА MACD_hist < 0
                if rsi is not None and rsi > 70 and macd_hist is not None and macd_hist < 0:
                    reversal = True
                    reversal_reason = f"RSI={round(rsi,1)} MACD_hist={round(macd_hist,4)}"
                # АБО пробій bid-wall
                elif book and book.get("bid_walls"):
                    highest_bid_wall = max(w[0] for w in book["bid_walls"])
                    if price < highest_bid_wall:
                        reversal = True
                        reversal_reason = f"price broken bid-wall ({price} < {highest_bid_wall})"
            else:
                # Умова розвороту для SHORT: RSI < 30 ТА MACD_hist > 0
                if rsi is not None and rsi < 30 and macd_hist is not None and macd_hist > 0:
                    reversal = True
                    reversal_reason = f"RSI={round(rsi,1)} MACD_hist={round(macd_hist,4)}"
                # АБО пробій ask-wall
                elif book and book.get("ask_walls"):
                    lowest_ask_wall = min(w[0] for w in book["ask_walls"])
                    if price > lowest_ask_wall:
                        reversal = True
                        reversal_reason = f"price broken ask-wall ({price} > {lowest_ask_wall})"
        
        # Перевірка на маніпуляцію
        manip_hold = False
        if manip and manip.get("severity") == "HIGH" and conviction < 0.6:
            manip_hold = True
            
        # Визначаємо новий цільовий Stop-Loss
        reason = "BE"
        new_sl = base_sl
        
        if reversal:
            # Тісніший SL при розвороті: тримаємо base_sl (entry + BE_PROFIT_PCT)
            # без трейлу, щоб зафіксувати прибуток
            new_sl = base_sl
            reason = "reversal-tighten"
        elif manip_hold:
            # Не рухаємо SL при HIGH-маніпуляції з низькою conviction
            new_sl = base_sl
            reason = "manip-hold"
        elif move_pct >= TRAIL_TRIGGER_PCT:
            # Трейлінг по ATR/ціні активований
            if pos_side == "long":
                trail_sl = price * (1.0 - TRAIL_DIST_PCT / 100.0)
                new_sl = max(base_sl, trail_sl)
            else:
                trail_sl = price * (1.0 + TRAIL_DIST_PCT / 100.0)
                new_sl = min(base_sl, trail_sl)
            reason = "trail"
            
        # Знаходимо всі поточні Stop-Loss ордери для цієї ноги в системі
        target_side = "sell" if pos_side == "long" else "buy"
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
                
        # Розраховуємо нове значення, округлене до 4 знаків
        new_sl_rounded = round(new_sl, 4)
        
        # Перевірка ідемпотентності:
        # Якщо вже є рівно ОДИН SL і його ціна дорівнює # =====================================================================
# РІШЕННЯ ТРЕЙДЕРА
# =====================================================================
def decide_and_act(report: dict, state: dict, deep: bool = False) -> dict:
    """
    Делегує прийняття рішень великій моделі Antigravity (2T+) через agy CLI.
    Отримує перелік торгових команд у форматі JSON, парсить їх та виконує.
    """
    import re
    
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
    
    # 2. Розраховуємо обмеження нотіоналу
    SAFE_NOTIONAL = 900_000.0  # USDT запас
    long_leg = next((l for l in legs if l["side"] == "long"), None)
    short_leg = next((l for l in legs if l["side"] == "short"), None)
    
    long_size = float(long_leg["size"]) if long_leg else 0.0
    short_size = float(short_leg["size"]) if short_leg else 0.0
    
    long_notional = long_size * price
    short_notional = short_size * price
    
    room_notional = max(0.0, SAFE_NOTIONAL - long_notional)
    room_contracts = int(room_notional / price) if price > 0 else 0
    
    # Розраховуємо відстань до ліквідації лонгу
    liq_long = float(long_leg.get("liquidationPrice") or 0) if long_leg else 0.0
    dist_to_liq_pct = 999.0
    if liq_long > 0 and price > 0:
        dist_to_liq_pct = (price - liq_long) / price * 100.0
        
    # 3. Будуємо промпт для Antigravity
    prompt = f"""You are the 2T+ Antigravity Trading Brain.
You must analyze the current market state and output a precise trading plan and execution commands.

### OWNER RULES (MUST BE STRICTLY FOLLOWED):
1. NEVER close a losing position manually. If uPnL < 0, wait or hedge.
2. Shrink a losing position ONLY with the profit from the opposite-direction position (harvesting).
3. If indicators are bullish, add LONG. If the trend is exhausted, take profit + add SHORT (do not add to losing side).
4. High risk -> hedge (open/add opposite side) and wait. Trigger: distance to long liquidation < 1.0%.
5. Auto-stop is OFF.
6. Short notional cap is 101,209 USDT. If net short exposure is > 101,209, short can ONLY be shrunk, do NOT add short!
7. Long cap is 1,000,000 USDT (safe target 900,000 USDT). Max allowed contracts to add to long: {room_contracts}.

### CURRENT STATE SNAPSHOT:
- Asset: XRPUSDT (on Bybit/BingX VST)
- Current price: {price}
- Open orders count: {open_orders_count}
- Distance to LONG liquidation: {dist_to_liq_pct:.3f}% (Liq price: {liq_long})
- Long Position size: {long_size} (Notional: {long_notional:.1f} USDT, uPnL: {long_leg.get('uPnL') if long_leg else 0.0})
- Short Position size: {short_size} (Notional: {short_notional:.1f} USDT, uPnL: {short_leg.get('uPnL') if short_leg else 0.0})
- Free Balance: {free_balance} USDT
- Open Orders List: {json.dumps(open_orders, default=str)}

### MARKET DATA & METRICS:
- Indicator Bias: {bias} (Conviction: {conviction * 100:.1f}%)
- Technical indicators: {json.dumps(tech, default=str)}
- Trend shift status: {json.dumps(trend, default=str)}
- Order Book walls & imbalance: {json.dumps(book, default=str)}
- Market Manipulation: {json.dumps(manip, default=str)}
- BTC context: {json.dumps(report.get('btc'), default=str)}
- BTC Liquidation Map zones: {json.dumps(report.get('liq_map'), default=str)}
- TradingView technical rating: {json.dumps(report.get('tv'), default=str)}
- News sentiment: {json.dumps(report.get('news'), default=str)}

### TASK:
1. Write a very brief analysis of the current market state and your plan (in Ukrainian, max 5 lines).
2. Define the exact ccxt/qe_trade commands to execute.
3. Output the commands ONLY in a ```json code block at the very end of your response.

Valid commands format (JSON array of arrays):
```json
[
  ["place", "buy"|"sell", "LONG"|"SHORT", qty, price, tp, sl],
  ["market", "buy"|"sell", "LONG"|"SHORT", qty],
  ["cancel", "order_id"],
  ["modify_sl", "LONG"|"SHORT", new_sl_price]
]
```
If no action is required, output: `[]`.
"""
    
    print("[TRADER] Invoking Antigravity (2T+) for trading decision...")
    
    # 4. Викликаємо agy CLI
    try:
        r = subprocess.run(
            ["agy", "--dangerously-skip-permissions", "--print", prompt],
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
            res = qe(cmd_args)
            
            # Логування дії
            act_entry = {"act": f"AG_{action_type.upper()}", "cmd": [action_type] + cmd_args, "result": res}
            actions.append(act_entry)
            
            log_entry = {"act": f"AG_{action_type.upper()}", "args": cmd_args, "result": (res.get("error") or res.get("id") or "ok")}
            if action_type == "place" and len(cmd_args) >= 3:
                log_entry["qty"] = cmd_args[2]
                log_entry["price"] = cmd_args[3] if len(cmd_args) > 3 else "0"
            elif action_type == "market" and len(cmd_args) >= 3:
                log_entry["qty"] = cmd_args[2]
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
    }


# =====================================================================
# MAIN
# =====================================================================
def main(deep: bool = False):
    mode = "DEEP(15m)" if deep else "TRADE(5m)"
    print(f"[TRADER] {mode} cycle start {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")

    # 1. Аналіз (мозок акули)
    report = analyze()
    save_analysis(report)

    # 2. Рішення + дія
    state = load_state()
    state["cycle"] += 1
    state["last_bias"] = report["verdict"]["bias"]

    result = decide_and_act(report, state, deep=deep)
    save_state(state)

    # 3. Звіт
    print(f"[TRADER] bias={result.get('bias')} conv={result.get('conviction')} "
          f"decision={result.get('decision')} actions={len(result.get('actions', []))}")
    for a in result.get("actions", []):
        print(f"   - {a['act']}: {a.get('qty', a.get('price', ''))}")
    if result.get("notes"):
        for n in result["notes"]:
            print(f"   * {n}")

    # 4. Підсумок PnL з журналу
    try:
        import re
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
        print(f"[TRADER] realized PnL (journal): {realized:.2f} VST | {wins}/{closed} wins")
    except Exception as e:
        print(f"[TRADER] pnl read warn: {e}")

    print(f"[TRADER] cycle {state['cycle']} done.")


if __name__ == "__main__":
    deep_flag = "--deep" in sys.argv
    main(deep=deep_flag)
