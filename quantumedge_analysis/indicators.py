"""
QuantumEdge Analysis — Technical Indicators
Витягнуто з QuantumEdge/monitor_adjust.py (BTC-пайплайн) і адаптовано
під XRP/USDT. Тепер підключено до аналізу Супервізора (не висяче у старому коді).

Залежності: pandas, numpy, ta (Technical Analysis library).
Всі функції приймають DataFrame з колонками:
    timestamp, open, high, low, close, volume
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import ta


def compute_indicators(df: pd.DataFrame) -> dict:
    """
    Обчислює RSI(14), MACD(line/signal/hist), Bollinger Bands(20,2), ATR(14).
    Повертає dict з float-значеннями + похідні сигнали.
    """
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # --- RSI(14) ---
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]

    # --- MACD(12,26,9) ---
    macd = ta.trend.MACD(close)
    macd_line = macd.macd().iloc[-1]
    macd_signal = macd.macd_signal().iloc[-1]
    macd_hist = macd.macd_diff().iloc[-1]

    # --- Bollinger Bands(20, 2σ) ---
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    bb_lower = bb.bollinger_lband().iloc[-1]
    bb_mid = bb.bollinger_mavg().iloc[-1]
    bb_upper = bb.bollinger_hband().iloc[-1]

    # --- ATR(14) ---
    atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range().iloc[-1]

    price = float(close.iloc[-1])

    # --- Похідні сигнали ---
    # BB position: 0 = нижня, 0.5 = середня, 1 = верхня
    bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid else 0.0
    if bb_upper != bb_lower:
        bb_pos = (price - bb_lower) / (bb_upper - bb_lower)
    else:
        bb_pos = 0.5

    # RSI zone
    if rsi >= 70:
        rsi_zone = "OVERBOUGHT"
    elif rsi <= 30:
        rsi_zone = "OVERSOLD"
    elif rsi >= 55:
        rsi_zone = "BULLISH"
    elif rsi <= 45:
        rsi_zone = "BEARISH"
    else:
        rsi_zone = "NEUTRAL"

    # MACD cross state
    if macd_line > macd_signal:
        macd_state = "BULLISH"  # бичачий кросовер / вище сигналу
    else:
        macd_state = "BEARISH"

    # ATR як % від ціни (волатільність)
    atr_pct = (atr / price * 100) if price else 0.0

    return {
        "price": round(price, 6),
        "rsi_14": round(float(rsi), 2),
        "rsi_zone": rsi_zone,
        "macd_line": round(float(macd_line), 6),
        "macd_signal": round(float(macd_signal), 6),
        "macd_hist": round(float(macd_hist), 6),
        "macd_state": macd_state,
        "bb_lower": round(float(bb_lower), 6),
        "bb_mid": round(float(bb_mid), 6),
        "bb_upper": round(float(bb_upper), 6),
        "bb_width_pct": round(float(bb_width * 100), 3),
        "bb_position": round(float(bb_pos), 3),
        "atr_14": round(float(atr), 6),
        "atr_pct": round(float(atr_pct), 3),
    }


def trend_score(ind: dict) -> dict:
    """
    Перетворює індикатори на числовий bias-score (-3 .. +3).
    + = бичаче, - = ведмедяче. Для якісного аналізу Супервізора.
    """
    bull = 0
    bear = 0

    # RSI
    if ind["rsi_14"] > 55:
        bull += 1
    elif ind["rsi_14"] < 45:
        bear += 1

    # MACD
    if ind["macd_line"] > ind["macd_signal"]:
        bull += 1
    else:
        bear += 1

    # Ціна відн. BB
    if ind["price"] > ind["bb_mid"]:
        bull += 1
    else:
        bear += 1
    if ind["price"] >= ind["bb_upper"]:
        bull += 1
    elif ind["price"] <= ind["bb_lower"]:
        bear += 1

    score = bull - bear  # -3..+3
    if score >= 2:
        bias = "LONG"
    elif score <= -2:
        bias = "SHORT"
    else:
        bias = "NEUTRAL"

    return {
        "bullish_points": bull,
        "bearish_points": bear,
        "score": score,
        "bias": bias,
    }


if __name__ == "__main__":
    import json
    # Smoke test: генеруємо фейковий DF і друкуємо
    import numpy as np
    n = 100
    np.random.seed(1)
    closes = np.cumsum(np.random.randn(n)) + 100
    df = pd.DataFrame({
        "timestamp": range(n),
        "open": closes,
        "high": closes + 1,
        "low": closes - 1,
        "close": closes,
        "volume": np.random.rand(n) * 1000,
    })
    ind = compute_indicators(df)
    print(json.dumps(ind, indent=2))
    print(json.dumps(trend_score(ind), indent=2))
