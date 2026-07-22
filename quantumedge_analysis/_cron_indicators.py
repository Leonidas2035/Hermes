"""Cron helper: compute XRP 1h/5m and BTC 1h indicators (read-only)."""
import sys, json
from pathlib import Path
P = Path("/home/layman/.hermes/quantumedge_analysis")
sys.path.insert(0, str(P))
from indicators import compute_indicators, trend_score
from market_data import _make_exchange

def fetch(symbol, interval, limit=100):
    ex = _make_exchange()
    try:
        raw = ex.fetch_ohlcv(symbol, interval, limit=limit)
        rows = [{"timestamp": r[0], "open": float(r[1]), "high": float(r[2]),
                 "low": float(r[3]), "close": float(r[4]), "volume": float(r[5])} for r in raw]
        return rows
    finally:
        try: ex.close()
        except Exception: pass

def calc(symbol, interval):
    rows = fetch(symbol, interval)
    if len(rows) < 20:
        return {"interval": interval, "ok": False, "n": len(rows)}
    ind = compute_indicators(__import__("pandas").DataFrame(rows))
    sc = trend_score(ind)
    return {"interval": interval, "ok": True, "price": ind["price"],
            "rsi_14": round(ind["rsi_14"],2), "macd_line": round(ind["macd_line"],6),
            "macd_signal": round(ind["macd_signal"],6), "macd_hist": round(ind["macd_hist"],6),
            "bb_lower": round(ind["bb_lower"],5), "bb_mid": round(ind["bb_mid"],5),
            "bb_upper": round(ind["bb_upper"],5), "atr_14": round(ind["atr_14"],5),
            "atr_pct": ind["atr_pct"], "bias": sc["bias"], "score": sc["score"]}

out = {
    "XRP_1h": calc("XRP/USDT:USDT", "1h"),
    "XRP_5m": calc("XRP/USDT:USDT", "5m"),
    "BTC_1h": calc("BTC/USDT:USDT", "1h"),
}
print(json.dumps(out, indent=2))
