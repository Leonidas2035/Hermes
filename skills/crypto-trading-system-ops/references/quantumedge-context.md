# QuantumEdge context (session-derived, condensed)

## Working TradingView parse snippet (Node + Puppeteer, system chrome)
```js
const puppeteer = require('puppeteer');
const SYMBOL = process.argv[2] || 'XRPUSDT';
(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/usr/bin/google-chrome',
    args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.goto(`https://www.tradingview.com/symbols/${SYMBOL}/technicals/`,
                  { waitUntil: 'networkidle2', timeout: 45000 });
  await new Promise(r => setTimeout(r, 3500));
  const tech = await page.evaluate(() => {
    const txt = document.body.innerText;
    const m = txt.match(/(Strong Buy|Buy|Neutral|Sell|Strong Sell)/);
    const osc = txt.match(/Oscillators\s+(Strong Buy|Buy|Neutral|Sell|Strong Sell)/);
    const ma  = txt.match(/Moving Averages\s+(Strong Buy|Buy|Neutral|Sell|Strong Sell)/);
    const levels = [...txt.matchAll(/(Resistance|Support)\s*[:]?\s*([\d.]+)/g)].map(x=>`${x[1]} ${x[2]}`);
    return { rating:m?m[1]:null, oscillators:osc?osc[1]:null, movingAverages:ma?ma[1]:null, levels:levels.slice(0,10) };
  });
  await browser.close();
  console.log(JSON.stringify({ symbol: SYMBOL, technicalsPage: tech }, null, 2));
})().catch(e=>{ console.error('TV_PARSE_ERR', e.message); process.exit(1); });
```
Run: `node tools/tv_analyzer/tv_parse.js XRPUSDT`. Smoke-verified: returns
rating/oscillators/MA/levels for XRPUSDT.

## Architecture (as observed)
- Orchestrator: `QuantumEdge.py` — ZMQ daemon on :5560 (JSON-RPC:
  SYSTEM_BOOTSTRAP / DIAGNOSTICS / HALT). Components: hub, supervisor,
  ai_scalper, dyndca, lockbotbtc.
- MarketDataHub (ZMQ :5555) publishes depth L2, trades, klines, walls, metrics.
- ai_scalper: `src/quantum_edge_core/ai_scalper_bot/run_bot.py`, execution
  `bingx_gateway.py` (ccxt bingx, swap format `BASE/USDT:USDT`).
- QuestDB tables: `klines_1m`, `microstructure_v1`(absent), `trades`,
  `realized_trades`, `portfolio_state`, `market_features`, `orderbook_snapshots`,
  `bot_telemetry`. TS column = `timestamp`.
- Supervisor policy file: `runtime/policy.json` (allow_trading, mode,
  size_multiplier, block_loss_closure). `reason:"OK|LLM_CB_OPEN"` = LLM circuit
  breaker open (LLM moderation inactive).

## Sanctioned action flow that worked (XRP/USDT, testnet/VST)
1. Probe read-only: balance (free was 0 → margin locked), positions
   (LONG 28.7k + SHORT 850.7k, net-short ~822k), 32 open limit orders (all buy
   below market, not filling).
2. B) `cancel_all_orders` → 24 cancelled, book clean.
3. C) market `buy` 425k with `params={"positionSide":"SHORT"}` → SHORT halved
   (850.7k→425.7k), freed margin (free 0→~95k VST). Bot then resumed placing
   orders (the "Insufficient margin" 101204 errors stopped).
4. D) Bot was NOT actually hung — orchestrator false-reported TERMINATED; the
   real block was locked margin. Fix: psutil external-process detection by
   cmdline signature.

## Bias derivation that worked
TV rating (Neutral) + funding rate (+0.0001 → mildly bullish) + Firecrawl news
sentiment (BULLISH) → "NEUTRAL (news + funding mildly bullish)". Scalp plan:
trade range, no breakout without volume/OI confirmation.

## Firecrawl (news layer)
`POST https://api.firecrawl.dev/v1/search`, header `Authorization: Bearer <key>`,
body `{"query":"XRP Ripple price news today","limit":3}`. Free Tier — keep to 1
request per analysis. Crude sentiment via bull/bear keyword count on titles+desc.
