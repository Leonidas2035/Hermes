"""
QuantumEdge Analysis — Aggregator
Збирає всі дані (індикатори + біржа + TV + новини + BTC) в ОДИН
структурований звіт для якісного аналізу Супервізора.

Вихід: dict -> JSON-файл (latest.json) + історія (history/).
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from indicators import compute_indicators, trend_score
from market_data import (
    fetch_xrp_klines, fetch_funding_oi, fetch_order_book,
    fetch_btc_context, fetch_tv_rating, fetch_news, trading_session,
)

ANALYSIS_DIR = Path("/home/layman/.hermes/quantumedge_analysis")
HISTORY_DIR = ANALYSIS_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def build_report(symbol: str = "XRPUSDT", interval: str = "15m") -> dict:
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "symbol": symbol,
        "interval": interval,
        "session": trading_session(),
        "data": {},
        "errors": [],
    }

    # --- 1. Klines + індикатори ---
    kl = fetch_xrp_klines(interval, limit=100)
    if kl.get("ok"):
        import pandas as pd
        df = pd.DataFrame(kl["klines"])
        if len(df) >= 20:
            ind = compute_indicators(df)
            score = trend_score(ind)
            report["data"]["technicals"] = {**ind, **score}
        else:
            report["errors"].append(f"klines too short: {len(df)}")
            report["data"]["technicals"] = None
    else:
        report["errors"].append(f"klines: {kl.get('error')}")
        report["data"]["technicals"] = None

    # --- 2. Funding + OI ---
    fo = fetch_funding_oi()
    report["data"]["funding_oi"] = fo
    if "funding_error" in fo:
        report["errors"].append(fo["funding_error"])

    # --- 3. Order book ---
    ob = fetch_order_book(20)
    report["data"]["order_book"] = ob
    if not ob.get("ok"):
        report["errors"].append(ob.get("error", "book fail"))

    # --- 4. BTC ---
    btc = fetch_btc_context()
    report["data"]["btc"] = btc
    if "btc_error" in btc:
        report["errors"].append(btc["btc_error"])

    # --- 5. TV rating ---
    tv = fetch_tv_rating(symbol)
    report["data"]["tv"] = tv
    if not tv.get("ok"):
        report["errors"].append(f"tv: {tv.get('error')}")

    # --- 6. News ---
    news = fetch_news(symbol, limit=3)
    report["data"]["news"] = news
    if not news.get("ok"):
        report["errors"].append(f"news: {news.get('error')}")

    # --- СИНТЕЗ BIAS (для швидкого огляду) ---
    report["synthesis"] = _synthesize(report["data"])
    return report


def _synthesize(data: dict) -> dict:
    """Швидкий синтез bias з усіх джерел."""
    bias_parts = []

    # Technical (RSI/MACD/BB)
    tech = data.get("technicals")
    if tech:
        bias_parts.append(tech.get("bias"))  # LONG/SHORT/NEUTRAL

    # TV rating
    tv = data.get("tv", {})
    if tv.get("ok"):
        rec = (tv.get("technicalsPage", {}) or {}).get("rating")
        rating_map = {"Strong Buy": "LONG", "Buy": "LONG", "Neutral": "NEUTRAL",
                      "Sell": "SHORT", "Strong Sell": "SHORT"}
        if rec in rating_map:
            bias_parts.append(rating_map[rec])

    # Funding
    fo = data.get("funding_oi", {})
    fr = fo.get("funding_rate")
    if fr is not None:
        bias_parts.append("LONG" if fr > 0 else "SHORT")

    # News
    news = data.get("news", {})
    ns = news.get("sentiment")
    if ns == "BULLISH":
        bias_parts.append("LONG")
    elif ns == "BEARISH":
        bias_parts.append("SHORT")

    # Підрахунок
    from collections import Counter
    c = Counter(bias_parts)
    long_n = c.get("LONG", 0)
    short_n = c.get("SHORT", 0)
    neutral_n = c.get("NEUTRAL", 0)

    if long_n > short_n:
        final = "LONG"
    elif short_n > long_n:
        final = "SHORT"
    else:
        final = "NEUTRAL"

    return {
        "votes": {"LONG": long_n, "SHORT": short_n, "NEUTRAL": neutral_n},
        "final_bias": final,
        "confidence": (max(long_n, short_n) / max(1, len(bias_parts))),
    }


def save_report(report: dict):
    latest = ANALYSIS_DIR / "latest.json"
    latest.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    # Історія по годинах/хвилинах
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (HISTORY_DIR / f"report_{ts}.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    # Обмежимо історію 200 файлами
    files = sorted(HISTORY_DIR.glob("report_*.json"))
    for f in files[:-200]:
        try:
            f.unlink()
        except Exception:
            pass


def main():
    report = build_report()
    save_report(report)
    syn = report["synthesis"]
    print(f"=== ANALYIS READY ===")
    print(f"Session: {report['session']} | Bias: {syn['final_bias']} "
          f"(conf {syn['confidence']:.0%}) | votes {syn['votes']}")
    tech = report['data'].get('technicals')
    if tech:
        print(f"RSI={tech['rsi_14']} ({tech['rsi_zone']}) | MACD={tech['macd_state']} | "
              f"BB_pos={tech['bb_position']} | ATR%={tech['atr_pct']}")
    if report["errors"]:
        print(f"Errors: {report['errors']}")
    print(f"Saved: {ANALYSIS_DIR / 'latest.json'}")


if __name__ == "__main__":
    main()
