import asyncio, os, json
from dotenv import load_dotenv

env_path = os.path.join('/home/layman/.hermes/quantumedge_analysis', '.env')
load_dotenv(env_path)

import ccxt.async_support as ccxt

async def main():
    ak = os.getenv('BINGX_TESTNET_API_KEY') or os.getenv('BINGX_API_KEY', '')
    sc = os.getenv('BINGX_TESTNET_SECRET') or os.getenv('BINGX_SECRET', '')
    use_testnet = str(os.getenv('USE_TESTNET', '1')).lower() in {'1', 'true', 't'}

    ex = ccxt.bingx({
        'apiKey': ak, 'secret': sc,
        'options': {'defaultType': 'swap'},
        'enableRateLimit': True
    })
    if use_testnet: ex.set_sandbox_mode(True)
    await ex.load_markets()

    symbol = 'ETH/USDT:USDT'
    
    # 1. Fetch Open Orders for ETH
    orders = await ex.fetch_open_orders(symbol)
    
    # 2. Fetch Position
    positions = await ex.fetch_positions([symbol])
    eth_pos = [p for p in positions if float(p.get('contracts', 0) or 0) > 0]
    
    # 3. Fetch Real-time Orderbook
    ob = await ex.fetch_order_book(symbol, limit=50)
    bids = ob.get('bids', [])
    asks = ob.get('asks', [])
    
    top_bids = sorted(bids, key=lambda x: x[1], reverse=True)[:5]
    top_asks = sorted(asks, key=lambda x: x[1], reverse=True)[:5]

    print('=== LIVE ETH ANALYSIS ===')
    print('Open Orders:', [{'id': o['id'], 'side': o['side'], 'price': o['price'], 'amount': o['amount']} for o in orders])
    print('Active Position:', [{'amt': p.get('contracts'), 'entry': p.get('entryPrice'), 'mark': p.get('markPrice')} for p in eth_pos])
    print('\nTop Orderbook Bid Walls (Support):')
    for b in top_bids:
        val = b[0]*b[1]
        print(f'  Price: ${b[0]} | Vol: {b[1]:.2f} ETH (${val:,.2f} USD)')
        
    print('\nTop Orderbook Ask Walls (Resistance):')
    for a in top_asks:
        val = a[0]*a[1]
        print(f'  Price: ${a[0]} | Vol: {a[1]:.2f} ETH (${val:,.2f} USD)')

    await ex.close()

asyncio.run(main())
