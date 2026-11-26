"""
QuantumEdge Analysis — Technical Indicators (Advanced HFT Engine)
Включено: RSI(14), MACD(12,26,9), Bollinger Bands(20,2), ATR(14),
          VWAP (Intraday Volume-Weighted Average Price),
          StochRSI (Stochastic RSI for micro-scalping),
          EMA 20 Slope (Momentum vector).
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import ta


def compute_indicators(df: pd.DataFrame) -> dict:
    """
    Обчислює RSI, MACD, BB, ATR, VWAP, StochRSI та EMA20 Slope.
    Повертає dict з float-значеннями + похідні сигнали.
    """
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    # --- 1. RSI(14) ---
    rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()
    rsi = float(rsi_series.iloc[-1])

    # --- 2. MACD(12,26,9) ---
    macd = ta.trend.MACD(close)
    macd_line = float(macd.macd().iloc[-1])
    macd_signal = float(macd.macd_signal().iloc[-1])
    macd_hist = float(macd.macd_diff().iloc[-1])

    # --- 3. Bollinger Bands(20, 2σ) ---
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    bb_lower = float(bb.bollinger_lband().iloc[-1])
    bb_mid = float(bb.bollinger_mavg().iloc[-1])
    bb_upper = float(bb.bollinger_hband().iloc[-1])

    # --- 4. ATR(14) ---
    atr = float(ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range().iloc[-1])

    price = float(close.iloc[-1])

    # --- 5. VWAP (Intraday) ---
    # Розрахунок VWAP відносно останніх N свічок або дня
    tp = (high + low + close) / 3.0
    vp = tp * volume
    cum_vp = vp.rolling(window=min(len(df), 96)).sum() # 96 свічок по 15м = 24 години
    cum_vol = volume.rolling(window=min(len(df), 96)).sum()
    vwap_series = cum_vp / cum_vol
    vwap = float(vwap_series.iloc[-1]) if not cum_vol.empty and cum_vol.iloc[-1] > 0 else price
    vwap_dist_pct = ((price - vwap) / vwap * 100.0) if vwap else 0.0

    # --- 6. StochRSI (14, 14) ---
    rsi_min = rsi_series.rolling(window=14).min()
    rsi_max = rsi_series.rolling(window=14).max()
    rsi_diff = rsi_max - rsi_min
    stoch_rsi_series = np.where(rsi_diff > 0, (rsi_series - rsi_min) / rsi_diff * 100.0, 50.0)
    stoch_rsi = float(stoch_rsi_series[-1])

    # --- 7. EMA 20 Slope (Momentum Vector) ---
    ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    ema20_now = float(ema20.iloc[-1])
    ema20_prev = float(ema20.iloc[-3]) if len(ema20) >= 3 else ema20_now
    ema20_slope_pct = ((ema20_now - ema20_prev) / ema20_prev * 100.0) if ema20_prev else 0.0

    # --- 8. Trading Range (Donchian Channels N=20) ---
    donchian_h = high.rolling(window=20).max()
    donchian_l = low.rolling(window=20).min()
    donchian_m = (donchian_h + donchian_l) / 2.0
    
    tr_res = float(donchian_h.iloc[-1]) if not donchian_h.empty else price
    tr_sup = float(donchian_l.iloc[-1]) if not donchian_l.empty else price
    tr_mid = float(donchian_m.iloc[-1]) if not donchian_m.empty else price

    # --- Похідні сигнали ---
    bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid else 0.0
    bb_pos = (price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5

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

    # StochRSI zone
    if stoch_rsi >= 80:
        stoch_zone = "OVERBOUGHT_PEAK"
    elif stoch_rsi <= 20:
        stoch_zone = "OVERSOLD_BOTTOM"
    else:
        stoch_zone = "NEUTRAL"

    # VWAP Bias
    if vwap_dist_pct > 0.3:
        vwap_bias = "ABOVE_VWAP (ABOVE_FAIR_PRICE)"
    elif vwap_dist_pct < -0.3:
        vwap_bias = "BELOW_VWAP (UNDERVALUED_LONG_ZONE)"
    else:
        vwap_bias = "AT_VWAP (FAIR_PRICE)"

    # MACD state
    macd_state = "BULLISH" if macd_line > macd_signal else "BEARISH"

    # ATR %
    atr_pct = (atr / price * 100) if price else 0.0

    return {
        "price": round(price, 6),
        "vwap": round(vwap, 6),
        "vwap_dist_pct": round(vwap_dist_pct, 2),
        "vwap_bias": vwap_bias,
        "rsi_14": round(rsi, 2),
        "rsi_zone": rsi_zone,
        "stoch_rsi": round(stoch_rsi, 2),
        "stoch_zone": stoch_zone,
        "ema20_slope_pct": round(ema20_slope_pct, 4),
        "macd_line": round(macd_line, 6),
        "macd_signal": round(macd_signal, 6),
        "macd_hist": round(macd_hist, 6),
        "macd_state": macd_state,
        "bb_lower": round(bb_lower, 6),
        "bb_mid": round(bb_mid, 6),
        "bb_upper": round(bb_upper, 6),
        "bb_width_pct": round(bb_width * 100, 3),
        "bb_position": round(bb_pos, 3),
        "atr_14": round(atr, 6),
        "atr_pct": round(atr_pct, 3),
        "tr_resistance": round(tr_res, 6),
        "tr_support": round(tr_sup, 6),
        "tr_mid": round(tr_mid, 6),
    }


def trend_score(ind: dict) -> dict:
    """
    Перетворює розширені індикатори на числовий bias-score (-4 .. +4).
    """
    bull = 0
    bear = 0

    # 1. RSI & StochRSI
    if ind["rsi_14"] > 55:
        bull += 1
    elif ind["rsi_14"] < 45:
        bear += 1

    if ind["stoch_rsi"] < 30: # Скальп лонг від дна
        bull += 1
    elif ind["stoch_rsi"] > 70: # Скальп шорт від піку
        bear += 1

    # 2. VWAP
    if ind["vwap_dist_pct"] < -0.1: # Ціна нижче VWAP = вигідно купувати
        bull += 1
    elif ind["vwap_dist_pct"] > 0.1:
        bear += 1

    # 3. MACD
    if ind["macd_line"] > ind["macd_signal"]:
        bull += 1
    else:
        bear += 1

    # 4. EMA20 Slope
    if ind["ema20_slope_pct"] > 0.02:
        bull += 1
    elif ind["ema20_slope_pct"] < -0.02:
        bear += 1

    score = bull - bear
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
