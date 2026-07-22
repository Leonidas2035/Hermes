# Джерела даних QuantumEdge (реальність, перевірена фактами)

## Мережа
- `binance.com` / `fapi.binance.com` — DNS fail з цього ПК. НЕ використовувати.
  Перевірка: `getent hosts api.binance.com` → FAIL.
- `api.bybit.com` / `stream.bybit.com` — OK. Перевірка: `getent hosts api.bybit.com` → OK.

## ccxt (rest)
- Bybit: `fetch_ohlcv` (пагінація по `since`, ~1000/запит), `fetch_oi_history`,
  `fetch_order_book` (поточний). Джерело №1 для історії.
- OKX: фолбек (теж ccxt) для OHLCV/OI.
- BingX: використовується ботом; для аналітики rest обмежений.

## ccxt.pro (WebSocket) — для order flow
- **Bybit book+trades — БЕЗ ключа.** Публічні ринкові дані. Перевірено:
  `ccxtpro.bybit()` без apiKey, `watch_order_book`/`watch_trades` працюють.
  Символ деривативів: `BTC/USDT:USDT`, `options={"defaultType":"linear"}`.
- **BingX book+trades — З ключами з .env.** Перевірено працює (smoke-тест:
  book bid0=64380.9, trade buy 64383.6). Ключі підхоплюються через `python-dotenv`:
  `BINGX_API_KEY` / `BINGX_API_SECRET` (або `_DEMO_` варіанти).
  НЕ хардкодити. Реальний .env = симлінк `/home/layman/QuantumEdge/.env`
  -> `/home/layman/.hermes/.env`.

## Кеш / файли
- runtime/cache/ohlcv_BTC_USDT_USDT_1h_bybit_365d.json — 8760 свічок (рік)
- runtime/cache/oi_BTC_USDT_USDT_1h_bybit_365d.json — 2000 (OI коротший період)
- runtime/orderflow_raw/*.jsonl — self-collected book+trades (WS)

## Важливо
- **Історичного L2-стакана у ccxt НЕМАЄ** (лише поточний + історичні trades).
  Тому маніпуляції бектестимо на self-collected живому WS-дампі.
- Збирання BingX і Bybit ОДНОЧАСНО у той самий jsonl = гонка запису (два процеси).
  Один процес з `--exchange both` пише через єдиний writer — безпечно.
