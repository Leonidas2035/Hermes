#!/home/korben/QuantumEdge-main/.venv/bin/python3
"""QE manual monitor: fetches data via BingX VST (demo) API directly."""
import os, sys, json, math, datetime, hmac, hashlib, urllib.parse, urllib.request

SYMBOL = "BTC-USDT"  # BingX internal symbol format for swap
BASE_URL = "https://open-api-vst.bingx.com"  # VST demo endpoint

def api_get(path, params):
    params = dict(params)
    params["timestamp"] = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    sorted_items = sorted(params.items())
    query = urllib.parse.urlencode(sorted_items)
    signature = hmac.new(
        os.environ.get("BINGX_DEMO_API_SECRET", "").encode(),
        query.encode(),
        hashlib.sha256,
    ).hexdigest()
    url = f"{BASE_URL}{path}?{query}&signature={signature}"
    headers = {"X-BX-APIKEY": os.environ.get("BINGX_DEMO_API_KEY", "")}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(str(e))

def fetch_positions():
    data = api_get("/openApi/swap/v2/user/positions", {})
    positions = []
    for p in data.get("data", []):
        amt = float(p.get("positionAmt", 0))
        if amt == 0:
            continue
        positions.append({
            "id": p.get("positionId"),
            "symbol": p.get("symbol"),
            "side": p.get("positionSide", "").lower(),
            "contracts": amt,
            "entry": float(p.get("avgPrice", 0)),
            "mark": float(p.get("markPrice", 0)),
            "unrealized_pnl": float(p.get("unrealizedProfit", 0)),
            "realized_pnl": float(p.get("realisedProfit", 0)),
            "leverage": float(p.get("leverage", 0)),
            "liquidation": float(p.get("liquidationPrice", 0)),
            "pnl_ratio": float(p.get("pnlRatio", 0)),
            "risk_rate": float(p.get("riskRate", 0)),
            "margin": float(p.get("initialMargin", 0)),
            "position_value": float(p.get("positionValue", 0)),
        })
    return positions

def fetch_balance():
    data = api_get("/openApi/swap/v2/user/balance", {})
    balance_info = data.get("data", {})
    if isinstance(balance_info, dict):
        balance_info = balance_info.get("balance", {})
    usdt = 0.0
    if isinstance(balance_info, dict):
        # VST demo account uses VST currency
        usdt = float(balance_info.get("availableMargin", 0))
    elif isinstance(balance_info, list):
        for item in balance_info:
            if item.get("asset") in ("USDT", "VST"):
                usdt = float(item.get("availableMargin", 0))
                break
    return usdt

def fetch_ohlcv():
    params = {"symbol": SYMBOL, "interval": "1h", "limit": 50}
    data = api_get("/openApi/swap/v3/quote/klines", params)
    candles = []
    raw = data.get("data", [])
    if not raw:
        return candles
    first = raw[0]
    if isinstance(first, dict):
        for c in raw:
            candles.append({
                "time": c.get("time", c.get(0)),
                "open": float(c.get("open", c.get(1, 0))),
                "high": float(c.get("high", c.get(2, 0))),
                "low": float(c.get("low", c.get(3, 0))),
                "close": float(c.get("close", c.get(4, 0))),
                "volume": float(c.get("volume", c.get(5, 0))),
            })
    else:
        for c in raw:
            candles.append({
                "time": c[0],
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })
    return candles

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    for i in range(period, len(deltas)):
        gain = gains[i]
        loss = losses[i]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
    return rsi

def calc_bollinger(closes, period=20, mult=2):
    if len(closes) < period:
        return None, None, None
    window = closes[-period:]
    mid = sum(window) / period
    std = math.sqrt(sum((c - mid) ** 2 for c in window) / period)
    return mid - mult * std, mid, mid + mult * std

def pct(a, b):
    try:
        return (a - b) / b * 100
    except Exception:
        return 0.0

def main():
    out = {"time_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "alerts": []}
    try:
        positions = fetch_positions()
        balance = fetch_balance()
        longs = [p for p in positions if p["side"] == "long"]
        shorts = [p for p in positions if p["side"] == "short"]

        candles = fetch_ohlcv()
        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        last = closes[-1] if closes else 0
        rsi = calc_rsi(closes, 14)
        bb_lower, bb_mid, bb_upper = calc_bollinger(closes, 20, 2)

        net = sum(p["contracts"] * (1 if p["side"] == "long" else -1) for p in positions)

        # Determine action
        action = "Чекати"
        for p in shorts:
            pnl = -pct(p["mark"], p["entry"])
            if pnl > 0.5:
                action = "Частковий тейк 30% шорту"
                break
            elif pnl < -8:
                action = "Хеджувати шорт"
                break
        for p in longs:
            pnl = pct(p["mark"], p["entry"])
            if pnl > 0.5:
                action = "Частковий тейк 30% лонгу"
                break
            elif pnl < -8:
                action = "Хеджувати лонг"
                break

        # Trend
        trend = "NEUTRAL"
        if rsi is not None:
            if rsi < 30 and last < (bb_lower or 0):
                trend = "BEARISH"
            elif rsi > 70 and last > (bb_upper or float('inf')):
                trend = "BULLISH"
            elif rsi < 45:
                trend = "BEARISH_SOFT"
            elif rsi > 55:
                trend = "BULLISH_SOFT"

        # Market mode
        width = (bb_upper - bb_lower) if (bb_upper is not None and bb_lower is not None) else 0
        pos_in_band = (last - bb_lower) / width if width else 0.5
        market_mode = "RANGE" if (0.35 < pos_in_band < 0.65 and (rsi is None or 40 < rsi < 60)) else "TREND"

        # Volatility
        vol = "CALM"
        atr_str = "N/A"
        if len(closes) >= 15:
            trs = []
            for i in range(1, len(closes)):
                h = highs[i]
                l = lows[i]
                prev_c = closes[i-1]
                tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
                trs.append(tr)
            atr = sum(trs[:14]) / 14
            atr_str = f"{atr:.1f}"
            atr_pct = (atr / last * 100) if last else 0
            if atr_pct > 2.5:
                vol = "HIGH_VOL"
            elif atr_pct > 1.5:
                vol = "CHOPPY"

        lines = []
        lines.append(f"Режим: {market_mode} | breakout: false")
        lines.append(f"Дія: {action}")
        lines.append("")
        lines.append("Позиції:")

        for p in longs:
            pnl = pct(p["mark"], p["entry"])
            lines.append(f"• LONG: {p['contracts']:.4f} BTC @ {p['entry']:,.1f}, PnL: {pnl:+.2f}%")
        if not longs:
            lines.append("• LONG: 0")

        for p in shorts:
            pnl = -pct(p["mark"], p["entry"])
            lines.append(f"• SHORT: {p['contracts']:.4f} BTC @ {p['entry']:,.1f}, PnL: {pnl:+.2f}%")
        if not shorts:
            lines.append("• SHORT: 0")

        lines.append(f"• Net BTC: {net:+.4f}")
        lines.append("")
        lines.append(f"RSI: {rsi:.2f} | ATR: {atr_str}")
        lines.append(f"Волатильність: {vol} | Тренд: {trend}")
        lines.append("")
        lines.append("Orderbook walls: bid=0, ask=0")
        lines.append(f"Ордерів: 0/20")
        lines.append("")
        lines.append(f"Баланс: {balance:,.1f} USDT")

        out["report"] = "\n".join(lines)
    except Exception as e:
        out["report"] = f"Error: {e}"

    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
