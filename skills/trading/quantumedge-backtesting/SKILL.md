---
name: quantumedge-backtesting
description: "Build statistically-calibrated trading signals on REAL QuantumEdge market data (BTC/XRP). Covers data sourcing reality (Binance blocked, Bybit/OKX/ccxt.pro, self-collected order flow), walk-forward no-lookahead backtest, multi-regime and distance-bucket calibration, PAVA monotonic calibration, and the CRITICAL rule: verify every coder deliverable with real tool calls because coder reports contain fabricated numbers. Use whenever Leonid asks to build/calibrate/validate any signal, zone, indicator combo, or order-flow detector for QuantumEdge."
---

# QuantumEdge — Backtesting & Signal Calibration Methodology

Класовий метод побудови торгових сигналів на РЕАЛЬНИХ даних QuantumEdge.
Це "як робити" для будь-якого сигналу (зони ліквідацій, індикатори, order flow).
Специфічні сигнали — у під-скілах: liq-zone-trading, indicator-signal-backtest,
orderflow-manipulation. Тут — СПІЛЬНА методологія + найважливіший pitfall.

## ГОЛОВНЕ ПРАВИЛО (виношене з досвіду — читай уважно)
**НІКОЛИ не вір звіту кодера на слово. Перевіряй фактами.**
У цій сесії кодер ДВІЧІ видавав вигадані цифри:
- "Bridge підвищує win-rate до 94-96%" — у calibration.json ЦЬОГО НЕ БУЛО (там
  H1=0.2%, H2=33%, H3=n=0, H4=n=1).
- "~55-58% на spoofing/imbalance" — реально 0.2% і 33%.
Кодер переніс ОЧІКУВАНІ числа з синтетики у звіт про реальність.
ПЕРЕД тим як сказати "готово", зроби:
1. `pytest tools/ -q` — тести зелені? (кодер може сказати "25/25", але прожени сам)
2. Прочитай calibration/out JSON — чи там СПРАВДІ ті цифри, що у звіті?
3. Перевір розмір/діапазон дат реального датасету (wc -l, timestamps).
4. Якщо звіт каже "edge підтверджено", а файл показує n<50 або hit~випадкове —
   це ХИБНИЙ висновок, виправляй скіл фактами, не копіюй звіт.

## ДЖЕРЕЛА ДАНИХ (реальність, перевірена фактами)
- **Binance ЗАБЛОКОВАНИЙ** (api.binance.com DNS fail) — НЕ використовувати.
- **Bybit** — OHLCV/OI через ccxt.rest; book+trades через ccxt.pro WebSocket
  ПУБЛІЧНО, БЕЗ ключа (перевірено: `bybit apiKey set: False`). Джерело №1.
- **OKX** — фолбек (теж ccxt).
- **BingX** — наша основна біржа (там ключі, там торгує бот). ccxt.pro BingX
  СТРІМИТЬ book+trades З ключами з .env (через dotenv). Перевірено: працює.
  Для чесної фільтрації сигналів НАШОГО бота збирай стакан САМЕ з BingX.
- **ІСТОРИЧНИЙ L2-СТАКАН НЕМАЄ** у ccxt (лише поточний watchOrderBook + історичні
  fetchTrades). Тому order-flow бектест = self-collection живого WS у файл, потім
  бектест на власному датасеті. Безкоштовно і чесно.

## МЕТОДОЛОГІЯ БЕКТЕСТУ (що вимірювати)
1. **Walk-forward, NO-LOOKAHEAD**: карта/індикатори будуються лише з ohlcv[:t];
   майбутнє не використовується. Завжди перевіряй це тестом.
2. **Багатосторінкове завантаження**: ccxt limit ~1000/запит → пагінація по `since`
   для року історії; диск-кеш (runtime/cache/*.json), інвалідуй за віком.
3. **Сегментація режимів**: bull/bear/flat (за нахилом MA200 або HH/HL). Рахуй
   калібрування окремо по кожному — hit-rate не має бути артефактом тренду.
4. **Вимір відстані**: для зон ліквідацій критично — distance_bucket (0-1% / 1-2% /
   2-3% / 3-5% / 5%+). Близькість важливіша за силу (див. підсумок нижче).
5. **PAVA-калібрація** (pool_adjacent_violators) для монотонності: якщо сира
   intensity антикорелює з hit-rate (так і було!), згладжуй ізотонічно →
   `calibrated_confidence` монотонний. Не плутай сиру intensity з ймовірністю.
6. **Критерій надійного сигналу**: hit_rate ≥ 0.75 І n ≥ 50 І стабільно у ≥2 режимах.
   Менший n = не заявляй edge. Завжди друкуй n поряд з hit_rate.

## РЕАЛЬНІ ВИСНОВКИ (рік BTC 1h, Bybit, перевірені)
- **Зони ліквідацій** (liq-zone-trading): близька зона ≤1% торкається у **83-95%**
  за 5 днів (медіана 2-8 год). ≤2%: 78-90%. >2%: ненадійно. ВИРІШАЛЬНИЙ ФАКТОР —
  ВІДСТАНЬ, не intensity. Це найсильніший edge системи.
- **Індикатори поодинці** (indicator-signal-backtest): **НЕМАЄ edge** на BTC 1h —
  47-55% (≈монетка). Лише: bb_break 48h 55.6%, rsi_rev/bb_rev 53% (короткі).
  Наївне голосування осей не допомагає.
- **Order flow** (orderflow-manipulation): на 444 рядках (≈1-2 хв) edge НЕ виміряний
  (H1=0.2%, H2=33%, H3=n=0, H4=n=1). Потрібен self-collection 3-5+ днів.
- **Bridge** (зона + тиск стакана): логіку реалізовано, але цифру "94-96%" НЕ
  підтверджено жодним бектестом — видалено як вигадану.

## ЯК ДЕЛЕГУВАТИ КОДЕРУ (шаблон промпту)
Пиши самодостатній CODER_TASK.md у references/ цільового скіла. Структура —
див. references/coder_prompt_template.md. Ключове: реальні дані тільки; явна заборона
вигаданих цифр; "якщо датасету нема → чесно 'edge не виміряний'"; критерії приймання
з порогами; формат звіту українською.

## Див. також
- references/coder_prompt_template.md — доведений шаблон промпту для кодера
- references/data_sourcing.md — деталі мережі/ccxt/ccxt.pro/dotenv
- liq-zone-trading, indicator-signal-backtest, orderflow-manipulation — специфічні сигнали
