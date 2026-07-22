# TradingView scraping via Puppeteer (system Chrome)

## Install (reuse system Chrome — do NOT download a second Chromium)
```bash
cd tools/tv_analyzer && npm init -y >/dev/null 2>&1
PUPPETEER_SKIP_DOWNLOAD=true npm install puppeteer@23
```
System Chrome was at `/usr/bin/google-chrome` (verify with `which google-chrome`).

## Launch
```js
const browser = await puppeteer.launch({
  headless: 'new',
  executablePath: '/usr/bin/google-chrome',
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
});
```

## Pages
- Overview: `https://www.tradingview.com/symbols/XRPUSDT/`
- Technicals: `https://www.tradingview.com/symbols/XRPUSDT/technicals/`

## Reading the DOM
- `waitUntil: 'networkidle2'`, timeout 45s, THEN `await new Promise(r => setTimeout(r, 4000))`
  so rating widgets finish rendering.
- Technical rating: `document.body.innerText.match(/(Strong Buy|Buy|Neutral|Sell|Strong Sell)/)`.
- On `/technicals/`: also capture `Oscillators (...)`, `Moving Averages (...)`,
  and support/resistance via `/(Resistance|Support)\s*[:]?\s*([\d.]+)/g`.
- Print `JSON.stringify(...)` to stdout; call from Python with
  `subprocess.run(['node','tv_parse.js', symbol], capture_output=True, text=True)`.

## Gotchas
- The symbol overview page mixes many tickers (BTC/ETH/etc sidebar) — prefer the
  `/technicals/` page for a clean rating.
- `document.querySelector('[data-testid="technical-analysis-summary"]')` is
  unreliable; regex over `body.innerText` is more robust.
