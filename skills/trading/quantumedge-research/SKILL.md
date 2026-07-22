---
name: quantumedge-research
description: Build, verify, and backtest trading signals for QuantumEdge (BTC/XRP on BingX) using REAL exchange data — liquidation heatmap, indicators, order flow. Covers data-source reality (Binance blocked, Bybit/BingX public WS), the "verify-don't-trust-coder" discipline, the delegate-to-coder pattern, and paper-test synthesis. Use when Leonid asks to research/validate a trading signal, build a backtest engine, or synthesize a trade plan from real data.
---

# QuantumEdge — Signal Research Methodology

Класова методологія для дослідження торгових сигналів QuantumEdge. Зв'язує три
вузькі скіли-сигнали в єдиний робочий потік. Читай цей скіл ПЕРЕД тим, як братись
за новий сигнал — тут спільна дисципліна, якої немає у вузьких скілах.

## КОНТЕКСТ
QuantumEdge — приватна HFT/торгова система BTC та XRP на BingX (VST/testnet).
Аналітичний контур: /home/layman/.hermes/quantumedge_analysis; інструменти в
/home/layman/QuantumEdge/tools/{liqmap,sigtest,orderflow}. venv: .venv/bin/python3.
Власник Leonid хоче СТИСЛІ відповіді українською, без розлогих пояснень.

## ПІДПОРЯДКОВАНІ СКІЛИ (вузькі сигнали)
- `liq-zone-trading` — карта ліквідацій (зони-магніти). РЕАЛЬНИЙ edge: зона ≤1%
  від ціни торкається у 83-95% за 5 днів (BTC, рік Bybit).
- `indicator-signal-backtest` — класичні індикатори (EMA/MACD/RSI/BB/OBV). Висновок:
  поодинці ≈ монетка (47-55% win-rate) на BTC 1h; працюють лише mean-reversion
  (короткі) та bb_break (48h, 55.6%).
- `orderflow-manipulation` — стакан + детектори маніпуляцій. Модуль готовий
  (25/25 тестів), але edge на маніпуляціях ще НЕ виміряний (треба self-collection).

## ДЖЕРЕЛА ДАНИХ — РЕАЛЬНІСТЬ (перевірено фактами)
- **Binance ЗАБЛОКОВАНИЙ** (DNS fail, api.binance.com не резолвиться). НЕ використовувати.
- Працюють: **Bybit** (OHLCV/OI/book+trades, головне джерело), **OKX** (фолбек),
  **BingX** (публічні OHLCV + приватний book через ключі з .env).
- **ccxt.pro публічний WS (book+trades) працює БЕЗ ключа** на Bybit/OKX. BingX WS
  для book/trades вимагає ключі (беруться з .env через dotenv, НЕ хардкодити).
- **Історичного L2-book (снепів стакану в минулому) НЕМАЄ** ні в ccxt, ні безплатно.
  Рішення: self-collection живого book+тrades через WS у файл, потім бектест на ньому.
- Річні OHLCV (8760 1h-свічок): пагінація fetch_ohlcv по `since` (ccxt ~1000/запит),
  диск-кеш у runtime/cache/. Bybit дає.
- Деталі: references/data_sources.md

## ДИСЦИПЛІНА: ВЕРИФІКУЙ, НЕ ДОВІРЯЙ ЗВІТУ КОДЕРА (критично!)
Кодер (Codex/Claude Code) може видати красивий звіт із цифрами, яких НЕМАЄ у файлах.
Це траплялось: кодер заявив "bridge підвищує win-rate до 94-96%", але у
runtime/orderflow_calibration.json було H1=0.2%, H2=33%, H3=n=0. Цифри вигадані.
ЗАВЖДИ перевіряй фактами після кожної видачі кодера:
1. `pytest tools/ -q` — тести зелені? (кількість має збігатись із заявою)
2. Прочитай РЕАЛЬНИЙ вихідний файл (calibration.json / jsonl) — чи там справді ті цифри?
3. Перевір розмір/діапазон дат реального датасету (wc -l, timestamps) — чи це рік, чи 444 рядки?
4. Якщо цифри у звіті ≠ файлам → ВИПРАВ скіл фактами, не мовчи.
5. НІЯКИХ вигаданих даних. Малий n (<50) = "edge не виміряний", не "сигнал працює".

## ДЕЛЕГУВАННЯ КОДЕРУ (робочий патерн Leonid)
Якщо застряг на кодуванні/багу (понад 2-3 спроби) — НЕ гризи далі. Спинись і:
1. Опиши проблему чесно (що зламано, факти з дебагу).
2. Склади детальний CODER_TASK-промпт (шаблон: references/coder_task_template.md):
   Context → Environment/Constraints (venv, Binance blocked, шляхи) → What exists →
   What to do (нумеровані блоки) → Acceptance criteria (жорсткі: реальні дані,
   n≥50, hit≥0.75, ≥2 режими, тести зелені) → Output format → Commands.
3. Віддай кодеру (Codex CLI / Claude Code / кодер юзера). Сам перевір результати
   за дисципліною вище.
   Шаблон промпту: **references/coder_task_template.md**
Leonid прямо сказав: "якщо завдання важке — опиши проблему та склади промпт,
кодер швидко все запрограмує". Це пріоритетний шлях для важкого імплементування.

## PAPER-TEST СИНТЕЗ (без ордерів)
Комбінуй індикатори + карту ліквідацій на ЖИВИХ даних BingX → короткий план.
Модуль: tools/papertest.py (запуск: `.venv/bin/python3 -m tools.papertest --symbol BTC/USDT:USDT`).
Логіка: enrich(df) → bias; build_heatmap(ohlcv) → _extract_zones(grid[:,-1],...) →
зони ≤2%; синтез: найближча зона = магніт (LONG_LIQ→SHORT сетап, SHORT_LIQ→LONG).
Ордери НЕ виконуються. Стакан (orderflow bridge) ще не інтегровано — наступний крок.

## МОНІТОРИНГ ЗБОРУ ДАНИХ (коли колектор у фоні)
Leonid: "тримай на контролі збір даних". Перевіряй періодично:
- `df -h /home/layman` — вільно місце (325ГБ зазвичай; ~2.7 МБ/хв потік book+trades)
- `ls -la runtime/orderflow_raw/*.jsonl` — файл росте?
- `ps aux | grep orderflow.collector` — процес живий?
- Ротація файлів уже реалізована (writer_loop: rotate за часом/розміром, унікальні
  імена через counter) — захист від гігантських файлів і переповнення диска.

## PITFALLS
- Binance недоступний — не пиши до нього. Bybit/OKX/BingX.
- Не escape-ити лапки як \" у patch для .py (tool кидає escape-drift).
- ccxt не має __version__ — це нормально, не падай на перевірці.
- Малий n = не робити заяв. Завжди друкуй n поряд з hit_rate.
- "Найсильніша зона (intensity 1.0)" НЕ означає найвпевненіший сигнал — intensity
  немонотонна (PAVA-калібратор це виправляє, див. liq-zone-trading).
- Класичні індикатори поодинці — НЕ сигнал. Карта ліквідацій (≤1%) — сигнал.
- Завжди верифікуй кодера реальними файлами, не звітом.
