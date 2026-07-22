# CODER TASK — Виправлення відкриття SHORT у BingX Hedge-Mode (qe_trade.py)

> Самодостатнє завдання для кодера (Codex / Claude Code / Cursor). Читати повністю.
> Репозиторій: /home/layman/QuantumEdge

═══ КРИТИЧНИЙ БАГ (перевірено фактами на живій біржі BingX VST) ═══

Автономний демон tools/xrp_short_watch.py викликає:
  qe_trade.py place sell SHORT 50000 1.0924 1.08 1.1459
(відкрити ШОРТ XRP при існуючому ЛОНГУ, hedge-mode)

РЕАЛЬНА ВІДПОВІДЬ БІРЖІ (два варіанти, залежно від params):

Варіант 1 (params БЕЗ reduceOnly, поточний стан):
  {"error":"bingx {\"code\":109420,\"msg\":\"position not exist\",\"data\":{}}"}
  → BingX інтерпретує side=sell+positionSide=SHORT як СПРОБУ ЗАКРИТИ шорт
    (reduce), але шорт-позиції немає → помилка.

Варіант 2 (додано reduceOnly:False до params):
  {"error":"bingx {\"code\":109400,\"msg\":\"In the Hedge mode, the 'ReduceOnly' field can not be filled.\",\"data\":{}}"}
  → BingX УЗАГАЛІ блокує поле reduceOnly у hedge-mode (навіть якщо False).

ОТЖЕ: жоден варіант не відкриває новий SHORT при існуючому LONG у hedge-mode.
Демон думає, що відкрив шорт (пише [EXEC] OPEN_SHORT), але ордер НЕ створюється.
Це НЕБЕЗПЕЧНО: звіт бреше, ордерів немає.

═══ ЩО ТРЕБА ЗРОБИТИ ═══

ФАЙЛ: /home/layman/QuantumEdge/tools/qe_trade.py
ФУНКЦІЯ: place(ex, side, pos_side, qty, price, tp=None, sl=None) (рядки ~124-133)

ЗАВДАННЯ: знайти правильний спосіб відкрити НОВУЙ SHORT-позицію в BingX hedge-mode
при існуючому LONG. Варіанти для дослідження (протестувати на живій BingX VST):

  A) Можливо BingX вимагає `positionSide` у форматі, який ccxt не передає правильно.
     Спробувати явно: params={"positionSide":"SHORT"} + side="sell" + type="limit"
     (це вже є, але можливо треба side="buy" з positionSide="SHORT"? НІ — це закриття лонгу).
  B) Можливо BingX hedge-mode вимагає окремий ендпоінт для відкриття протилежної ноги,
     або параметр `hedged: true` / `positionIdx: 2` (для hedge-mode positionIdx=1 це long,
     =2 це short). Перевірити чи ccxt.bingx підтримує positionIdx.
  C) Спробувати відкрити шорт ЧЕРЕЗ market order (не limit): create_order(type="market",
     side="sell", positionSide="SHORT") — можливо market не вимагає reduceOnly.
  D) Подивитись як працює існуючий трейдер (trader.py): чи відкривав він колись НОВИЙ
     SHORT через qe_trade place? (підказка: trader.py лише харвестив існуючий шорт через
     `market buy SHORT`, новий шорт НІКОЛИ не відкривав — тому бага не було помітно).

РІШЕННЯ МАЄ БУТИ:
  - place(sell, SHORT, ...) реально створює коротку ногу при існуючому лонгу
  - без помилок 109420/109400
  - TP/SL (takeProfitPrice/stopLossPrice) виставляються разом з ордером
  - ЛОНГ відкриття (buy LONG) НЕ ламається (перевірити!)

═══ ЯК ТЕСТУВАТИ (ОБЕРЕЖНО, це реальні ордери на VST) ═══

Створити tools/_test_place_short.py:
  1. Відкрити малий SHORT (qty=1000) через place(sell, SHORT, 1000, price, tp, sl)
  2. Перевірити, що ордер створився (snapshot показує short leg або open_order)
  3. ВІДРАЗУ скасувати (cancel_all) — не залишати висячий ордер!
  4. Повторити для LONG (buy LONG) — переконатись що не зламалось
  5. Видалити _test_place_short.py після проходження

АБО просто викликати з CLI і перевірити snapshot:
  .venv/bin/python3 tools/qe_trade.py place sell SHORT 1000 1.09 1.08 1.10
  .venv/bin/python3 tools/qe_trade.py snapshot   # має показати short leg або open order
  .venv/bin/python3 tools/qe_trade.py cancel_all  # очистити!

═══ КРИТЕРІЇ ПРИЙМАННЯ ═══
  1. py_compile tools/qe_trade.py — OK
  2. .venv/bin/python3 -m pytest tools/ -q — 26 passed (не зламати!)
  3. РЕАЛЬНИЙ ТЕСТ: place sell SHORT створює ордер без помилок 109420/109400,
     snapshot підтверджує коротку ногу (або open_order), потім cancel_all.
  4. ЛОНГ відкриття не зламане (place buy LONG працює як раніше).
  5. execute_short_setup у xrp_short_watch.py має перевіряти результат place
     і НЕ писати [EXEC] OPEN_SHORT якщо ордер не створився (важливо! зараз бреше).
     Додати перевірку: res.get("id") is not None перед поверненням "OPEN_SHORT".

═══ КОМАНДИ ═══
  cd /home/layman/QuantumEdge
  .venv/bin/python3 -m py_compile tools/qe_trade.py
  .venv/bin/python3 -m pytest tools/ -q
  .venv/bin/python3 tools/qe_trade.py place sell SHORT 1000 1.09 1.08 1.10 && .venv/bin/python3 tools/qe_trade.py snapshot && .venv/bin/python3 tools/qe_trade.py cancel_all

═══ ФОРМАТ ЗВІТУ (українською) ═══
  Який варіант спрацював (A/B/C/D) | що змінено в place | результат реального тесту |
  чи execute_short_setup тепер чесно перевіряє ордер.
