# BingX Swap API — перевірені кверки (quantumedge)

Факти виявлені ЖИВИМИ викликами (не юніт-тестами) у сесії 2026-07. Стосуються
`ccxt.bingx` у режимі `swap` + hedge-mode (VST/testnet). Не дублювати випадково.

## 1. edit_position НЕ ІСНУЄ
`ccxt.bingx` не має методу `edit_position` (hasattr → False). Будь-яка спроба
модифікувати СЛ/ТП через нього → AttributeError. Не використовувати.

## 2. Зміна СЛ = cancel + recreate
Правильний життєвий цикл для трейлінгу СЛ до BE на BingX:
1. `fetch_positions(symbols=[SYMBOL])` → взяти `contracts` (реальний розмір).
2. `fetch_open_orders(SYMBOL)` → знайти існуючий СЛ-ордер:
   фільтр `o["type"] in ("stop","trigger")` АБО `info.get("stopLossPrice")`
   або `info.get("triggerPrice")`, і `info["positionSide"]==side`.
3. `cancel_order(old_id, SYMBOL)`.
4. `create_order(type="market", side=протилежний, amount=РОЗМІР_ПОЗИЦІЇ,
   params={"positionSide": side, "stopLossPrice": new_sl})`.

## 3. reduceOnly ЗАБОРОНЕНО в hedge-mode
`params={"reduceOnly": True}` → помилка:
`code 109400, "In the Hedge mode, the 'ReduceOnly' field can not be filled"`.
НЕ передавати. У hedge-mode ордер протилежного боку і так редьюсить позицію.

## 4. amount=0.0 відхиляється
Створення ордера з `amount=0.0` → `"amount of XRP/USDT:USDT must be greater than
minimum amount precision of 1"`. Завжди брати реальний розмір позиції з
`fetch_positions`.

## 5. Публічні OHLCV/book/trades працюють БЕЗ ключа
`ccxt.bingx().fetch_ohlcv(...)`, `fetch_ticker`, `fetch_order_book` — анонімно.
Приватні дії (ордери, позиції) — через ключі з `.env` (dotenv), НЕ хардкодити.

## 6. WS book+trades
`ccxt.pro.bingx().watch_order_book()` / `watch_trades()` працюють з ключам з .env.
Без ключа публічний WS може не streamити повний book — використовувати ключі.

## 7. ВІДКРИТТЯ НОВОГО SHORT при існуючому LONG (БАГА open-position, 2026-07)
У hedge-mode, коли вже є LONG і треба відкрити SHORT (хедж/скальп) через
`create_order(symbol, type="limit", side="sell", params={"positionSide":"SHORT"})`,
BingX СПРИЙМАЄ це як спробу ЗАКРИТИ шорт, якого немає:
- БЕЗ reduceOnly: `{"code":109420,"msg":"position not exist"}`
- З `reduceOnly:False`: `{"code":109400,"msg":"In the Hedge mode, the 'ReduceOnly'
  field can not be filled"}` (див. п.3 — поле заборонено взагалі).

ЖОДЕН варіант не створює коротку ногу. Це НЕ виправлено у master
(див. CODER_TASK_short_open_fix.md). Можливі напрямки фіксу для кодера:
- спробувати `positionIdx` (1=long, 2=short) у params замість positionSide;
- спробувати `side="buy"` з `positionSide="SHORT"` (це НЕ закриття лонгу, а відкриття
  короткої ноги у hedge-mode — BingX так розрізняє ноги);
- перевірити чи ccxt.bingx передає positionSide у правильному регістрі/формі.

## Швидкий рецепт перевірки (чи ордер реально створився)
ПІСЛЯ кожного `place`/`market` — ОБОВ'ЯЗКОВО звірити з біржею:
```
.venv/bin/python3 tools/qe_trade.py snapshot
# шукати legs[] з side=="short" і size>0, АБО open_orders_count>0
```
Якщо код/демон каже "OPEN SHORT", а snapshot має лише long leg і open_orders=0 →
ордер НЕ створився (помилка 109420/109400 проковтнута). execute_short_setup має
перевіряти `res.get("id") is not None` перед записом "[EXEC] OPEN_SHORT".

## 8. ЖИВА ПЕРЕВІРКА vs ЗВІТ (дисципліна)
Кодер (і автономний демон) може звітувати успіх ("OPEN SHORT XRP", "edge 94-96%"),
якого НЕМАЄ на біржі/у файлі. Дві незалежні перевірки:
- файл результатів: references/CODER_VERIFY.md (calibration.json is_synthetic, n, hit_rate)
- САМА БІРЖА: `qe_trade.py snapshot` (legs + open_orders) — для ордерів/позицій.
Обидві обов'язкові перед "готово".
