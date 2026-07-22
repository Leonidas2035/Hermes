---
name: lock-unwind
description: Розторговка (unwind) захеджованого дельта-нейтрального "замка" LONG+SHORT у QuantumEdge (BingX VST, XRP) без порушення правил власника. Use when Leonid asks як розторгувати замок / вийти із захеджованої пари / TREND_UNLOCK / нахилити замок за трендом / харвест протилежної ноги. Базується на LockBot DDN (TREND_UNLOCK) + правилах власника.
---

# QuantumEdge — Розторговка замка (Lock Unwind / TREND_UNLOCK)

"Замок" = дельта-нейтральна пара: LONG ≈ SHORT за розміром, нетто-дельта ~0.
Ставиться при високому ризику (правило #4: хедж+чекати). Мета розторговки —
вийти з мінуса, коли зʼявляється прогнозований тренд, НЕ порушуючи правила власника.

## ⚠️ ГОЛОВНА МАТЕМАТИКА (перевіряй ПЕРШОЮ — часто рятує від збитку)
Заморожений PnL замка = (SHORT_entry − LONG_entry) × size.
- Якщо LONG_entry > SHORT_entry (як буває після хедж-добору на хаях) → спред
  ВІДʼЄМНИЙ → **парне закриття рівних обсягів фіксує ЗБИТОК** на будь-якій ціні.
  Приклад (2026-07-21): LONG 700k@1.1502 + SHORT 700k@1.1442 → спред −0.006/unit
  → парний харвест = −4200 VST ГАРАНТОВАНО. Це ПАСТКА, не роби так.
- Нетто uPnL замерзає і НЕ рухається, поки ноги рівні (плюс однієї = мінус іншої).
Висновок: доки ноги рівні — «харвест парою» тут збитковий. Розторговувати треба
через НАХИЛ книги, а не парне закриття.

## ПРАВИЛЬНИЙ TREND_UNLOCK (без порушення правил власника)
Ідея з LockBot DDN профілю `trend` (band ±0.2 замість ±0.05): при сильному тренді
розширюємо коридор — тримаємо ногу ЗА трендом, протилежну поступово фіксуємо.
Адаптація під правила власника (#1 не закривати збиткові; #2 скорочувати збиткову
лише прибутком протилежної):

1. **ПІДТВЕРДИ ТРЕНД** (не вгадуй): композит XRP (див. нижче) має бути сильний в один
   бік (|score|≥60), imbalance у той самий бік, liq-магніти по курсу тренду. Спитай agy
   про макро/новини/BTC (стійкий тренд vs пастка на хаях). Розторговуй ЛИШЕ на підтвердженні.
2. **НАХИЛ через добір ноги ЗА трендом** (правило #3: тренд→добір). Тренд вгору →
   добираємо LONG ринком/лімітом → книга стає НЕТТО-ЛОНГ → заробляємо на русі, жодну
   збиткову ногу НЕ чіпаємо. Тренд вниз (і SHORT має room) — навпаки. УВАГА: SHORT
   часто впертий у ліміт нотіоналу (code 101209) → нарощувати не можна, лише LONG-бік.
3. **ЛІМІТИ (священні):** LONG ≤1M нотіоналу (правило #7). Порахуй: (LONG_size+добір)
   × mark ≤ 1_000_000. SHORT НЕ нарощувати понад план (правило #6, room за 101209).
4. **ХАРВЕСТ протилежної НА РІВНЯХ** (правило #2): коли рух дав профіт нахиленій нозі,
   зрізай збиткову ногу ЧАСТИНАМИ на liq-магнітах / стінках стакану — але тільки якщо
   реалізований профіт нахилу ПОКРИВАЄ фіксацію збитку (інакше знову пастка спреду).
5. **ЗАХИСТ / RE-LOCK (правило #4):** трейл захисного SL по нозі-за-трендом уздовж
   15m/1h EMA. Якщо тренд зламався (imbalance перевернувся, ціна нижче ключової EMA) →
   НЕГАЙНО віднови нейтраль 1:1 (дорівняй ноги) і чекай.

## ПОСЛІДОВНІСТЬ ДІЙ (щоцикл при відкритому замку)
1. `cd /home/layman/QuantumEdge && .venv/bin/python3 tools/qe_trade.py snapshot`
   → зчитай legs (size/entry/uPnL обох ніг), mark, imbalance, session, free-маржу.
2. Порахуй спред замка (SHORT_entry − LONG_entry) → зрозумій, чи парне закриття збиткове.
3. Композит XRP (сильний напрям?):
   `python -c "import sys; sys.path.insert(0,'/home/layman/QuantumEdge'); import pandas as pd; from tools.liqmap.datafeed import fetch_ohlcv,fetch_oi_history,fetch_context; from tools.composite_signal.engine import calculate_composite_score; SYM='XRP/USDT:USDT'; o,_=fetch_ohlcv('1h',150,SYM); oi,_=fetch_oi_history('1h',150,SYM); c=fetch_context(SYM); df=pd.DataFrame(o,columns=['t','o','h','l','c','v']); r=calculate_composite_score(df,funding_rate=c.get('funding',0),oi_series=oi,liq_zones=None); print('score',r['score'],'trend',round(r['trend'],1),'mom',round(r['momentum'],1))"`
   (composite CLI хардкодить BTC — для XRP став symbol у виклику, як вище).
4. liq-магніти XRP (де цілі харвесту): build_heatmap із symbol='XRP/USDT:USDT'
   (див. скіл liq-zone-trading; CLI теж хардкодить BTC — будуй inline з потрібним symbol).
5. На 15m/сумніві — **agy** (обовʼязково, його аналітика в основі рішення):
   `/home/layman/.local/bin/agy --dangerously-skip-permissions --effort high --add-dir /home/layman/QuantumEdge --add-dir /home/layman/.hermes/quantumedge_analysis --print "<snapshot+композит+магніти, питання: тренд стійкий чи пастка? розторговувати чи тримати нейтраль? рівні добору/харвесту/трейлу>"`
6. Дій за TREND_UNLOCK вище. Після КОЖНОГО ордеру — re-snapshot, звір legs (правило верифікації).
7. Звіт у TG лише по руху позицій/ордерів (коротко: дія/сторона/розмір/ціна; закриття +PnL+баланс).

## LockBotBtc (референс, НЕ чіпати — рефакторинг дорогий)
Бот `src/quantum_edge_core/lock_bot/` створювався саме для авто-розторговки, але
НЕ налаштований під нас: config/lockbot.yaml → symbol ETHUSDT, біржа Binance Testnet
(не XRP/BingX). Аудит (docs/lockbot_audit.md, docs/zero_trades_diagnostic.md):
- **DDNEngine** (ddn/engine.py) — чиста математика дельти: тримає Net Delta у коридорі
  band_low..band_high навколо target. Профілі: `neutral` (±0.05, харвест/флет),
  `trend` (±0.2, розторговка за трендом). Це і є TREND_UNLOCK.
- Керується ЗЗОВНІ командами Supervisor по ZMQ :5556 (SET_PROFILE, PANIC_LOCK).
  Це чистий safety-гейт БЕЗ автономного циклу → без Supervisor торгує 0 угод.
- Fade за VWAP: шорт на хаях, лонг на лоях відносно денного VWAP.
- PANIC_LOCK: екстрено рівняє дельту при загрозі ліквідації (min_distance_to_liq_bps 200).
Беремо з нього ІДЕЮ (профіль trend = нахил замка за трендом), а не сам код.

## Pitfalls
- НЕ роби парне закриття рівних ніг при відʼємному спреді — гарантований збиток (див. математику).
- composite_signal/cli.py та liqmap/cli.py ХАРДКОДЯТЬ BTC. Для XRP став symbol='XRP/USDT:USDT'
  у виклику fetch_ohlcv/fetch_oi_history/fetch_context/build_heatmap (inline-скрипт).
- SHORT упертий у ліміт нотіоналу (101209) — розторговку робимо через LONG-бік.
- Правило #1 непорушне: збиткову ногу НЕ закривати ринком «щоб вийти». Тільки нахил + харвест профітом.
- Той самий venv: /home/layman/QuantumEdge/.venv/bin/python3.
- Після ордеру ЗАВЖДИ re-snapshot і звір legs (size/бік не перевернувся, нотіонал у лімітах).
- agy кликати через subprocess-масив аргументів, не через shell (промпт містить JSON/спецсимволи).
