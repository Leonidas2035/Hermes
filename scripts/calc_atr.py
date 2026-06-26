#!/home/korben/QuantumEdge-main/.venv/bin/python3
import os, sys, json, math
import ccxt

SYMBOL = "BTC/USDT:USDT"

def make_ex():
    return ccxt.bingx({
        "apiKey": os.getenv("BINGX_DEMO_API_KEY", ""),
        "secret": os.getenv("BINGX_DEMO_API_SECRET", ""),
        "options": {"defaultType": "swap", "adjustForTimeDifference": True, "createMarketBuyOrderRequiresPrice": False},
        "enableRateLimit": True,
    })

def calc_atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        high = candles[i][2]
        low = candles[i][3]
        prev_close = candles[i-1][4]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs[:period]) / period

def main():
    ex = make_ex()
    candles = ex.fetch_ohlcv(SYMBOL, timeframe="1h", limit=50)
    atr = calc_atr(candles, 14)
    result = {"atr": atr if atr is not None else "N/A"}
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
