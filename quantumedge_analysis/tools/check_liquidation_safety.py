import asyncio, os, json
from dotenv import load_dotenv

env_path = os.path.join('/home/layman/.hermes/quantumedge_analysis', '.env')
load_dotenv(env_path)

import ccxt.async_support as ccxt

async def check_and_guard(auto_close=False):
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

    positions = await ex.fetch_positions()
    active = [p for p in positions if float(p.get('contracts', 0) or 0) > 0]
    
    report = []
    close_triggered = False

    for p in active:
        info = p.get('info', {})
        symbol = p.get('symbol')
        side = info.get('positionSide', 'LONG')
        amt = float(info.get('positionAmt', 0))
        entry = float(info.get('avgPrice', 0))
        mark = float(info.get('markPrice', 0))
        liq = float(info.get('liquidationPrice', 0) or 0)
        risk_rate = float(info.get('riskRate', 0))
        upnl = float(info.get('unrealizedProfit', 0))

        dist_val = mark - liq if liq > 0 else 0
        dist_pct = (dist_val / mark) * 100.0 if mark > 0 and liq > 0 else 0

        # Safety Check: If Risk Rate > 80% or BTC within 1.5% ($62,400) of Liquidation $61,541
        threshold_approaching = False
        if symbol.startswith('BTC') and liq > 0 and mark <= liq * 1.015: # 1.5% buffer
            threshold_approaching = True
        elif risk_rate >= 0.80:
            threshold_approaching = True

        report.append({
            'symbol': symbol,
            'amt': amt,
            'entry': entry,
            'mark': mark,
            'liq': liq,
            'dist_val': dist_val,
            'dist_pct': dist_pct,
            'risk_rate': risk_rate,
            'upnl': upnl,
            'threshold_approaching': threshold_approaching
        })

        if threshold_approaching and auto_close and not symbol.startswith('ETH'):
            print(f'[EMERGENCY CLOSE TRIGGERED] Closing non-ETH position {symbol}!')
            try:
                close_side = 'sell' if side == 'LONG' else 'buy'
                order = await ex.create_order(
                    symbol=symbol,
                    type='market',
                    side=close_side,
                    amount=amt,
                    params={'positionSide': side}
                )
                print(f'[EMERGENCY CLOSE SUCCESS] Closed {symbol}: {order.get("id")}')
                close_triggered = True
            except Exception as e:
                print(f'[EMERGENCY CLOSE ERROR] {symbol}: {e}')

    await ex.close()
    return report, close_triggered

if __name__ == '__main__':
    report, closed = asyncio.run(check_and_guard(auto_close=False))
    print(json.dumps(report, indent=2))
