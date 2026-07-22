# CODER TASK — Кореляція BTC + додавання BTC як торгової пари (XRP SHORT-WATCH)

> Самодостатнє завдання для кодера (Codex / Claude Code / Cursor). Читати повністю.
> Репозиторій: /home/layman/QuantumEdge . Аналітичний контур: /home/layman/.hermes/quantumedge_analysis/

═══ КОНТЕКСТ ═══
Є автономний демон tools/xrp_short_watch.py (запущений фоном, аналізує XRP кожні 5 хв,
сам відкриває/харвестить ШОРТ через tools/qe_trade.py, НЕ чіпає існуючий LONG XRP
за правилом власника 1). Він працює, АЛЕ сліпий до BTC: вимагає 3+ індикатори в шорт
САМОГО XRP. Проблема: коли BTC досягає ключового рівня (напр. 65000) і розвертається,
а на XRP індикатори ще "не дозріли" (лише 1-2 голоси), демон пропускає вхід у шорт,
хоча ринок ведмедячий (BTC EMA спадає, US-сесія волатильна). XRP іде за BTC із запізненням.

ВЛАСНИК хоче (Варіант А): додати кореляцію з BTC — якщо BTC показує ведмедячий сетап
(або досяг ключового рівня й розвернувся), і на XRP є близька LONG_LIQ зона (ціль ТП)
+ хоча б 1-2 індикатори в шорт → відкривати шорт по XRP РАНІШЕ, ніж дозріють 3 голоси.
А ТАКОЖ: додати BTC як ОКРЕМУ торгову пару (власний аналіз + власні ордери).

═══ ЦІЛЬОВИЙ WORKSPACE ТА СКІЛИ (точні шляхи) ═══

РЕПОЗИТОРІЙ: /home/layman/QuantumEdge
ВЕНВ: /home/layman/QuantumEdge/.venv/bin/python3

СКІЛИ (готові модулі, ІМПОРТУВАТИ, не переписувати):
  • Індикатори:     /home/layman/QuantumEdge/tools/sigtest/indicators.py
                     функція enrich(df) -> DataFrame з колонками ema9/ema21/ema50,
                     rsi, macd_hist, macd, adx, obv_slope, bb_pos, bb_upper, bb_lower, atr_pct
                     (df має мати колонки ts,open,high,low,close,volume)
  • Карта лікв.:    /home/layman/QuantumEdge/tools/liqmap/model.py
                     build_heatmap(ohlcv, price_bins=140) -> dict з 'grid','price_levels'
                     _extract_zones(profile, centers, last_price, top=8) -> list зон
                     (profile = np.array(heat['grid'])[:,-1], centers = np.array(heat['price_levels']))
                     зона = {price, intensity, side:'LONG_LIQ'|'SHORT_LIQ', dist_pct}
  • Виконання:     /home/layman/QuantumEdge/tools/qe_trade.py
                     CLI: snapshot | place <side> <posSide> <qty> <price> [tp] [sl] |
                           market <side> <posSide> <qty> | modify_sl <posSide> <new_sl>
                     place створює limit-ордер з tp/sl через params stopLossPrice/takeProfitPrice
                     SYMBOL береться з ENV MARKET_DATA_SYMBOLS (default XRPUSDT) — для BTC
                     треба передати SYMBOL=BTCUSDT або викликати з правильним символом.

ФАЙЛ ДЛЯ ДООПРАЦЮВАННЯ: /home/layman/QuantumEdge/tools/xrp_short_watch.py
  (вже містить: analyze_xrp(), current_position(), decide_short(), execute_short_setup(),
   main_loop(). Треба додати BTC-кореляцію та BTC-пару, НЕ ламаючи існуюче.)

═══ ЩО ЗРОБИТИ ═══

1. ДОДАТИ analyze_btc() — аналог analyze_xrp(), але для BTC/USDT:USDT:
   - fetch_ohlcv('BTC/USDT:USDT','1h',limit=200) через ccxt.bingx
   - enrich(df), порахувати long_votes/short_votes ЯК У analyze_xrp (EMA/MACD/RSI/OBV)
   - build_heatmap + _extract_zones -> near zones (<=2%)
   - ПОВЕРТАТИ dict: {price, bias, long_votes, short_votes, near_zones, rsi, macd_hist,
     ema9/21/50, key_level_hit (bool: чи ціна торкалася/перетнула 65000 за останні N свічок
     і розвернулася — напр. high>=65000 і закриття нижче)}

2. ДОДАТИ BTC-КОРЕЛЯЦІЮ В analyze_xrp() (Варіант А):
   - викликати analyze_btc() всередині analyze_xrp()
   - якщо BTC bias == 'SHORT' (або key_level_hit == True) → ДОДАТИ +1 short_голос до XRP
     (навіть якщо XRP-індикатори нейтральні). Тобто: xrp_short_votes += 1 якщо btc_short.
   - поріг для XRP-шорту ЗНИЗИТИ: було short_v >= 3, стало short_v >= 2 (бо BTC дає
     додатковий контекст). Але ЯКЩО BTC нейтральний/лонг — тримати поріг 3.

3. ДОДАТИ BTC-ПАРУ як окремий аналіз + виконання:
   - функція decide_and_execute_btc(sig_btc, pos_btc) — аналог execute_short_setup,
     але для BTC: шукає SHORT-сетап по BTC (3+ індикатори в шорт + LONG_LIQ зона нижче),
     відкриває шорт через qe_trade (SYMBOL=BTCUSDT), харвестить прибутковий.
   - ПРАВИЛО: BTC-шорт відкривається ЛИШЕ якщо bias=='SHORT' і є near LONG_LIQ зона.
     Не закривати збиткові (той самий принцип, що для XRP).
   - qe_trade.py викликати з env SYMBOL=BTCUSDT:
     subprocess.run([venv, 'tools/qe_trade.py', 'snapshot'], env={**os.environ, 'MARKET_DATA_SYMBOLS':'BTCUSDT'})
     (qe_trade бере SYMBOL з MARKET_DATA_SYMBOLS.split(',')[0])

4. У main_loop() — викликати analyze_btc() + decide_and_execute_btc() паралельно з XRP.
   Писати звіт у ТОЙ САМИЙ xrp_short_watch.jsonl (додати поле 'pair':'BTC' або окремий рядок).
   TG-сповіщення (send_telegram_message) — дублювати для BTC аналогічно XRP.

5. TG-НОТИФІКАЦІЯ (вже імпортована send_telegram_message):
   - upon OPEN SHORT BTC -> 📉 OPEN SHORT BTC (qty, tp, sl, bias, btc_price)
   - upon CLOSE SHORT BTC (profit) -> 📈 CLOSE SHORT BTC (uPnL, reason)

═══ ПРАВИЛА ВЛАСНИКА (священні, не порушувати) ═══
  • НЕ закривати збиткові позиції (ні XRP, ні BTC).
  • Авто-стоп ВИМКНЕНО — СЛ лише широкий (5%), страхування гепу, не тісний трейл.
  • Шорт лише харвест (ліміт нотіоналу BingX ~1M на 10x) — не нарощувати шорт без міри.
  • Лонг XRP (898145 @ 1.1215) НЕ чіпати.

═══ КРИТЕРІЇ ПРИЙМАННЯ ═══
  1. py_compile tools/xrp_short_watch.py — без помилок.
  2. Тест емуляції (tools/_test_btc_corr.py, потім ВИДАЛИТИ):
     - емулювати BTC bias=SHORT (rsi=40, macd_hist=-10, ema спадає) -> analyze_xrp()
       має дати +1 short_голос від BTC (short_votes зростає на 1 відносно без BTC).
     - емулювати XRP short_v=2 + BTC short -> сетап ШОРТ готовий (short_target != None).
       Раніше при short_v=2 сетапу не було.
     - емулювати BTC neutral -> XRP short_v=2 НЕ дає сетап (поріг 3 без BTC-підтвердження).
  3. НЕ ламати існуючі 26 тестів: .venv/bin/python3 -m pytest tools/ -q (має бути 26 passed).
  4. ЖОДНИХ вигаданих даних. Перевіряти на реальних даних BingX (fetch_ohlcv працює).
  5. Створити tools/_test_btc_corr.py, прогнати, переконатись що PASS, потім видалити.

═══ КОМАНДИ ПЕРЕВІРКИ ═══
  cd /home/layman/QuantumEdge
  .venv/bin/python3 -m py_compile tools/xrp_short_watch.py
  .venv/bin/python3 -m pytest tools/ -q
  .venv/bin/python3 tools/xrp_short_watch.py --once   # один цикл, перевірити BTC+XRP звіт
  .venv/bin/python3 tools/_test_btc_corr.py

═══ ФОРМАТ ЗВІТУ (українською, коротко) ═══
  Що додано | які функції | результат тестів емуляції | чи працює BTC-кореляція на живих даних.
