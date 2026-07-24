"""
================================================================
QuantumEdge — MARKET ANALYSIS (Hermes Trader / Market-Maker mode)
================================================================
Автор: Hermes (Супервізор->Трейдер-акула, 15+ років на ф'ючерсах)
Папка: ~/.hermes/quantumedge_analysis/market_analysis.py

ЦЕ НЕ СТАРИЙ supervisor_market_analysis.py. Це новий аналітичний
контур трейдера-маркет-мейкера:
  - Раннє виявлення зміни тренду (MACD-перелом, BB-пробій, RSI-дивергенція,
    структура LH/LL / HL/HH на клинках)
  - Читання маніпуляцій стаканом (spoofing, wall-кластери, iceberg-об'єми,
    фальшиві пробої, absorption)
  - Макро-картина по BTC + кореляція XRP/BTC
  - Вердикт трейдера: bias + conviction + конкретні рівні входу/виходу

НЕ СТАВИТЬ ОРДЕРИ. Тільки аналіз + торговий план для виконання
через qe_trade.py (або вручну власником).

Залежить від: indicators.py, market_data.py (той самий venv QuantumEdge).
================================================================
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from indicators import compute_indicators, trend_score
from market_data import (
    fetch_xrp_klines, fetch_funding_oi, fetch_order_book,
    fetch_btc_context, fetch_tv_rating, fetch_news, trading_session,
)
from config import ASSET_STRATEGIES, GLOBAL_LIMITS
from recovery_ledger import get_accumulated_loss, get_recovery_target

ANALYSIS_DIR = Path("/home/layman/.hermes/quantumedge_analysis")
HISTORY_DIR = ANALYSIS_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================================
# 1. РАННЄ ВИЯВЛЕННЯ ЗМІНИ ТРЕНДУ
# =====================================================================
def detect_trend_shift(df: pd.DataFrame) -> dict:
    """
    Акула бачить зміну тренду ДО того, як її побачать лямбда-боти.
    Шукаємо:
      - MACD-перелом (hist змінив знак + line crosses signal)
      - BB-пробій/стискання (squeeze -> imminent move)
      - RSI-дивергенція (ціна новий хай, RSI нижчий -> розворот вниз)
      - Структура свінгів (HH/HL = аптренд, LH/LL = даунтренд)
    """
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # --- MACD ---
    macd = ta_trend_macd(close)
    hist = macd["hist"]
    line = macd["line"]
    signal = macd["signal"]
    macd_turning_up = hist.iloc[-2] < 0 and hist.iloc[-1] > 0
    macd_turning_down = hist.iloc[-2] > 0 and hist.iloc[-1] < 0
    macd_cross_up = line.iloc[-2] <= signal.iloc[-2] and line.iloc[-1] > signal.iloc[-1]
    macd_cross_down = line.iloc[-2] >= signal.iloc[-2] and line.iloc[-1] < signal.iloc[-1]

    # --- Bollinger squeeze ---
    bb = ta_bb(close)
    width = (bb["upper"] - bb["lower"]) / bb["mid"]
    width_now = width.iloc[-1]
    width_prev = width.iloc[-10] if len(width) > 10 else width.iloc[0]
    squeezing = width_now < width_prev * 0.85  # стискання = скоро імпульс
    band_walk_up = close.iloc[-1] >= bb["upper"].iloc[-1]
    band_walk_dn = close.iloc[-1] <= bb["lower"].iloc[-1]

    # --- RSI divergence (проста: останній свінг-хай/лай vs RSI) ---
    rsi = ta_rsi(close)
    div = _rsi_divergence(close, rsi, high, low)

    # --- Swing structure ---
    structure = _swing_structure(high, low, close)

    # --- ВЕРДИКТ зміни тренду ---
    shift = "NONE"
    signals = []
    if macd_turning_up or macd_cross_up:
        signals.append("MACD_UP")
    if macd_turning_down or macd_cross_down:
        signals.append("MACD_DN")
    if band_walk_up:
        signals.append("BB_WALK_UP")
    if band_walk_dn:
        signals.append("BB_WALK_DN")
    if div == "BEARISH":
        signals.append("RSI_DIV_BEAR")
    if div == "BULLISH":
        signals.append("RSI_DIV_BULL")

    up_sig = sum(1 for s in signals if ("UP" in s or "BULL" in s))
    dn_sig = sum(1 for s in signals if ("DN" in s or "BEAR" in s))

    if up_sig >= 2 and dn_sig == 0:
        shift = "REVERSAL_UP"
    elif dn_sig >= 2 and up_sig == 0:
        shift = "REVERSAL_DOWN"
    elif squeezing and (up_sig or dn_sig):
        shift = "SQUEEZE_BREAKOUT_PENDING"

    return {
        "shift": shift,
        "signals": signals,
        "macd_turning_up": macd_turning_up,
        "macd_turning_down": macd_turning_down,
        "squeeze": bool(squeezing),
        "band_walk": "UP" if band_walk_up else ("DOWN" if band_walk_dn else "NONE"),
        "rsi_divergence": div,
        "structure": structure,
        "bb_width_pct": round(float(width_now * 100), 3),
    }


def _rsi_divergence(close, rsi, high, low) -> str:
    """Спрощена дивергенція: порівняти 2 останні свінги."""
    try:
        # останні 2 локальні максимуми/мінімуми по close
        n = len(close)
        if n < 30:
            return "NONE"
        # хай: індекси 2-х вищих піків у 2-й половині
        h1, h2 = close.iloc[-20:-5].max(), close.iloc[-5:].max()
        r1, r2 = rsi.iloc[-20:-5].max(), rsi.iloc[-5:].max()
        if h2 > h1 and r2 < r1:
            return "BEARISH"  # ціна вище, RSI нижче -> розворот вниз
        if close.iloc[-5:].min() < close.iloc[-20:-5].min() and rsi.iloc[-5:].min() > rsi.iloc[-20:-5].min():
            return "BULLISH"
    except Exception:
        pass
    return "NONE"


def _swing_structure(high, low, close) -> dict:
    """Визначаємо структуру: HH/HL (бичача) чи LH/LL (ведмедяча)."""
    try:
        recent = close.iloc[-20:]
        last = recent.iloc[-1]
        prev = recent.iloc[0]
        if last > prev:
            return {"trend": "UP", "note": "Higher close sequence"}
        else:
            return {"trend": "DOWN", "note": "Lower close sequence"}
    except Exception:
        return {"trend": "UNKNOWN"}


# =====================================================================
# 2. АНАЛІЗ МАНІПУЛЯЦІЙ СТАКАНОМ (Market-Maker reading)
# =====================================================================
def detect_manipulation(book: dict) -> dict:
    """
    Акула читає стакан як книгу. Шукаємо:
      - Spoofing: величезна стіна, якої не має бути (або asymmetry)
      - Wall clusters: щільні стіни на рівні (support/resistance фейкові?)
      - Absorption: великі об'єми при малому русі ціни
      - Imbalance extremes: >0.3 або <-0.3 = один бік тисне
    """
    if not book.get("ok"):
        return {"detected": False, "reason": "no book"}

    bids = book.get("bid_walls", [])
    asks = book.get("ask_walls", [])
    imb = book.get("imbalance", 0)
    bv = book.get("bid_vol10", 0)
    av = book.get("ask_vol10", 0)

    findings = []
    severity = "LOW"

    # 1. Spoofing / гігантська стіна (набагато більша за інші)
    all_walls = bids + asks
    if all_walls:
        max_wall = max(w[1] for w in all_walls)
        avg_wall = sum(w[1] for w in all_walls) / len(all_walls)
        if max_wall > avg_wall * 4 and max_wall > 300000:
            side = "BID" if any(w[1] == max_wall and w in bids for w in all_walls) else "ASK"
            findings.append(f"SPOOF_{side}: стіна {max_wall:,.0f} > 4x середньої ({avg_wall:,.0f})")
            severity = "HIGH"

    # 2. Imbalance extreme
    if imb > 0.3:
        findings.append(f"BUY_PRESSURE: imbalance +{imb} (покупці тиснуть)")
        severity = "MEDIUM" if severity == "LOW" else severity
    elif imb < -0.3:
        findings.append(f"SELL_PRESSURE: imbalance {imb} (продавці тиснуть)")
        severity = "MEDIUM" if severity == "LOW" else severity

    # 3. Wall cluster біля ціни (фейковий support/resistance?)
    #    якщо 3+ стіни в межах 0.2% — можливо MM тримає рівень
    near_walls = 0
    for w in bids + asks:
        near_walls += 1
    if len(bids) >= 3 and len(asks) >= 3:
        findings.append(f"WALL_CLUSTER: щільні стіни з обох боків (range-bound MM)")

    # 4. Absorption (багато об'єму, мало руху) — порівняти bv+av vs ATR
    #    якщо об'єм великий, а ціна в стакані вузька — absorption
    total_vol = bv + av
    if total_vol > 2_000_000:
        findings.append(f"HIGH_LIQUIDITY: {total_vol:,.0f} в топ-10 (можлива absorption)")

    return {
        "detected": len(findings) > 0,
        "severity": severity,
        "findings": findings,
        "imbalance": imb,
        "bid_vol10": bv,
        "ask_vol10": av,
    }


# =====================================================================
# 3. МАКРО ПО BTC + КОРЕЛЯЦІЯ
# =====================================================================
def analyze_btc(btc: dict) -> dict:
    if "btc_error" in btc:
        return {"status": "error", "note": btc["btc_error"]}
    last = btc.get("btc_last")
    ch = btc.get("btc_change24")
    xr = btc.get("xrp_btc")
    out = {"btc_last": last, "btc_change24": ch, "xrp_btc": xr, "zone": "MID", "bias": "NEUTRAL"}
    if last:
        if last <= 64500:
            out["zone"] = "CORRECTION_63.6-64.5k"
            out["bias"] = "WAIT_SWEEP"  # відео-логіка: чекати свіп вниз
            out["note"] = "BTC у зоні корекції — НЕ купувати на хаях, чекати sweep"
        elif last >= 66000:
            out["zone"] = "BREAKOUT_UP"
            out["bias"] = "LONG_AGGRESSIVE"
            out["note"] = "BTC пробій >66k — лонг агресивніше"
        else:
            out["zone"] = "MID_RANGE"
            out["bias"] = "NEUTRAL"
            out["note"] = "BTC середина діапазону — нейтрально"
    return out


# =====================================================================
# 4. СИНТЕЗ ВЕРДИКТУ ТРЕЙДЕРА
# =====================================================================
def trader_verdict(tech, trend, manip, btc_an, tv, news, session) -> dict:
    """
    Акула зважує ВСЕ і видає вердикт.
    conviction: 0..1 (наскільки впевнений)
    """
    votes_long = 0
    votes_short = 0
    notes = []

    # Technical bias
    tb = tech.get("bias")
    if tb == "LONG":
        votes_long += 1
    elif tb == "SHORT":
        votes_short += 1
    else:
        notes.append("tech NEUTRAL")

    # Trend shift
    sh = trend.get("shift")
    if sh == "REVERSAL_UP":
        votes_long += 2
        notes.append("TREND SHIFT UP (early)")
    elif sh == "REVERSAL_DOWN":
        votes_short += 2
        notes.append("TREND SHIFT DOWN (early)")
    elif sh == "SQUEEZE_BREAKOUT_PENDING":
        notes.append("SQUEEZE — чекати пробій")

    # BTC macro
    bb = btc_an.get("bias")
    if bb == "LONG_AGGRESSIVE":
        votes_long += 1
    elif bb == "WAIT_SWEEP":
        votes_short += 0  # нейтрально-обережно
        notes.append("BTC sweep pending — обережно")

    # TV
    if tv.get("ok"):
        rec = (tv.get("technicalsPage", {}) or {}).get("rating")
        if rec in ("Strong Buy", "Buy"):
            votes_long += 1
        elif rec in ("Sell", "Strong Sell"):
            votes_short += 1

    # News
    ns = news.get("sentiment")
    if ns == "BULLISH":
        votes_long += 1
    elif ns == "BEARISH":
        votes_short += 1

    # Manipulation корекція
    if manip.get("detected") and manip.get("severity") == "HIGH":
        notes.append(f"MM MANIP: {manip['findings']}")
        # spoof на bid -> можливо знімуть вниз; spoof на ask -> знімуть вгору
        for f in manip["findings"]:
            if "SPOOF_BID" in f:
                votes_short += 1
                notes.append("spoof bid = фейк support, чекай зняття")
            elif "SPOOF_ASK" in f:
                votes_long += 1
                notes.append("spoof ask = фейк resistance, чекай зняття")

    # Фінальний вердикт
    if votes_long > votes_short:
        bias = "LONG"
    elif votes_short > votes_long:
        bias = "SHORT"
    else:
        bias = "NEUTRAL"

    total = votes_long + votes_short
    conviction = max(votes_long, votes_short) / max(1, total)

    # Якщо маніпуляція HIGH — знижуємо conviction (не ліземо в пастку)
    if manip.get("severity") == "HIGH":
        conviction *= 0.7

    return {
        "bias": bias,
        "conviction": round(conviction, 2),
        "votes_long": votes_long,
        "votes_short": votes_short,
        "notes": notes,
    }


# =====================================================================
# 5. РІВНІ ВХОДУ/ВИХОДУ (план трейдера)
# =====================================================================
def build_levels(tech, book, trend) -> dict:
    price = tech["price"]
    atr = tech["atr_14"]
    bb_l, bb_m, bb_u = tech["bb_lower"], tech["bb_mid"], tech["bb_upper"]

    # Базові рівні від BB + ATR
    if tech["bias"] == "LONG" or trend["shift"] in ("REVERSAL_UP", "NONE"):
        entry = round(bb_l if price > bb_l else price * 0.999, 5)
        tp1 = round(bb_m, 5)
        tp2 = round(bb_u, 5)
        sl = round(entry - atr * 1.5, 5)
    else:
        entry = round(bb_u if price < bb_u else price * 1.001, 5)
        tp1 = round(bb_m, 5)
        tp2 = round(bb_l, 5)
        sl = round(entry + atr * 1.5, 5)

    # Мікро-рівні зі стакану (стінки = фактичний support/resistance)
    bid_walls = book.get("bid_walls", [])
    ask_walls = book.get("ask_walls", [])
    support = bid_walls[0][0] if bid_walls else round(bb_l, 5)
    resistance = ask_walls[0][0] if ask_walls else round(bb_u, 5)

    return {
        "price": price,
        "entry_zone": entry,
        "tp1": tp1,
        "tp2": tp2,
        "stop_loss": sl,
        "support_book": support,
        "resistance_book": resistance,
        "atr": atr,
    }


# =====================================================================
# HELPERS (ta wrappers)
# =====================================================================
def ta_trend_macd(close):
    import ta
    m = ta.trend.MACD(close)
    return {"line": m.macd(), "signal": m.macd_signal(), "hist": m.macd_diff()}


def ta_bb(close):
    import ta
    b = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    return {"upper": b.bollinger_hband(), "mid": b.bollinger_mavg(), "lower": b.bollinger_lband()}


def ta_rsi(close):
    import ta
    return ta.momentum.RSIIndicator(close, window=14).rsi()


# =====================================================================
# MAIN
# =====================================================================
def run(symbol: str = "XRPUSDT", interval: str = "15m") -> dict:
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "symbol": symbol,
        "interval": interval,
        "session": trading_session(),
        "trader": "Hermes Market-Maker (15+ yr)",
    }

    # 1. Klines + індикатори
    kl = fetch_xrp_klines(interval, limit=120)
    df = pd.DataFrame(kl["klines"]) if kl.get("ok") else pd.DataFrame()
    if len(df) >= 20:
        tech = compute_indicators(df)
        score = trend_score(tech)
        tech.update(score)
        
        # Calculate trend exhaustion: price dev >= 3*ATR and RSI > 75 or < 25
        price = float(tech.get("price", 0))
        bb_mid = float(tech.get("bb_mid", price))
        atr_14 = float(tech.get("atr_14", 0))
        rsi_14 = float(tech.get("rsi_14", 50))
        
        exhaustion = False
        if atr_14 > 0:
            dev = abs(price - bb_mid)
            if dev >= 3 * atr_14 and (rsi_14 > 75 or rsi_14 < 25):
                exhaustion = True
        tech["trend_exhaustion"] = exhaustion
    else:
        tech = {"bias": "NEUTRAL", "error": "klines short", "trend_exhaustion": False}
    report["technicals"] = tech

    # 2. Trend shift
    if len(df) >= 30:
        report["trend_shift"] = detect_trend_shift(df)
    else:
        report["trend_shift"] = {"shift": "NONE", "error": "no df"}

    # 3. Book + manipulation
    book = fetch_order_book(20)
    report["order_book"] = book
    report["manipulation"] = detect_manipulation(book)

    # 4. Funding/OI
    report["funding_oi"] = fetch_funding_oi()

    # 5. BTC
    btc = fetch_btc_context()
    report["btc"] = btc
    report["btc_analysis"] = analyze_btc(btc)

    # 6. TV + News
    tv = fetch_tv_rating(symbol)
    news = fetch_news(symbol, limit=3)
    report["tv"] = tv
    report["news"] = news

    # 7. Verdict + levels
    report["verdict"] = trader_verdict(
        tech, report["trend_shift"], report["manipulation"],
        report["btc_analysis"], tv, news, report["session"])
    report["levels"] = build_levels(tech, book, report["trend_shift"])

    # 8. Recovery Ledger & Signal Integration
    base_asset = symbol.upper().replace("USDT","").replace("/","").replace(":","").strip()
    acc_loss = get_accumulated_loss(base_asset)
    report["recovery_ledger"] = {"symbol": base_asset, "accumulated_loss": acc_loss}
    if acc_loss > 0:
        rsi_val = float(tech.get("rsi_14", 50))
        if rsi_val < 35 or tech.get("macd_hist", 0) > 0:
            report["recovery_signal"] = {
                "symbol": base_asset,
                "signal": "RECOVERY_AVERAGE_DOWN",
                "accumulated_loss": acc_loss,
                "recommendation": "Reversal detected on bottom/recovery zone; average down to update breakeven & TP target."
            }

    # 9. Hedge Opportunities
    hedge_ops = []
    rsi_val = float(tech.get("rsi_14", 50))
    if rsi_val > 75 or tech.get("trend_exhaustion"):
        hedge_ops.append({
            "symbol": symbol,
            "signal": "COUNTER_SHORT_SCALP",
            "reason": f"RSI={rsi_val} overbought / trend exhaustion"
        })
    elif rsi_val < 25 or (tech.get("trend_exhaustion") and rsi_val < 30):
        hedge_ops.append({
            "symbol": symbol,
            "signal": "COUNTER_LONG_SCALP",
            "reason": f"RSI={rsi_val} oversold / trend exhaustion"
        })
    report["hedge_opportunities"] = hedge_ops

    # 10. Liquidation map
    report["liq_map"] = _load_liqmap()

    return report


def _load_liqmap(max_age_min: int = 20) -> dict:
    """Читає runtime/liqmap_latest.json; регенерує якщо застарів/відсутній."""
    import subprocess, time as _t
    qe = Path("/home/layman/.hermes/quantumedge_analysis")
    jf = qe / "runtime" / "liqmap_latest.json"
    try:
        stale = (not jf.exists()) or (_t.time() - jf.stat().st_mtime > max_age_min * 60)
        if stale:
            subprocess.run(
                [str(qe / "venv" / "bin" / "python3"), "-m", "tools.liqmap.cli", "build",
                 "--tf", "1h", "--limit", "200"],
                cwd=str(qe), capture_output=True, timeout=120)
        d = json.loads(jf.read_text())
        return {
            "last_price": d.get("last_price"),
            "nearest_long_liq": d.get("nearest_long_liq"),
            "nearest_short_liq": d.get("nearest_short_liq"),
            "strongest_zone": d.get("strongest_zone"),
            "interpretation": d.get("interpretation"),
            "zones": d.get("zones", [])[:6],
        }
    except Exception as e:
        return {"error": str(e)[:100]}


def save(r: dict):
    out = ANALYSIS_DIR / "market_analysis.json"
    latest_out = ANALYSIS_DIR / "latest.json"
    content = json.dumps(r, indent=2, default=str)
    out.write_text(content, encoding="utf-8")
    latest_out.write_text(content, encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (HISTORY_DIR / f"ma_{ts}.json").write_text(content, encoding="utf-8")
    for f in sorted(HISTORY_DIR.glob("ma_*.json"))[:-200]:
        try:
            f.unlink()
        except Exception:
            pass


def _print_human(r: dict):
    v = r["verdict"]
    t = r["technicals"]
    tr = r["trend_shift"]
    m = r["manipulation"]
    b = r["btc_analysis"]
    lv = r["levels"]
    print("=" * 64)
    print(f"  MARKET ANALYSIS — {r['symbol']}  [{r['session']} session]")
    print(f"  {r['generated_at']}")
    print("=" * 64)
    print(f"  VERDICT: {v['bias']}  | conviction {v['conviction']:.0%}")
    print(f"  votes L/S: {v['votes_long']}/{v['votes_short']}")
    for n in v["notes"]:
        print(f"    • {n}")
    print("-" * 64)
    print(f"  PRICE: {lv['price']} | RSI {t.get('rsi_14')} ({t.get('rsi_zone')}) "
          f"| MACD {t.get('macd_state')} | BB_pos {t.get('bb_position')}")
    print(f"  TREND SHIFT: {tr.get('shift')} {tr.get('signals')}")
    print(f"  MM MANIP: {m.get('severity')} — {m.get('findings')}")
    print(f"  BTC: {b.get('zone')} ({b.get('bias')}) | XRP/BTC {b.get('xrp_btc')}")
    lm = r.get("liq_map", {})
    if lm and not lm.get("error"):
        nl = lm.get("nearest_long_liq") or {}
        ns = lm.get("nearest_short_liq") or {}
        sz = lm.get("strongest_zone") or {}
        print(f"  LIQ-MAP BTC: магніт↓ {nl.get('price')} ({nl.get('dist_pct')}%) | "
              f"магніт↑ {ns.get('price')} ({ns.get('dist_pct')}%) | "
              f"найсильн. {sz.get('price')} [{sz.get('side')}]")
    print("-" * 64)
    print(f"  ENTRY ~{lv['entry_zone']} | TP1 {lv['tp1']} | TP2 {lv['tp2']} | SL {lv['stop_loss']}")
    print(f"  Book S/R: supp {lv['support_book']} / res {lv['resistance_book']}")
    print("=" * 64)


if __name__ == "__main__":
    rep = run()
    save(rep)
    _print_human(rep)
