# CODER TASK — 15m таймінг входу + фільтр "не шортити в дамп" (xrp_short_watch.py)

> Самодостатнє завдання для кодера (Codex / Claude Code / Cursor). Читати повністю.
> Репозиторій: /home/layman/QuantumEdge

═══ КОНТЕКСТ ═══
Автономний демон tools/xrp_short_watch.py аналізує XRP/BTC кожні 5 хв і сам відкриває
шорт за сетапом. ЗАРАЗ аналіз на 1h (fetch_ohlcv(...,"1h",limit=200), рядки 44 і 99).
ПРОБЛЕМА власника: "Ціна XRP сильно просіла, і навіть якщо з'явиться сигнал в шорт —
вже пізно відкривати, бо рух себе вичерпав і ми відкриєм шорт на дні". 1h індикатори
запізнюються: коли вони "дозріють" до 3 голосів у шорт, ціна вже відскочила/дійшла до дна.

РІШЕННЯ власника: ДОДАТИ 15m для ТАЙМІНГУ входу + залишити 1h для ТРЕНДУ + фільтр
"не шортити в дамп" (не відкривати шорт після різкого падіння — бо це дно/відскік).

═══ ЦІЛЬОВИЙ ФАЙЛ ═══
/home/layman/QuantumEdge/tools/xrp_short_watch.py
Імпорти скілів (НЕ змінювати): tools/sigtest/indicators.py (enrich), tools/liqmap/model.py
(qe_trade.py для виконання). Венв: /home/layman/QuantumEdge/.venv/bin/python3

═══ ЩО ЗРОБИТИ ═══

1. ДОДАТИ analyze_tf(symbol, tf="15m", limit=200) — копія analyze_xrp, але з іншим ТФ:
   - fetch_ohlcv(symbol, "15m", limit=200)
   - enrich(df), порахувати long_v/short_v ЯК У analyze_xrp (EMA/MACD/RSI/OBV)
   - build_heatmap + _extract_zones -> near zones
   - повернути dict: {price, bias, long_votes, short_votes, rsi, macd_hist, obv_slope,
     near_zones, short_target (як у analyze_xrp)}

2. МОДИФІКУВАТИ analyze_xrp() — викликати analyze_tf(SYM, "15m") всередині:
   - h1 = аналіз на 1h (тренд, ПОРІГ 3 для bias)
   - m15 = аналіз на 15m (таймінг, ПОРІГ 2 для entry-сигналу)
   - BTC-кореляція (існуюча) додає +1 до m15.short_v (як зараз до 1h)
   - bias (загальний) = SHORT якщо m15.short_v >= 2 АБО (h1.short_v >= 3 І m15 корелює)
   - КЛЮЧОВЕ: сетап шорту (short_target) формується тільки якщо m15.short_v >= 2
     (швидкий вхід на 15m), а не чекати 1h дозрівання.

3. ФІЛЬТР "НЕ ШОРТИТИ В ДАМП" (запобігання входу на дні):
   - порахувати % падіння за останні N=4 свічки 15m: drop_pct = (close[-4]-close[-1])/close[-4]*100
   - якщо drop_pct >= 1.5% (різкий дамп) -> short_target = None (НЕ відкривати шорт,
     бо рух вичерпано, дно близько). Записати в звіт причину: "DUMP_FILTER: drop X%".
   - аналогічно для BTC (analyze_btc з 15m): якщо BTC дампнув >=2% за 4 свічки 15m -> не шортити.

4. У execute_short_setup() — перевіряти, що short_target не None І не заблоковано
   фільтром дампу (sig.get("dump_blocked") != True). Якщо dump_blocked -> НЕ відкривати,
   записати в звіт "SKIP (dump filter)".

5. У main_loop() — логувати обидва ТФ: h1_bias, m15_bias, drop_pct, dump_blocked.

═══ ПРАВИЛА ВЛАСНИКА (не порушувати) ═══
  • НЕ закривати збиткові (лонг XRP 898145 @ 1.1215 не чіпати).
  • Авто-стоп вимкнено — СЛ лише широкий (5%).
  • Шорт лише харвест.
  • НЕ відкривати шорт на дампі (нове правило!).

═══ КРИТЕРІЇ ПРИЙМАННЯ ═══
  1. py_compile tools/xrp_short_watch.py — OK.
  2. .venv/bin/python3 -m pytest tools/ -q — 26 passed (не зламати!).
  3. Тест емуляції (tools/_test_tf.py, потім ВИДАЛИТИ):
     - Сценарій A: h1=NEUTRAL, m15=SHORT(2S), BTC confirm -> short_target НЕ None (вхід на 15m).
     - Сценарій B: m15=SHORT(2S) АЛЕ drop_pct=2.0% -> short_target=None, dump_blocked=True.
     - Сценарій C: h1=LONG(3L), m15=NEUTRAL -> short_target=None (тренд проти).
  4. ЖОДНИХ вигаданих даних. Перевірити на живих даних BingX (fetch_ohlcv працює).
  5. _test_tf.py створити, прогнати, переконатись PASS, видалити.

═══ КОМАНДИ ═══
  cd /home/layman/QuantumEdge
  .venv/bin/python3 -m py_compile tools/xrp_short_watch.py
  .venv/bin/python3 -m pytest tools/ -q
  .venv/bin/python3 tools/xrp_short_watch.py --once
  .venv/bin/python3 tools/_test_tf.py

═══ ФОРМАТ ЗВІТУ (українською) ═══
  Що додано (analyze_tf, 15m таймінг, dump-фільтр) | результати емуляції | чи працює
  на живих даних (h1/m15 bias, drop_pct, dump_blocked).
