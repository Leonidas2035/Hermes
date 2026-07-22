"""
QuantumEdge Analysis — Market Data Collector
Збирає ВСІ дані для аналізу Супервізора напряму з біржі (BingX VST),
без залежності від QuestDB / MarketDataHub daemon.

Джерела:
  - ccxt.bingx (testnet/sandbox) — klines, funding, OI, ticker, order book
  - TradingView parse (tv_analyzer/tv_parse.js) — технічний рейтинг
  - Firecrawl (Free Tier) — новинний sentiment

Ключі беруться з .env (BINGX_TESTNET_API_KEY / SECRET) проєкту QuantumEdge.
"""
from __future__ import annotations
import os
import sys
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

# Шлях до проєкту QuantumEdge (для .env та tv_analyzer)
QE_ROOT = Path("/home/layman/.hermes/quantumedge_analysis")
sys.path.insert(0, str(QE_ROOT))

from dotenv import load_dotenv
load_dotenv(QE_ROOT / ".env")

import ccxt

SYMBOL = os.getenv("MARKET_DATA_SYMBOLS", "XRPUSDT").split(",")[0]
BASE = SYMBOL.replace("USDT", "")
CCXT_SYMBOL = f"{BASE}/USDT:USDT"
BTC_SYMBOL = "BTC/USDT:USDT"
USE_TESTNET = str(os.getenv("USE_TESTNET", "1")).lower() in {"1", "true", "t"}


def _make_exchange():
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    ex = ccxt.bingx({
        "apiKey": ak, "secret": sc,
        "options": {"defaultType": "swap"},
        "enableRateLimit": True, "timeout": 30000,
    })
    if USE_TESTNET:
        ex.set_sandbox_mode(True)
    return ex


# --------------------------------------------------------------------------
# 1. XRP OHLCV (для індикаторів) — напряму з біржі
# --------------------------------------------------------------------------
def fetch_xrp_klines(interval: str = "15m", limit: int = 100) -> dict:
    """
    Klines XRP/USDT з біржі. Повертає dict з DataFrame-сумісним записом
    + готовий pandas DataFrame (через to_dict) для indicators.compute_indicators.
    """
    ex = _make_exchange()
    try:
        raw = ex.fetch_ohlcv(CCXT_SYMBOL, interval, limit=limit)
        rows = []
        for r in raw:
            ts, o, h, l, c, v = r[0], r[1], r[2], r[3], r[4], r[5]
            rows.append({
                "timestamp": ts,
                "open": float(o), "high": float(h), "low": float(l),
                "close": float(c), "volume": float(v),
            })
        return {
            "ok": True,
            "interval": interval,
            "count": len(rows),
            "klines": rows,
            "first_ts": rows[0]["timestamp"] if rows else None,
            "last_ts": rows[-1]["timestamp"] if rows else None,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        try:
            ex.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# 2. Funding + Open Interest + Mark price
# --------------------------------------------------------------------------
def fetch_funding_oi() -> dict:
    ex = _make_exchange()
    out = {}
    try:
        fr = ex.fetch_funding_rate(CCXT_SYMBOL)
        out["funding_rate"] = fr.get("fundingRate")
        out["mark_price"] = fr.get("markPrice")
        out["index_price"] = fr.get("indexPrice")
    except Exception as e:
        out["funding_error"] = str(e)
    try:
        oi = ex.fetch_open_interest(CCXT_SYMBOL)
        out["open_interest_usd"] = oi.get("openInterestValue")
    except Exception as e:
        out["oi_error"] = str(e)
    try:
        ex.close()
    except Exception:
        pass
    return out


# --------------------------------------------------------------------------
# 3. Order book (мікроструктура) — стінки + imbalance
# --------------------------------------------------------------------------
def fetch_order_book(depth: int = 20) -> dict:
    ex = _make_exchange()
    try:
        ob = ex.fetch_order_book(CCXT_SYMBOL, limit=depth)
        bids = ob.get("bids", [])
        asks = ob.get("asks", [])
        bv = sum(b[1] for b in bids[:10])
        av = sum(a[1] for a in asks[:10])
        def walls(levels, n=5):
            s = sorted(levels, key=lambda x: x[1], reverse=True)[:n]
            return [[round(p, 4), round(v, 1)] for p, v in s]
        out = {
            "ok": True,
            "best_bid": bids[0][0] if bids else None,
            "best_ask": asks[0][0] if asks else None,
            "bid_vol10": round(bv, 1),
            "ask_vol10": round(av, 1),
            "imbalance": round((bv - av) / (bv + av), 3) if (bv + av) else 0,
            "bid_walls": walls(bids),
            "ask_walls": walls(asks),
        }
    except Exception as e:
        out = {"ok": False, "error": str(e)}
    try:
        ex.close()
    except Exception:
        pass
    return out


# --------------------------------------------------------------------------
# 4. BTC як провідний індикатор
# --------------------------------------------------------------------------
def fetch_btc_context() -> dict:
    ex = _make_exchange()
    out = {}
    try:
        tk = ex.fetch_ticker(BTC_SYMBOL)
        out["btc_last"] = tk.get("last")
        out["btc_change24"] = tk.get("percentage")
        fr = ex.fetch_funding_rate(BTC_SYMBOL)
        out["btc_funding"] = fr.get("fundingRate")
        oi = ex.fetch_open_interest(BTC_SYMBOL)
        out["btc_oi_usd"] = oi.get("openInterestValue")

        sol_tk = ex.fetch_ticker("SOL/USDT:USDT")
        sol_price = float(sol_tk.get("last") or 0)
        out["sol_last"] = sol_price
        out["sol_change24"] = sol_tk.get("percentage")

        xrp_tk = ex.fetch_ticker("XRP/USDT:USDT")
        xrp_price = float(xrp_tk.get("last") or 0)
        out["xrp_last"] = xrp_price
        out["xrp_change24"] = xrp_tk.get("percentage")

        btc_price = float(tk.get("last") or 0)
        if btc_price > 0:
            if sol_price > 0:
                out["btc_sol_ratio"] = round(btc_price / sol_price, 2)
            if xrp_price > 0:
                out["btc_xrp_ratio"] = round(btc_price / xrp_price, 2)
    except Exception as e:
        out["btc_error"] = str(e)
    try:
        ex.close()
    except Exception:
        pass
    return out


# --------------------------------------------------------------------------
# 5. TradingView технічний рейтинг (Puppeteer)
# --------------------------------------------------------------------------
def fetch_tv_rating(symbol: str = SYMBOL) -> dict:
    """
    Отримує технічний рейтинг з TradingView через безкоштовний публічний API сканера.
    Працює миттєво в Python, без запуску Puppeteer / Chrome.
    """
    import urllib.request
    import json
    
    tv_symbol = f"BYBIT:{symbol.upper()}"
    url = "https://scanner.tradingview.com/crypto/scan"
    payload = {
        "symbols": {
            "tickers": [tv_symbol],
            "query": { "types": [] }
        },
        "columns": [
            "Recommend.All",
            "Recommend.Other",
            "Recommend.MA",
            "close"
        ]
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
        rows = data.get("data", [])
        if not rows:
            return {"ok": False, "error": f"No scanner data returned for {tv_symbol}"}
            
        d = rows[0].get("d", [])
        if len(d) < 4:
            return {"ok": False, "error": "Incomplete scanner data columns"}
            
        rec_all, rec_other, rec_ma, price = d[0], d[1], d[2], d[3]
        
        def map_score(val):
            if val is None:
                return "Neutral"
            if val > 0.5:
                return "Strong Buy"
            elif val >= 0.1:
                return "Buy"
            elif val > -0.1:
                return "Neutral"
            elif val >= -0.5:
                return "Sell"
            else:
                return "Strong Sell"
                
        rating = map_score(rec_all)
        oscillators = map_score(rec_other)
        moving_averages = map_score(rec_ma)
        
        return {
            "ok": True,
            "symbol": symbol,
            "recommendation": rating,
            "priceText": str(price),
            "levels": [],
            "technicalsPage": {
                "rating": rating,
                "oscillators": oscillators,
                "movingAverages": moving_averages,
                "levels": []
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# --------------------------------------------------------------------------
# 6. Новинний sentiment (Google News RSS Feed - Безкоштовний аналог Firecrawl)
# --------------------------------------------------------------------------
def fetch_news(symbol: str = SYMBOL, limit: int = 3) -> dict:
    """
    Збирає новини за допомогою безкоштовного Google News RSS Feed.
    Обіймає ліміти та платні тарифи Firecrawl.
    """
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    import re
    
    coin_name = "Ripple" if "XRP" in symbol else ("Bitcoin" if "BTC" in symbol else symbol.replace("USDT", ""))
    query = f"{symbol.replace('USDT', '')} {coin_name} price news"
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read()
        
        root = ET.fromstring(xml_data)
        headlines = []
        for item in root.findall(".//item")[:limit]:
            title = item.find("title").text if item.find("title") is not None else ""
            desc = item.find("description").text if item.find("description") is not None else ""
            # Очищення HTML-тегів з опису
            desc = re.sub('<[^<]+?>', '', desc) if desc else ""
            headlines.append({"title": title, "desc": desc[:160]})
            
        blob = " ".join((h["title"] or "") + " " + (h["desc"] or "") for h in headlines).lower()
        bull = sum(blob.count(w) for w in ["surge", "rise", "gain", "bull", "up", "momentum", "breakout"])
        bear = sum(blob.count(w) for w in ["drop", "fall", "bear", "down", "crash", "sell", "loss"])
        if bull > bear:
            sentiment = "BULLISH"
        elif bear > bull:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"
            
        return {"ok": True, "headlines": headlines, "sentiment": sentiment, "bull": bull, "bear": bear}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def trading_session() -> str:
    h = datetime.now(timezone.utc).hour
    if 13 <= h < 21:
        return "US"
    if 7 <= h < 13:
        return "EU"
    if 0 <= h < 7 or h >= 22:
        return "ASIA"
    return "EU_US_OVERLAP"


if __name__ == "__main__":
    # Smoke test (без TV/новин, щоб не ганяти node/firecrawl)
    print("SESSION:", trading_session())
    print("KLINES:", json.dumps(fetch_xrp_klines("15m", 5), default=str)[:400])
    print("FUNDING/OI:", json.dumps(fetch_funding_oi(), default=str))
    print("BOOK:", json.dumps(fetch_order_book(10), default=str)[:400])
    print("BTC:", json.dumps(fetch_btc_context(), default=str)[:400])
