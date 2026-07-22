# CODER TASK — Smart Stop-Loss для QuantumEdge (trader.py)

## Контекст
Файл: `/home/layman/.hermes/quantumedge_analysis/trader.py` (execution-мозок автономного
крона QE Trader 5m, `752701ce6015`). Торгуємо XRP/USDT на BingX VST, hedge-mode, 10x.
Власник (Leonid) ПІДТВЕРДИВ авто-трейлінг/SL: потрібен стоп-лосс у breakeven (без збитку),
щоб при дампі не залазити в мінус. Але поточний алгоритм має БАГ і тупий (плоский BE).
Треба: (1) прибрати баг стекінгу SL, (2) замінити на РОЗУМНИЙ алгоритм SL.

## БАГ (що ламається зараз)
Функція `trail_to_breakeven(snap, price, ...)` (рядки ~163-197) кожен 5-хв цикл робить:
```python
res = qe(["modify_sl", leg["side"].upper(), str(round(new_sl, 4))])
```
і НЕ скасовує попередній SL. На BingX VST hedge-mode `qe_trade.py modify_sl` (через ccxt)
НЕ оновлює існуючий SL, а створює новий stop-market ордер (відома пастка:
`edit_position` не існує на `ccxt.bingx`; `reduceOnly` у hedge-mode відхиляється з
`109400 "In the Hedge mode, the 'ReduceOnly' field can not be filled."`). Результат:
за кілька годин накопичилось 15 дубль-SL ордерів на повний розмір позиції (898,145),
всі `sell market @1.1216` — стекінг. `cancel_all` у qe_trade.py теж має баг (ігнорується
BingX без positionSide), тому чистити довелось по ID.

## ЩО ЗРОБИТИ

### 1. Прибрати баг стекінгу
Перед виставленням НОВОГО SL — завжди спочатку скасувати старий SL-ордер цієї ж ноги.
Робочий патерн для BingX hedge-mode (перевірено):
- зняти старий SL: `qe(["cancel_sl", LEG])/` або через qe_trade.py `cancel <id>` із
  попереднім пошуком ID SL-ордера у `snapshot()["open_orders"]` (штрих: SL = stop-market
  ордер на закриття позиції, side протилежний нозі, type market/stop).
- потім виставити новий: `qe(["modify_sl", "LONG", str(new_sl)])` (qe_trade.py саме
  робить `create_order(... params={"stopLossPrice": X, "positionSide":"LONG"})` БЕЗ
  reduceOnly — це працює, див. references/bingx_stop_loss_modify.md).
- ГАРАНТУВАТИ ідемпотентність: якщо новий SL == старий (той самий new_sl), НЕ робити
  cancel+place (не спамити біржу кожен цикл).

### 2. Розумний алгоритм SL (замість плоского BE)
Нова функція `smart_stop_loss(snap, price, indicators, atr_pct, book)` має:
- **Вхід**: лише для ПРОФІТНОЇ ноги (uPnL>0), як і зараз.
- **Базовий рівень**: breakeven + крихта на фандинг/комісію (entry*1.0005 для long),
  але НЕ нижче. Це мінімум ("без збитку").
- **Трейлінг по ATR/ціні**: якщо ціна пішла далі від entry на >= `trail_trigger`
  (напр. 0.3% або ~1 ATR), рухати SL услід за ціною, тримаючи дистанцію
  `trail_dist` (напр. 0.4–0.6% або 1.2 ATR) — класичний parabolic trail.
  `new_sl = price * (1 - trail_dist)` для long.
- **Захист від спуфінгу/HIGH-manipulation**: якщо `indicators["manipulation"]=="HIGH"`
  і conviction низька — не рухати SL (тримати BE, не ловити вилам).
- **Індикаторний стоп-вихід (не переносити SL, а сигналити вихід)**: якщо long і
  (RSI>70 ТА MACD_hist<0) АБО ціна пробила нижній стек-вол (book bid_walls) — це
  розворот → SL має стояти агресивніше (ближче до ціни, напр. entry*1.0005 без трейлу),
  щоб зафіксувати профіт до дампу.
- **Не ловити геп/вілу**: SL ставити з запасом від entry (не впритул), щоб
  короткий викид ліквідності не знімав позицію в нуль (страхування гепу власника).
- **Логування**: кожен реальний cancel/place писати у `jlog` (як зараз TRAIL_BE),
  із зазначенням чому (BE / trail / manip-hold / reversal-tighten).

### 3. Налаштування (константи у верху файлу)
- `TRAIL_TRIGGER_PCT = 0.3`
- `TRAIL_DIST_PCT = 0.5`
- `BE_PROFIT_PCT = 0.05` (крихта на фандинг/комісію)
- `SL_TIGHTEN_ON_REVERSAL = True`

## ВИМОГИ ДО КОДЕРА
- Не чіпати оркестратор/бот (/home/layman/QuantumEdge), лише
  `/home/layman/.hermes/quantumedge_analysis/trader.py`.
- Зберегти всі існуючі lock-правила власника: #1 не закривати збиткові (SL ставити
  тільки коли в профіті, ніколи не нижче entry мінус запас), #5 авто-стоп вимк —
  SL тут = трейлінг-страховка, не hard stop ризик-менеджменту.
- `decide_and_act` має викликати нову `smart_stop_loss` замість `trail_to_breakeven`
  (рядок ~262 `trail_actions = trail_to_breakeven(...)`).
- Перевірити СПРАВЖНІМ запуском (не лише синтаксисом): після правки
  `cd ~/.hermes/quantumedge_analysis && ~/QuantumEdge/.venv/bin/python3 trader.py`
  і перевірити `qe_trade.py snapshot` → має бути РІВНО 1 SL-ордер на ногу, не стос.
- НЕ завищувати цифри у звіті — показати реальний snapshot open_orders_count==1.

## Довідка
- references/bingx_stop_loss_modify.md (у цьому ж skill-каталозі) — робочий патерн
  modify_sl для hedge-mode.
- Поточний баг у журналі: /home/layman/QuantumEdge/runtime/trade_journal.jsonl
  (серія modify_sl 2026-07-21 11:14→12:11, 10+ записів; стос 15 SL у snapshot).
- `qe_trade.py` CLI: `snapshot | modify_sl <LONG|SHORT> <price> | cancel <id> |
  cancel_all` (cancel_all має баг без positionSide — краще cancel по ID).
