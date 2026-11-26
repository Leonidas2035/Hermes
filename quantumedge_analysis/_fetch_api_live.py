import asyncio, os, json
from dotenv import load_dotenv

env_path = os.path.join('/home/layman/.hermes/quantumedge_analysis', '.env')
load_dotenv(env_path)

import ccxt.async_support as ccxt

async def main():
    ak = os.getenv('BINGX_TESTNET_API_KEY') or os.getenv('BINGX_API_KEY', '')
    sc = os.getenv('BINGX_TESTNET_SECRET') or os.getenv('BINGX_SECRET', '')
    use_testnet = str(os.getenv('USE_TESTNET', '1')).lower() in {'1', 'true', 't'}

    print(f"=== 🔗 ПРЕДКЛЮЧЕННЯ ДО BINGX API ({'TESTNET VST' if use_testnet else 'REAL'}) ===")
    ex = ccxt.bingx({
        'apiKey': ak,
        'secret': sc,
        'options': {'defaultType': 'swap'},
        'enableRateLimit': True
    })
    if use_testnet: ex.set_sandbox_mode(True)
    await ex.load_markets()

    symbols = ['BTC/USDT:USDT', 'XRP/USDT:USDT', 'SOL/USDT:USDT', 'ETH/USDT:USDT']

    print("\n--- 📈 АКТУАЛЬНІ ЦІНИ СТАКАНУ ТА ТІКЕРИ ---")
    for s in symbols:
        try:
            t = await ex.fetch_ticker(s)
            base = s.split(':')[0]
            last_price = t.get('last') or t.get('close') or 0
            bid_price = t.get('bid') or 0
            ask_price = t.get('ask') or 0
            chg = t.get('percentage') or 0
            print(f"• {base:<12} | Ціна: ${last_price:<10.4f} | Bid: ${bid_price:<10.4f} | Ask: ${ask_price:<10.4f} | 24h: {chg:+.2f}%")
        except Exception as e:
            print(f"• {s}: {e}")

    bal = await ex.fetch_balance()
    curr = 'VST' if use_testnet else 'USDT'
    q = bal.get(curr, {})
    total_bal = float(q.get('total') or 0)
    free_bal = float(q.get('free') or 0)
    used_bal = float(q.get('used') or 0)

    print(f"\n--- 💰 БАЛАНС АКАУНТУ ({curr}) ---")
    print(f"• Загальний баланс (Total Equity): {total_bal:,.2f} {curr}")
    print(f"• Вільна маржа (Free Balance):   {free_bal:,.2f} {curr} ({(free_bal/total_bal*100 if total_bal else 0):.1f}%)")
    print(f"• Задіяна маржа (Used Margin):   {used_bal:,.2f} {curr} ({(used_bal/total_bal*100 if total_bal else 0):.1f}%)")

    positions = await ex.fetch_positions(symbols)
    active_positions = [p for p in positions if float(p.get('contracts') or 0) > 0]

    print(f"\n--- 📊 ВІДКРИТІ ПОЗИЦІЇ ({len(active_positions)}) ---")
    if active_positions:
        for p in active_positions:
            info = p.get('info', {})
            sym = (p.get('symbol') or '').split(':')[0]
            side = str(p.get('side') or info.get('positionSide') or '').upper()
            contracts = float(p.get('contracts') or info.get('positionAmt') or 0)
            entry = float(p.get('entryPrice') or info.get('avgPrice') or info.get('entryPrice') or 0)
            mark = float(p.get('markPrice') or info.get('markPrice') or 0)
            upnl = float(p.get('unrealizedPnl') or info.get('unrealizedProfit') or 0)
            lev = float(p.get('leverage') or info.get('leverage') or 1)
            margin = (entry * contracts) / lev if lev > 0 else 0
            roi = (upnl / margin * 100) if margin > 0 else 0

            pnl_sign = f"+${upnl:,.2f}" if upnl >= 0 else f"-${abs(upnl):,.2f}"
            print(f"• {sym:<10} | Side: {side:<5} ({lev:.0f}x) | Об'єм: {contracts:,.2f} | Entry: ${entry:,.4f} | Mark: ${mark:,.4f} | uPnL: {pnl_sign} VST | ROI: {roi:+.2f}%")
    else:
        print("Відкритих позицій немає.")

    print("\n--- 🎯 АКТИВНІ ОРДЕРИ В СТАКАНІ ---")
    total_orders = 0
    for s in symbols:
        try:
            oo = await ex.fetch_open_orders(s)
            if oo:
                total_orders += len(oo)
                base = s.split(':')[0]
                print(f"• {base} ({len(oo)} ордерів):")
                for o in oo:
                    side = str(o.get('side')).upper()
                    price = float(o.get('price') or 0)
                    amount = float(o.get('amount') or 0)
                    o_type = str(o.get('type')).upper()
                    print(f"   └─ {side:<4} {amount:,.2f} @ ${price:,.4f} ({o_type})")
        except Exception as e:
            print(f"Error fetching orders for {s}: {e}")

    if total_orders == 0:
        print("Активних ордерів у стакані немає.")

    await ex.close()

if __name__ == "__main__":
    asyncio.run(main())
