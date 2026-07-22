# QuantumEdge — Архітектура агентів (Watchdog → Hermes → agy)

## СХЕМА ВЗАЄМОДІЇ (як має працювати)

```
┌─────────────────────────────────────────────────────────────┐
│ RTX 4060 (локально) — Ollama, hermes3:8b-llama3.1-q5_K_M    │
│                                                               │
│  WATCHDOG AGENT (watchdog.py, автономний цикл 5хв)           │
│   1. qe_trade.py snapshot → позиції/ордери/баланс            │
│   2. fetch_ohlcv 5m (BingX VST) → vol_index (ATR-спайк)      │
│   3. ціна vs попередня → price_move_pct                      │
│   4. розрахунок buffer_pct до ліквідації (вручну)            │
│   5. питає локалку (Ollama) → wake=true/false + reason       │
│   6. ПИШЕ runtime/watchdog_signal.json                       │
│   ⚠ НЕ крон Hermes — автономний процес на ПК (while True).  │
└───────────────────────────┬─────────────────────────────────┘
                              │ пише watchdog_signal.json
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ HERMES (hy3, хмара) — ТРЕЙДЕР                                │
│  Крон 5хв: читає watchdog_signal.json                        │
│   • wake=false → поверхневий чек + SILENT                    │
│   • wake=true → діє за типом reason                          │
│  Крон 15хв: широкий збір даних → agy → рішення               │
└───────────────────────────┬─────────────────────────────────┘
                              │ (тільки при wake=true / 15хв)
                              │ детальний промпт із даними
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ agy (Antigravity CLI) — ГЛИБОКИЙ АНАЛІТИК                   │
│  • є інтернет + новини                                       │
│  • будує індикатори, liqmap, прогноз                         │
│  • повертає структурований аналіз + рівні                    │
│  Hermes отримує відповідь → САМ приймає рішення → ордери    │
└─────────────────────────────────────────────────────────────┘
```

## ШЛЯХИ МІЖАГЕНТНОЇ ВЗАЄМОДІЇ

| Файл / інструмент | Хто пише | Хто читає | Призначення |
|---|---|---|---|
| `/home/layman/QuantumEdge/runtime/watchdog_signal.json` | Watchdog (локалка) | Hermes (крон) | Сигнал пробудження: `{"wake":bool,"reason":str,"vol_index":float,"price_move_pct":float,"buffer_pct":float,"note":str,"timestamp_utc":str}` |
| `/home/layman/QuantumEdge/tools/qe_trade.py snapshot` | (CLI) | Watchdog + Hermes | Знімок позицій/ордерів/балансу BingX VST |
| `/home/layman/QuantumEdge/tools/watchdog.py` | (файл) | Watchdog агент | Скрипт моніторингу |
| `/home/layman/QuantumEdge/runtime/trader_plan.md` | Hermes | Hermes + oversight | Поточний план + запасний + тригери |
| `/home/layman/QuantumEdge/runtime/local_analysis.json` | (опц.) analyzer | Hermes | Резервний аналіз локалки |
| `/home/layman/QuantumEdge/runtime/trade_journal.jsonl` | trader.py | Hermes | Журнал дій (PnL, ордери) |
| `/home/layman/.local/bin/agy` | (бінар) | Hermes (виклик) | Antigravity CLI для глибокого аналізу |
| `/home/layman/.hermes/quantumedge_analysis/` | (контур) | Hermes + agy | market_analysis.py, trader.py, indicators.py |

**Ollama endpoint:** `http://localhost:11434/api/generate` (модель `hermes3:8b-llama3.1-q5_K_M`).
**BingX VST:** ключі в `.env` (`BINGX_TESTNET_API_KEY/SECRET`, `USE_TESTNET=true`), symbol `XRP/USDT:USDT`, hedge-mode, 10x.

## ЛОГІКА WATCHDOG (5хв цикл, автономно на 4060)

Watchdog НЕ торгує. Тільки міряє і будить.

Правила `wake=true`:
- `scheduled_5m` → будить Hermes для ПОВЕРХНЕВОГО чеку (кожні 5хв).
- `scheduled_15m` → будить Hermes для ШИРОКОГО аналізу через agy (на 00/15/30/45 хв).
- `vol_spike` → vol_index>0.75 АБО price_move_pct>1.0% → позапланово.
- `liq_alert` → buffer_pct<3.0% → КРИТИЧНО.

Fallback (якщо Ollama впала): математичні правила ті самі → будить за порогами.

## ПРОМПТ ДЛЯ agy (глибокий аналіз, 15хв або vol_spike)

Hermes формує цей промпт із зібраних даних і викликає:
```
/home/layman/.local/bin/agy --dangerously-skip-permissions --effort high \
  --add-dir /home/layman/QuantumEdge \
  --add-dir /home/layman/.hermes/quantumedge_analysis \
  --print "<ПРОМПТ НИЖЧЕ>"
```

**ТЕКСТ ПРОМПТУ (Hermes підставляє реальні дані у {фігурні дужки}):**

```
Проаналізуй ринок BTC/USDT та XRP/USDT на СВІЖИХ даних BingX VST.
Це демо-рахунок QuantumEdge (XRP/USDT, hedge-mode, 10x). Не змінюй нічого на біржі — тільки аналіз + рекомендації.

=== СТАН ПОЗИЦІЙ (qe_trade.py snapshot) ===
{ПОВНИЙ JSON snapshot: mark_price, balance free/used, legs[size/entry/uPnL/lev], open_orders}

=== ІНДИКАТОРИ (збудовані Hermes через ccxt) ===
XRP 1h: RSI={}, MACD line/sig/hist={}, BB[low/mid/up]={}, ATR={}, ATR%={}
XRP 15m: RSI={}, MACD hist={}, BB pos={}
XRP 5m: RSI={}, MACD hist={}
BTC 1h: RSI={}, MACD={}, BB={}, ATR={}

=== ORDER BOOK (XRP) ===
bid_walls={}, ask_walls={}, imbalance={}

=== LIQMAP (runtime/liqmap_latest.json) ===
nearest_short_liq={price, dist%}, strongest_zone={price, intensity}

=== BTC КОНТЕКСТ ===
BTC ціна={}, funding={}, OI={}, зона (63.6-64.5k корекція / >66k пробій / mid)={}

=== НОВИНИ (Google News RSS, останні) ===
{короткий sentiment + заголовки}

=== ЗАВДАННЯ ===
1. Тренд і фаза (1h + 15m): бичаче/ведмеже/нейтрально, чи не перегріте (RSI>70).
2. СИГНАЛИ на вхід/вихід зараз. Врахуй liqmap-магніти (куди тягне ціну).
3. РЕКОМЕНДАЦІЯ для поточної LONG позиції XRP ({size} @ {entry}, uPnL {pnl}):
   тримати / фіксувати частково / повністю закрити? Рівні TP/SL.
4. ЧИ відкривати SHORT (лише якщо індикатори розвернулись) — рівні entry/TP/SL.
   УВАГА: власник дозволяє шорт ЛИШЕ харвест (скорочення існуючого), не нарощування.
5. ПРОГНОЗ на US-сесію (13-21 UTC): напрямок, волатильність, магніти ліквідацій.

ФОРМАТ ВІДПОВІДІ (укр, ≤25 рядків):
- Індикатори+числа
- Сигнали
- Стан позицій
- Рівні (TP/SL long, entry/TP/SL short)
- Прогноз US-сесії
- Висновок: що Hermes має зробити (hold/harvest/close/add)
```

## ЛОГІКА HERMES (крон 5хв, hy3)

```
Читати runtime/watchdog_signal.json:
IF wake == false AND reason == scheduled_5m:
    # поверхневий чек
    cd ~/.hermes/quantumedge_analysis && ~/QuantumEdge/.venv/bin/python3 trader.py
    IF позиція суттєво змінилась (uPnL дріснув >2% / нові ордери):
        короткий звіт 3 рядки
    ELSE: SILENT
IF wake == true:
    IF reason == scheduled_5m (плановий 5хв):
        # поверхневий аналіз + корекція позицій
        snapshot + індикатори 1h/15m/5m (швидко) → підкоригувати SL/грід/харвест
        короткий звіт
    IF reason == scheduled_15m OR vol_spike OR liq_alert:
        # ШИРОКИЙ збір + agy
        зібрати ВСІ дані (snapshot, індикатори, book, liqmap, BTC, новини)
        сформувати промпт → agy --print
        отримати відповідь → проаналізувати
        САМ прийняти рішення → trader.py / qe_trade.py
        детальний звіт (≤15 рядків)
```

## ПРАВИЛА ВЛАСНИКА (священні, для всіх агентів)
1. НЕ закривати збиткові позиції.
2. Збиткову скорочувати ЛИШЕ прибутком протилежної (харвест SHORT у плюсі → ADD_LONG).
3. Індикатори в лонг → добір; рух видихся → фіксація + шорт (шорт НЕ нарощувати).
4. Високий ризик → хедж + чекати.
5. Авто-стоп ВИМКНЕНО (захист через аналіз, не hard stop).
6. Шорт упёрся в ліміт нотіоналу (101209) — шорт ЛИШЕ скорочувати.
7. Лонг ≤1M USDT нотіоналу (room_contracts-гард, не спам 101209).

## ЩО ВПРОВАДИТИ КОДЕРУ

1. **Watchdog як автономний агент (НЕ крон Hermes):** `watchdog.py` запускається як
   постійний процес на ПК (systemd user service / nohup / supervisor), цикл `while True`
   з `time.sleep(300)`. Пише `watchdog_signal.json`. Має авто-рестарт.
2. **Hermes крон 5хв** (вже є, d2cf4bcf694d, hy3) — читає сигнал, торгує, звітує.
3. **Hermes крон 15хв** — для wide-збору + agy (окремий крон АБО той самий 5хв при reason=scheduled_15m).
4. **agy wrapper** у Hermes: виклик `agy --dangerously-skip-permissions --effort high
   --add-dir ... --print "<промпт>"`, парсинг stdout → рішення.
5. **Міст-файли** (див. таблицю шляхів) — єдині точки контакту агентів.

## ПЕРЕВІРКА (verification)
- Watchdog: `python3 tools/watchdog.py` → з'являється watchdog_signal.json з vol_index≠0.
- Hermes 5хв: при wake=true виконує trader.py + (якщо 15хв) викликає agy.
- agy: реальний виклик повертає аналіз із цифрами (не вигаданими).
- Ніяких ордерів без санкції власника у режимі перегляду; у авто-режимі — за правилами #1-7.

## ВІДОМІ ПАСТКИ (не повторювати)
- ccxt 4.5.64: `fetch_ohlcv`/`fetch_ticker` — КОРУТИНИ (await), не sync.
- BingX hedge-mode: `cancel_all` без positionSide ігнорується; SL через
  `create_order(stopLossPrice, positionSide, NO reduceOnly)`.
- `liquidationPrice` на VST = None → рахувати вручну: liq≈entry*(1-0.95/lev).
- Ollama не має інету/новин → глибокий аналіз ТІЛЬКИ через agy.
- 1M USDT кап на ногу → room_contracts-гард перед добором лонгу.
