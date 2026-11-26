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
  7. Min ROI Gate (SOL): Не закривати LONG-позицію SOL менше ніж на +1.5% ROI per trade.

РЕЖИМ: демо (BingX VST). Реальні ордери на рахунку VST.
================================================================
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv

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
    """Викликає qe_trade.py і повертає JSON-результат.
    У DRY_RUN режимі мутаційні дії (place/market/cancel/modify_sl/set_sl)
    НЕ виконуються на біржі — лише логуються для факт-чеку.
    """
    action = (args[0] if args else "").lower()
    MUTATING = {"place", "market", "cancel", "modify_sl", "set_sl"}
    if DRY_RUN and action in MUTATING:
        print(f"[DRY-RUN] WOULD EXECUTE: qe_trade.py {' '.join(map(str, args))}")
        return {"dry_run": True, "action": action, "args": list(args), "simulated": True}
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
# CONTEXTUAL MEMORY BUILDER (Оптимізація для усунення 'амнезії' у 5m)
# =====================================================================
def get_recent_actions(limit: int = 5) -> list:
    """Зчитує останні N дій з журналу угод для запобігання циклічних замін ордерів"""
    recent = []
    if JOURNAL.exists():
        try:
            with open(JOURNAL, "r") as f:
                lines = f.readlines()
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        try:
                            d = json.loads(line)
                            recent.append(d)
                            if len(recent) >= limit:
                                break
                        except Exception:
                            continue
        except Exception:
            pass
    return list(reversed(recent))


# =====================================================================
# ДИСПАТЧЕР РІШЕНЬ (Зчитує ринок + Antigravity)
# =====================================================================
def decide_and_act(report: dict, state: dict, deep: bool = False) -> dict:
    price = report["levels"]["price"]
    book = report.get("order_book", {})
    tech = report.get("technicals", {})
    verdict = report.get("verdict", {})
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
    
    # 2. Отримуємо макро-контекст по крос-парам
    btc_ctx = report.get("btc") or {}
    btc_price = btc_ctx.get("btc_last") or 0.0
    sol_price = btc_ctx.get("sol_last") or 0.0
    xrp_price = btc_ctx.get("xrp_last") or snap.get("mark_price") or price
    btc_sol_ratio = btc_ctx.get("btc_sol_ratio") or 0.0
    btc_xrp_ratio = btc_ctx.get("btc_xrp_ratio") or 0.0
    
    total_balance = float(balance.get("total") or 1.0)
    free_pct = (free_balance / total_balance) * 100.0 if total_balance > 0 else 100.0
    margin_rule = (
        f"⚠️ [MARGIN LOCK ACTIVE]: Free margin {free_pct:.1f}% is BELOW 10.0% — STRICTLY NO new directional positions. Only reduceOnly / cancellations permitted."
        if free_pct < 10.0 else
        "✅ Free margin OK (>= 10.0%). Normal directional trading permitted under DNA v4.0."
    )

    # 3. Зчитуємо останні 5 дій з журналу пам'яті
    recent_actions = get_recent_actions(5)

    # 4. Будуємо розширений контекстний промпт для Antigravity
    prompt = f"""You are the 2T+ Antigravity Trading Brain operating under HERMES TRADING DNA v4.0 NATIVE.
You must analyze the multi-asset market state (XRP, BTC, SOL) and output precise execution commands.

### ACTIVE TRADING PAIRS & DNA v4.0 DIRECTIVES:
- BTC/USDT: FROZEN MODE. Do NOT place, modify, or close BTC positions without explicit manual order.
- XRP/USDT: LONG under MANUAL control (do NOT average/touch). SHORT SCALP ALLOWED when overbought (5m StochRSI > 80 or heavy Ask walls).
- SOL/USDT: SWING TRADING. Target ROI >= +30.0%. Use TP limit orders, never panic-dump.

### CROSS-PAIR RATIOS & PRICES:
- BTC/USDT: {btc_price} (24h: {btc_ctx.get('btc_change24')}%)
- SOL/USDT: {sol_price} (24h: {btc_ctx.get('sol_change24')}%)
- XRP/USDT: {xrp_price} (24h: {btc_ctx.get('xrp_change24')}%)
- BTC/SOL Ratio: {btc_sol_ratio} | BTC/XRP Ratio: {btc_xrp_ratio}

### MARGIN STATUS & DECAY RULE:
- Total Balance: {total_balance:.2f} VST | Free Balance: {free_balance:.2f} VST ({free_pct:.1f}% free)
{margin_rule}

### 🧠 RECENT EXECUTED ACTIONS (LAST 5 CYCLES / MEMORY PERSISTENCE):
{json.dumps(recent_actions, indent=2, default=str)}

### 📋 HERMES TRADING DNA v4.0 SACRED DIRECTIVES:
1. NO FULL LOSS REALIZATION: NEVER close a losing position (uPnL < 0) 100% per market. Max 50% partial reduction ONLY when offset by counter-profit.
2. MINIMUM ROI GATES: SOL Swing target ROI >= +30.0%. XRP/BTC DCA/Scalp target ROI >= +1.5%.
3. 10% FREE MARGIN PROTECTION: If free margin < 10.0%, output [] (HOLD) or reduceOnly/cancel only. No new directional positions.
4. 5-MINUTE CYCLE MEMORY: Review [RECENT EXECUTED ACTIONS]. Do NOT cancel/replace identical resting limit orders. Avoid cyclic place/cancel loops.
5. STOCH_RSI (5m/15m): StochRSI < 20 = bottom entry; > 80 = top exit / short-scalp signal.
6. BINGX HEDGE: All short/sell closing commands execute with reduceOnly=True automatically.

### CURRENT POSITIONS SNAPSHOT:
{json.dumps(legs, indent=2, default=str)}

### OPEN ORDERS LIST:
{json.dumps(open_orders, indent=2, default=str)}

### MARKET INDICATORS & BIAS:
- Technical indicators: {json.dumps(tech, default=str)}
- Order Book walls & imbalance: {json.dumps(book, default=str)}

### TASK:
1. Write a very brief analysis of the market and cross-pair trends (in Ukrainian, max 3 lines).
2. Output exact execution commands ONLY in a ```json code block at the end.

Valid commands format:
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
    
    # 5. Визначаємо модель та викликаємо agy CLI без прапора --effort для моделей Flash Low
    agy_model = os.getenv("AGY_MODEL", "Gemini 3.6 Flash (High)")
    
    # Для agy CLI: якщо у файлі .env стоїть Low, виправляємо на Gemini 3.6 Flash (High) або викликаємо сумісно
    if agy_model == "Gemini 3.6 Flash (Low)":
        agy_model = "Gemini 3.6 Flash (High)"
        
    agy_cmd = ["agy", "--model", agy_model, "--effort", "high", "--dangerously-skip-permissions", "--print", prompt]
    print(f"[TRADER] Using model: {agy_model}")
        
    try:
        r = subprocess.run(
            agy_cmd,
            capture_output=True, text=True, timeout=120
        )
        if r.returncode != 0:
            # Якщо --effort викликає помилку через версію CLI, повторюємо без --effort
            agy_cmd_fallback = ["agy", "--model", agy_model, "--dangerously-skip-permissions", "--print", prompt]
            r = subprocess.run(agy_cmd_fallback, capture_output=True, text=True, timeout=120)
            
        if r.returncode != 0:
            print(f"[TRADER] agy CLI error: {r.stderr}")
            return {"error": f"agy CLI returned {r.returncode}", "actions": []}
            
        response = r.stdout or ""
        print("\n=== ANTIGRAVITY DECISION & PLAN ===")
        print(response)
        print("===================================\n")
        
        # 6. Парсимо JSON команди з відповіді
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
                    
        # 7. Виконуємо команди
        for cmd in cmd_block:
            if not isinstance(cmd, list) or not cmd:
                continue
            action_type = cmd[0]
            
            cmd_args = []
            for arg in cmd[1:]:
                if arg is None:
                    cmd_args.append("none")
                else:
                    cmd_args.append(str(arg))
            
            while cmd_args and cmd_args[-1].lower() in ("none", "null"):
                cmd_args.pop()
                
            print(f"[TRADER] Executing command: {[action_type] + cmd_args}")
            res = qe([action_type] + cmd_args)
            
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


def main(deep: bool = False):
    mode = "DEEP(15m)" if deep else "TRADE(5m)"
    print(f"[TRADER] {mode} cycle start {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")

    report = analyze()
    save_analysis(report)

    state = load_state()
    state["cycle"] += 1
    state["last_bias"] = report["verdict"]["bias"]

    result = decide_and_act(report, state, deep=deep)
    save_state(state)

    print(f"[TRADER] bias={result.get('bias')} conv={result.get('conviction')} "
          f"decision={result.get('decision')} actions={len(result.get('actions', []))}")
    for a in result.get("actions", []):
        print(f"   - {a['act']}: {a.get('qty', a.get('price', ''))}")

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
            f"<b>📊 QuantumEdge Multi-Asset{' [DRY-RUN]' if DRY_RUN else ''} | Цикл #{state['cycle']}</b>\n"
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
