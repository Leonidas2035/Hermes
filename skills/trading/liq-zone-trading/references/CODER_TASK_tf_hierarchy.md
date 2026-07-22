# CODER TASK — Ієрархія ТФ (4h/15m/5m) + усунення "порожньої роботи"

> Самодостатнє завдання для кодера (Codex / Claude Code / Cursor). Читати повністю.
> Репозиторій: /home/layman/QuantumEdge . Файл: /home/layman/QuantumEdge/tools/xrp_short_watch.py

═══ ПРОБЛЕМА (вказівка власника) ═══
Демон прокидається кожні 5 хв, але analyze_xrp аналізує 1h свічку (fetch_ohlcv(...,"1h",limit=200)).
Це ПОРОЖНЯ РОБОТА: 1h свічка оновлюється раз на годину, тому 12 прокидань на годину
дивляться на ОДНУ й ту ж 1h свічку — індикатори не змінюються. Треба вибудувати
ІЄРАРХІЮ ТФ:
  • 4h  — ГЛОБАЛЬНИЙ контекст (лонг-тренд? бічник? чи взагалі не шортити?)
  • 15m — СЕТАПИ шорту (коли 4h не проти, шукаємо 3+ голоси + LONG_LIQ зона)
  • 5m  — ЛОКАЛЬНА оцінка + ТАЙМІНГ входу (демон прокидається -> дивиться 5m)
Також: "можливо глобальний лонг по 4h і в моменті кілька шортів по 15m" — тобто
шорт це СКАЛЬП/ХЕДЖ всередині глобального лонг-тренду, не глобальний розворот.

═══ ЦІЛЬОВИЙ ФАЙЛ ═══
/home/layman/QuantumEdge/tools/xrp_short_watch.py
Скіли (НЕ змінювати): tools/sigtest/indicators.py (enrich), tools/liqmap/model.py
(qe_trade.py для виконання, ВЖЕ виправлено для SHORT у hedge-mode).

═══ ЩО ЗРОБИТИ ═══

1. СТВОРИТИ analyze_tf(symbol, tf, limit=200) — універсальна ф-ція (замість дублювання):
   - fetch_ohlcv(symbol, tf, limit=200), enrich(df)
   - порахувати long_v/short_v (EMA/MACD/RSI/OBV як зараз)
   - build_heatmap + _extract_zones -> near zones (<=2%)
   - повернути dict: {tf, price, bias, long_votes, short_votes, rsi, macd_hist,
     obv_slope, near_zones, short_target, drop_pct (див. п.4)}

2. РЕФАКТОРИНГ analyze_xrp() — викликати analyze_tf для ТРЬОХ ТФ:
   h4 = analyze_tf(SYM, "4h")    # глобальний контекст
   m15 = analyze_tf(SYM, "15m")   # сетап шорту
   m5 = analyze_tf(SYM, "5m")     # локальний таймінг
   (analyze_btc() аналогічно: h4/m15/m5, якщо треба кореляція)

3. ІЄРАРХІЯ РІШЕНЬ (у decide_short / execute):
   - ГЛОБАЛЬНИЙ КОНТЕКСТ (h4):
       * h4.bias == "LONG"  -> шорт дозволений лише як СКАЛЬП/ХЕДЖ (короткий, take-profit близько)
       * h4.bias == "SHORT" -> можна шортити агресивніше (трендовий шорт)
       * h4.bias == "NEUTRAL" -> шорт лише за чітким 15m+5m сетапом
   - СЕТАП ШОРТУ (m15): m15.short_v >= 2 І є LONG_LIQ зона -> short_target формується
   - ТАЙМІНГ (m5): вхід дозволений якщо m5 підтверджує (m5.short_v >= 1 АБО m5.rsi>55
     АБО m5.macd_hist>0 для лонгу / навпаки для шорту). Якщо m5 проти -> відкласти вхід.
   - BTC-КОРЕЛЯЦІЯ: якщо BTC h4/m15 в шорт -> +1 до m15.short_v (як зараз було для 1h).

4. ФІЛЬТР ДАМПУ (на m15, запобігання входу на дні):
   drop_pct = (close[-4]-close[-1])/close[-4]*100  (4 свічки 15m)
   якщо drop_pct >= 1.5% -> short_target = None, dump_blocked = True
   (аналогічно m5: якщо drop >= 1.0% за 4 свічки 5m -> не входити)

5. ЛОКАЛЬНА ОЦІНКА ПРИ КОЖНОМУ ПРОКИДАННІ:
   Демон прокидається (sleep 300) -> analyze_xrp() дивиться 5m (свіжа свічка кожні 5 хв!)
   -> більше не "порожня робота". 1h/4h оновлюються рідше, але 5m дає свіжі сигнали.

6. УВІМКНУТИ 5m У MAIN_LOOP: викликати analyze_xrp (яка тепер дивиться 4h/15m/5m),
   логувати h4_bias, m15_bias, m5_bias, drop_pct, dump_blocked у звіт.

═══ ПРАВИЛА ВЛАСНИКА ═══
  • НЕ закривати збиткові (лонг XRP не чіпати).
  • Авто-стоп вимкнено — СЛ широкий (5%).
  • Шорт = скальп/хедж (не глобальний розворот, якщо h4=LONG).
  • Не шортити в дамп (drop-фільтр).
  • execute_short_setup має перевіряти res.get("id") is not None (вже виправлено кодером).

═══ КРИТЕРІЇ ПРИЙМАННЯ ═══
  1. py_compile tools/xrp_short_watch.py — OK.
  2. .venv/bin/python3 -m pytest tools/ -q — 26 passed.
  3. Тест емуляції (tools/_test_hierarchy.py, потім ВИДАЛИТИ):
     - A: h4=LONG, m15=SHORT(2S), m5=SHORT(1S) -> short_target готовий (скальп у лонг-тренді).
     - B: h4=SHORT, m15=SHORT(3S), m5=NEUTRAL, drop=0% -> short_target готовий (агресивний).
     - C: m15=SHORT(2S) АЛЕ drop_pct=2.0% -> dump_blocked=True, short_target=None.
     - D: m15=SHORT(2S) АЛЕ m5=LONG(3L) -> вхід відкладено (m5 проти), short_target=None.
  4. ЖОДНИХ вигаданих даних. Перевірити на живих даних BingX.
  5. _test_hierarchy.py створити, прогнати, PASS, видалити.

═══ КОМАНДИ ═══
  cd /home/layman/QuantumEdge
  .venv/bin/python3 -m py_compile tools/xrp_short_watch.py
  .venv/bin/python3 -m pytest tools/ -q
  .venv/bin/python3 tools/xrp_short_watch.py --once
  .venv/bin/python3 tools/_test_hierarchy.py

═══ ФОРМАТ ЗВІТУ (українською) ═══
  Що змінено (analyze_tf, ієрархія 4h/15m/5m, dump-фільтр) | результати емуляції A-D |
  чи демон тепер дивиться 5m при кожному прокиданні (не порожня робота).
