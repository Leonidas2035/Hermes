import yfinance as yf
import json
import os
from datetime import datetime
import pytz

def fetch_macro_data():
    """Fetches macro data using yfinance (SPY, QQQ, DXY, VIX, US10Y)"""
    tickers = {
        "SP500": "^GSPC",
        "NASDAQ": "^NDX",
        "DXY": "DX-Y.NYB",
        "VIX": "^VIX",
        "US10Y": "^TNX"
    }
    
    macro_state = {
        "timestamp_utc": datetime.now(pytz.utc).isoformat(),
        "data": {},
        "sentiment": "NEUTRAL",
        "risk_appetite": "MODERATE"
    }
    
    try:
        # Fetching data for all tickers
        for name, symbol in tickers.items():
            ticker = yf.Ticker(symbol)
            # Use '1d' history to get the latest close/current price
            hist = ticker.history(period="5d")
            
            if len(hist) >= 2:
                current_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                change_pct = ((current_price - prev_price) / prev_price) * 100
                
                macro_state["data"][name] = {
                    "price": round(current_price, 2),
                    "change_pct": round(change_pct, 2)
                }
            else:
                macro_state["data"][name] = {"error": "Insufficient data"}
                
        # Determine Sentiment and Risk Appetite based on DXY and VIX
        dxy = macro_state["data"].get("DXY", {})
        vix = macro_state["data"].get("VIX", {})
        sp500 = macro_state["data"].get("SP500", {})
        
        # Risk appetite logic
        if vix.get("price", 0) > 20.0 or dxy.get("change_pct", 0) > 0.5:
            macro_state["risk_appetite"] = "LOW (RISK-OFF)"
            macro_state["sentiment"] = "BEARISH"
        elif sp500.get("change_pct", 0) > 0.5 and vix.get("price", 0) < 18.0:
            macro_state["risk_appetite"] = "HIGH (RISK-ON)"
            macro_state["sentiment"] = "BULLISH"
            
    except Exception as e:
        macro_state["error"] = str(e)
        
    return macro_state

if __name__ == "__main__":
    print("Fetching Macro Data V2...")
    data = fetch_macro_data()
    
    save_path = os.path.join(os.path.dirname(__file__), "macro_state.json")
    with open(save_path, "w") as f:
        json.dump(data, f, indent=4)
        
    print("Macro Data saved to macro_state.json:")
    print(json.dumps(data, indent=2))
