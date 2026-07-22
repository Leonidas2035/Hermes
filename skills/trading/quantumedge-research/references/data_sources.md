# QuantumEdge — Факти по джерелах даних (перевірено 2026-07)

Стислий банк перевірених фактів про доступність даних. Не дзеркало доків — лише
те, що реально протестовано в цьому середовищі.

## Мережа / біржі
- **Binance ЗАБЛОКОВАНИЙ**: `getent hosts api.binance.com` → FAIL (DNS). Не писати до нього.
- **Bybit**: працює. REST (OHLCV/OI) + ccxt.pro WS (book+trades) БЕЗ ключа.
  Публічний WS: `watch_order_book`, `watch_trades` — відкриті ендпоїнти.
- **OKX**: працює як фолбек. Аналогічні можливості.
- **BingX**: публічний OHLCV через ccxt (без ключа ОК); book+trades через ccxt.pro
  ВИМАГАЄ ключі. Ключі беруться з `.env` (симлінк на /home/layman/.hermes/.env)
  через `dotenv.load_dotenv()`, змінні `BINGX_API_KEY` / `BINGX_API_SECRET`
  (або `_DEMO_` варіанти). НІКОЛИ не хардкодити ключі в коді.

## Що реально доступно
- **OHLCV історичні**: так, пагінацією. ccxt ~1000 свічок/запит → цикл по `since`.
  Рік 1h BTC = 8760 свічок. Кеш на диск: runtime/cache/ohlcv_BTC_*.json.
- **OI (Open Interest) історичні**: Bybit `fetch_oi_history` (OKX фолбек);
  BingX OI history НЕМАЄ. BingX дає лише поточний OI.
- **Funding**: BingX/Bybit REST.
- **Trades історичні**: так (ccxt `fetchTrades`, пагінація по часу) — основа order-flow.
- **L2 book історичні (снепи стакану "в минулому")**: НІ. ccxt не має. Безплатно
  не існує. Платні вендори (Kaiko/TensorCharts/CryptoQuant) — поза scope.
  → Рішення: **self-collection** живого book+тrades через WS у файл, потім бектест.

## Обсяги / продуктивність (реальні виміри)
- Book+trades потік: ~2.7 МБ/хв (BTC 1h, depth 50). Рік такого = ~1.4 ТБ (не збирати рік!).
- Ротація колектора: новий файл кожні 60 хв АБО при перевищенні 2 ГБ (writer_loop).
- Диск хоста: ~325 ГБ вільно — короткі/середні прогони безпечні.
- liqmap backtest: 8760 свічок × step6 walk-forward ≈ кілька хв (векторизовано numpy).
- sigtest backtest: 8760 свічок, 4 горизонти ≈ <1 хв.

## Quirks (пастки)
- ccxt не має `__version__` — `import ccxt; ccxt.__version__` кидає AttributeError. Нормально.
- `build_heatmap(ohlcv)` повертає `grid` як **list of lists**, а не np.array →
  конвертуй `np.array(heat["grid"])` і бери `[:, -1]` для поточного профілю.
- `_extract_zones(profile, centers, last_price)` чекає `profile` = 1D array
  (останній стовпець grid), а НЕ весь grid.
- BingX symbol для деривативів: `BTC/USDT:USDT` (defaultType linear).
- ccxt WS шумить warning у stderr — глушити grep -vE у терміналі.
