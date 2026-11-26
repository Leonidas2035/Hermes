import os
import sys
import asyncio
from dotenv import load_dotenv
import ccxt.async_support as ccxt

# Setup path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

SYMBOL = "SOL/USDT:USDT"
LEVERAGE = 50
MARGIN_ALLOCATION = 5000  # Збільшена маржа: 5,000 VST
TARGET_ROI_PCT = 30.0     # Тейк-Профіт: +30% ROI
STOP_LOSS_ROI_PCT = 15.0  # Стоп-Лос: -15% ROI (жорсткий контроль ризику)

async def execute_swing(bias: str):
    ak = os.getenv("BINGX_TESTNET_API_KEY") or os.getenv("BINGX_API_KEY", "")
    sc = os.getenv("BINGX_TESTNET_SECRET") or os.getenv("BINGX_SECRET", "")
    use_testnet = str(os.getenv("USE_TESTNET", "1")).lower() in {"1", "true", "t"}
    
    ex = ccxt.bingx({"apiKey": ak, "secret": sc, "options": {"defaultType": "swap"}})
    if use_testnet: ex.set_sandbox_mode(True)
    await ex.load_markets()
    
    ticker = await ex.fetch_ticker(SYMBOL)
    current_price = ticker['last']
    
    # Розрахунок розміру позиції (збільшена маржа * плече)
    position_usd = MARGIN_ALLOCATION * LEVERAGE
    amount = position_usd / current_price
    
    # Розрахунок цін TP та SL на основі заданого ROI
    target_move = TARGET_ROI_PCT / 100.0 / LEVERAGE
    sl_move = STOP_LOSS_ROI_PCT / 100.0 / LEVERAGE
    
    if bias.upper() == "LONG":
        side = "buy"
        pos_side = "LONG"
        tp_price = current_price * (1 + target_move)
        sl_price = current_price * (1 - sl_move)
    else:
        side = "sell"
        pos_side = "SHORT"
        tp_price = current_price * (1 - target_move)
        sl_price = current_price * (1 + sl_move)
        
    print("==================================================")
    print(f"🔥 AGGRESSIVE SWING TRADER | {SYMBOL} | {pos_side}")
    print(f"Margin: {MARGIN_ALLOCATION} VST | Lev: {LEVERAGE}x | Size: {amount:.2f} SOL")
    print(f"Entry: {current_price:.3f} | TP: {tp_price:.3f} (+{TARGET_ROI_PCT}%) | SL: {sl_price:.3f} (-{STOP_LOSS_ROI_PCT}%)")
    print("==================================================")
    
    try:
        # 1. Відкриття позиції (Market Order)
        order = await ex.create_order(
            symbol=SYMBOL, type="market", side=side, amount=amount,
            params={"positionSide": pos_side}
        )
        print(f"✅ Позицію відкрито! Order ID: {order.get('id')}")
        
        # 2. Виставлення Take Profit (Limit Order)
        tp_side = "sell" if pos_side == "LONG" else "buy"
        await ex.create_order(
            symbol=SYMBOL, type="limit", side=tp_side, amount=amount, price=round(tp_price, 3),
            params={"positionSide": pos_side}
        )
        print(f"✅ Take Profit успішно виставлено на {tp_price:.3f}")
        
        # 3. Виставлення Stop Loss (STOP_MARKET Order)
        await ex.create_order(
            symbol=SYMBOL, type="STOP_MARKET", side=tp_side, amount=amount,
            params={"positionSide": pos_side, "triggerPrice": round(sl_price, 3)}
        )
        print(f"✅ Stop Loss успішно виставлено на {sl_price:.3f}")
        
    except Exception as e:
        print(f"❌ Помилка виконання: {e}")
        
    await ex.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        bias = sys.argv[1]
        asyncio.run(execute_swing(bias))
    else:
        print("Використання: python3 sol_swing_trader.py [LONG|SHORT]")
