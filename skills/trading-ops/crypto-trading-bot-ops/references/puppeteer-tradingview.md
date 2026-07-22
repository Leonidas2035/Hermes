# Puppeteer + TradingView scraping

## Install (system chrome present)
```
PUPPETEER_SKIP_DOWNLOAD=true npm install puppeteer
```
Requires Node (v22 ok) and a system `google-chrome` binary.

## Launch (sandbox-safe on Linux)
```js
const puppeteer = require('puppeteer');
const browser = await puppeteer.launch({
  headless: 'new',
  executablePath: '/usr/bin/google-chrome',
  args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'],
});
```

## Pages
- Overview + price: `https://www.tradingview.com/symbols/XRPUSDT/`
- Technicals:   `https://www.tradingview.com/symbols/XRPUSDT/technicals/`

## Extract technical rating
```js
await page.goto(url, { waitUntil: 'networkidle2', timeout: 45000 });
await new Promise(r => setTimeout(r, 3500));   // widgets need time to render
const tech = await page.evaluate(() => {
  const t = document.body.innerText;
  return {
    rating:  (t.match(/(Strong Buy|Buy|Neutral|Sell|Strong Sell)/) || [])[1],
    oscillators: (t.match(/Oscillators\s+(Strong Buy|Buy|Neutral|Sell|Strong Sell)/) || [])[1],
    movingAverages: (t.match(/Moving Averages\s+(Strong Buy|Buy|Neutral|Sell|Strong Sell)/) || [])[1],
    levels: [...t.matchAll(/(Resistance|Support)\s*[:]?\s*([\d.]+)/g)].map(x => `${x[1]} ${x[2]}`),
  };
});
```

## Bias mapping
`Strong Buy`/`Buy` → LONG · `Neutral` → NEUTRAL · `Sell`/`Strong Sell` → SHORT.
Combine with funding rate and news sentiment before final bias.

## Tips
- `page.title()` is a quick liveness check (e.g. "XRPUSDT — XRP to Tether Price Chart — TradingView").
- TV may show day/week/month/year % moves in body text — useful regime context.
- Headless Chrome is heavy; launch once, reuse, `browser.close()` at end.
