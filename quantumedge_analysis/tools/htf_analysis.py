import asyncio
import pandas as pd
import ccxt.async_support as ccxt
import pandas_ta as ta

async def main():
    ex = ccxt.bingx({'options': {'defaultType': 'swap'}})
    await ex.load_markets()
    
    symbol = "BTC/USDT:USDT"
    
    for tf in ["4h", "1d", "1w"]:
        try:
            ohlcv = await ex.fetch_ohlcv(symbol, timeframe=tf, limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['RSI'] = ta.rsi(df['close'], length=14)
            macd = ta.macd(df['close'])
            if macd is not None:
                df = pd.concat([df, macd], axis=1)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            print(f"\n--- TIMEFRAME: {tf.upper()} ---")
            print(f"Close: {latest['close']}")
            print(f"RSI: {latest['RSI']:.2f} (Prev: {prev['RSI']:.2f})")
            
            macd_val = latest.get('MACD_12_26_9', 0)
            macd_hist = latest.get('MACDh_12_26_9', 0)
            print(f"MACD Hist: {macd_hist:.2f}")
            
            # Basic analysis
            if latest['RSI'] > 70:
                print("RSI Status: OVERBOUGHT (Caution, potential reversal)")
            elif latest['RSI'] < 30:
                print("RSI Status: OVERSOLD")
            else:
                print("RSI Status: NEUTRAL/BULLISH" if latest['RSI'] > 50 else "RSI Status: NEUTRAL/BEARISH")
                
            if macd_hist > 0:
                print("MACD Status: BULLISH MOMENTUM")
            else:
                print("MACD Status: BEARISH MOMENTUM")
                
        except Exception as e:
            print(f"Error on {tf}: {e}")
            
    await ex.close()

if __name__ == "__main__":
    asyncio.run(main())
