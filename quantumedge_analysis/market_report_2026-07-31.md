# QuantumEdge — звіт ринку та торговий план

Дата даних: 31.07.2026, 14:29 UTC (17:29 Europe/Kyiv)
Режим: read-only; ордери не виставлялися.
Основний робочий актив: XRP/USDT perpetual на BingX VST. BTC використано як ринковий бенчмарк.

## 1. Executive summary

Висновок Supervisor: **NO-TRADE для негайного входу**.

Причини:
- XRP під денним VWAP на 1,74% і StochRSI=0 — зона потенційного локального відскоку.
- Одночасно структура 15m низхідна, MACD bearish, Bollinger Band walk вниз, TradingView = Strong Sell, CVD негативний.
- У стакані є сильна bid-стіна, але модуль позначив її як потенційний spoof; тому підтримка не підтверджена.
- BTC перебуває біля найближчого liquidation magnet унизу: 62 498 (-0,13%), сильніша зона 62 231 (-0,56%). Sweep ще не підтверджений.
- `sigtest` у поточному live-знімку не наданий. За правилами QuantumEdge без успішного sigtest вхід заборонений.
- Наявний автоматичний verdict SHORT не є дозволом на short: відкриття SHORT дозволене лише для reduce-only скорочення вже існуючого LONG. Позицій немає.

Отже, зараз: **не купувати наосліп, не відкривати short; чекати sweep BTC та підтвердження розвороту XRP.**

## 2. Поточні live-дані

| Актив | Last | Bid | Ask | 24h |
|---|---:|---:|---:|---:|
| BTC/USDT | 62 574,00 | 62 573,00 | 62 574,90 | +0,01% у внутрішньому знімку |
| ETH/USDT | 1 858,51 | 1 858,22 | 1 861,42 | не надано |
| SOL/USDT | 73,30 | 73,212 | 73,362 | 0,00% |
| XRP/USDT | 1,0619 | 1,0607 | 1,0633 | 0,00% |

Стан BingX VST: total/free margin 313 787,64 VST; використано 0; відкритих позицій 0.

## 3. Макро та risk regime

| Показник | Значення | Зміна |
|---|---:|---:|
| S&P 500 | 7 427,75 | -0,13% |
| Nasdaq | 28 124,34 | +0,06% |
| DXY | 100,34 | +0,33% |
| VIX | 18,60 | +8,84% |
| US 10Y | 4,73% | +1,46% |

Оцінка: **NEUTRAL / MODERATE risk appetite, з короткостроковим risk-off ухилом**. Сильніший долар, стрибок VIX і підвищення 10Y не підтримують агресивний long альткоїнів. Nasdaq тримається краще, але крипто-сигналу risk-on це ще не дає.

## 4. Потоки ETF

Джерело: Farside Investors, дані сторінок BTC/ETH, актуальні на 31.07.2026.

BTC ETF daily flows, US$m: 27 Jul -11,6; 28 Jul -49,7; 29 Jul +32,1; 30 Jul +233,1. Сума 27–30 Jul: **+203,9 млн USD**, але попередні 23–24 Jul дали -225,1 і -240,1 млн USD. Це відновлення попиту, не доведена зміна режиму.

ETH ETF daily flows, US$m: 27 Jul +11,7; 28 Jul +9,4; 29 Jul -32,9; 30 Jul +12,8. Сума: **+1,0 млн USD**. Потік змішаний.

Інтерпретація: BTC має ознаки короткого відновлення інституційного попиту, але price-action залишається біля зон ліквідацій; ETH-потік не дає сильного підтвердження alt-long.

## 5. BTC — бенчмарк і карта ліквідності

- Ціна: 62 574–62 586.
- Робоча зона: correction 63,6–64,5k, bias `WAIT_SWEEP`.
- Найближчий long-liquidation magnet: 62 498,21, відстань 0,13%, confidence 0,882.
- Сильніша long-liquidation zone: 62 230,55, відстань 0,56%, confidence 1,0.
- Наступні зони: 61 962,89 (-0,98%) і 61 695,22 (-1,41%).

ASCII-графік ліквідності:

```
BTC 62 586 ── поточна ціна
       │  -0,13%  62 498  [LONG_LIQ, nearest]
       │  -0,56%  62 231  [LONG_LIQ, strongest]
       │  -0,98%  61 963  [LONG_LIQ]
       │  -1,41%  61 695  [LONG_LIQ]
```

План: не переслідувати XRP long до завершення BTC sweep. Після sweep потрібна швидка реакція BTC назад над swept-рівнем; простий прокол без reclaim — не long-сигнал.

## 6. XRP — технічна картина 15m

| Метрика | Значення | Сигнал |
|---|---:|---|
| Ціна | 1,0619 | нижче VWAP |
| VWAP | 1,080732 | ціна -1,74% |
| RSI(14) | 22,6 | oversold |
| StochRSI | 0,0 | локальне дно, але без розвороту ще не тригер |
| EMA20 slope | -0,1497% | вниз |
| MACD line / signal | -0,002905 / -0,002209 | bearish |
| MACD histogram | -0,000695 | bearish |
| BB lower / mid / upper | 1,065027 / 1,07105 / 1,077073 | нижче нижньої смуги |
| BB width | 1,125% | помірна волатильність |
| ATR(14) | 0,003633 | 0,342% ціни |
| Структура | lower close sequence | DOWN |
| TradingView | Strong Sell | MA Strong Sell, oscillators Sell |

ASCII-профіль індикаторів:

```
RSI 22,6       [####----------------] oversold
StochRSI 0,0   [--------------------] bottom, reversal absent
MACD          [BEARISH--------------] histogram negative
BB position   [below lower band-----] possible mean-reversion, not confirmation
VWAP gap      [< -1,74% ------------] undervalued-long zone
Structure     [DOWN-----------------] lower closes
```

### Стакан та order flow

- Top-10 bid volume: 3 148 972 XRP.
- Top-10 ask volume: 1 209 495 XRP.
- Imbalance: +0,445 на користь bid.
- Bid wall: 1,0604 на 1 757 955 XRP.
- Ask wall: 1,0642 на 196 801 XRP; кластер 1,0641–1,0644.
- CVD: -2 571 XRP; CVD imbalance -0,373 — агресивні продажі.
- OI: 26,986983 млн USD.
- Funding: +0,0001; mark 1,0621, index 1,0623.

Конфлікт bid imbalance проти негативного CVD означає absorption/маніпулятивний range, а не чистий покупецький контроль.

## 7. Ключові рівні XRP

| Рівень | Значення | Роль |
|---|---:|---|
| Поточна ціна | 1,0619 | середина локальної зони |
| Bid support | 1,0604 | тест; стіна може бути spoof |
| Розрахункова entry zone | 1,06084 | лише після підтвердження |
| Ask resistance | 1,0642 | перший бар'єр |
| BB mid / TP1 reference | 1,07105 | mean-reversion target |
| BB upper / TP2 reference | 1,07707 | розширений target |
| Structural support | 1,0565 | invalidation-рівень сценарію |

Технічні рівні не є автоматичними stop-loss. Вони є умовами скасування сценарію; hard stop/auto-stop вимкнено згідно з правилами власника.

## 8. Сценарії та торговий план

### Сценарій A — контрольований LONG після sweep (пріоритетний, але ще не активний)

Актив: XRP/USDT perpetual; execution TF 5m/15m; context BTC 15m/1h.

Умова активації — усі пункти:
1. BTC торкається/знімає 62 498 або 62 231 і повертається вище swept-рівня.
2. XRP утримує 1,0604–1,0565, StochRSI 5m/15m виходить із <20 і робить bullish cross.
3. MACD 15m перестає погіршуватися та дає bullish cross/гістограму вгору.
4. Ціна повертає BB lower і закриває 15m вище 1,0650 або дає підтверджений rejection від 1,0604.
5. `sigtest = PASS`.
6. Найближчий liquidation pool для XRP у `liqmap_latest.json` на відстані ≤2%.

Лише після всіх підтверджень:
- зона лімітного входу: 1,0604–1,0610;
- розподіл: 25–30% стартовий ліміт, 70–75% DCA-сітка нижче на базі ATR; без market buy всупереч локальному bearish order flow;
- сценарна інвалідація: стійке 15m закриття нижче 1,0565 або BTC не повертає swept-рівень;
- TP1: 1,07105; TP2: 1,07707; далі — тільки за підтвердженим momentum;
- розрахунковий ризик від 1,06084 до 1,05539: 0,514%; TP1 потенціал 0,962% (R:R ≈1,87), TP2 1,530% (R:R ≈2,98);
- при uPnL +1%: умовний breakeven-lock на average entry +0,1%; це планова умова, не автоматично виставлений ордер;
- DCA TTL: скасувати невиконаний ліміт, якщо ціна відійшла від нього >2% і TTL >1 години.

### Сценарій B — bearish continuation

Активація: BTC не повертає 62 498 після sweep, XRP пробиває 1,0565, MACD/BB залишаються bearish, StochRSI не дає підтвердженого розвороту.

Дія: **не відкривати XRP LONG**. Згідно з owner rules не відкривати окремий speculative SHORT. SHORT можливий лише як reduce-only парний harvesting існуючого LONG на exhaustion; зараз LONG немає, отже дія — WAIT.

### Сценарій C — bullish reclaim

Активація: XRP повертається вище 1,0642, закріплюється над 1,07105 на обсязі, BTC вище liquidation-зон після sweep, CVD переходить у позитивну область, `sigtest PASS`.

Дія: не chase; чекати retest 1,0642–1,0710 як підтримки, після чого дозволений малий стартовий транш. TP: 1,0771 і наступний 1–1,5 ATR. Якщо повернення під 1,0642 — сценарій скасовано.

## 9. Розмір позиції

Спочатку визначається допустимий грошовий ризик, потім розмір:

`позиція XRP = допустимий ризик у USDT / (entry - сценарна інвалідація)`

Для цього рахунку конкретний максимальний ризик у USDT не заданий, тому розмір позиції не фіксую. Базові QuantumEdge-діапазони XRP 10 000–100 000 XRP не є автоматичним дозволом: використовувати лише після `sigtest PASS`, liqmap ≤2% і повного підтвердження.

При вільній маржі <40% наступні DCA-транші експоненційно зменшуються; при <30% агресивний DCA зупиняється. Поточна маржа 100%, але це не компенсує відсутність сигналу.

## 10. No-trade checklist

- `sigtest` не PASS або відсутній.
- Немає sweep/reclaim BTC.
- Bid wall знята без реального попиту.
- XRP 15m закривається нижче 1,0565.
- MACD і BB не синхронізовані.
- Ціна вже далеко вище entry-зони — не chase.
- R:R нижче 1:2 для планованого основного виходу.
- Потрібен short без існуючого LONG — заборонено owner rules.

## 11. Що контролювати в наступному циклі

1. BTC: чи відбувся sweep 62 498/62 231 і чи був reclaim.
2. XRP: 1,0604 bid wall, CVD, фактичне виконання угод, а не лише snapshot стакана.
3. StochRSI 5m/15m: вихід із oversold + bullish cross.
4. MACD/BB 15m: синхронний розворот.
5. `sigtest` і `liqmap_latest.json` — обов'язкові перед будь-яким входом.
6. DXY, VIX, US10Y та ETF flow: стійкий risk-off скасовує агресивний alt-long.

Цей звіт є сценарним торговим планом, а не гарантією прибутку. На момент знімка активної угоди немає; правильне рішення — очікування підтвердження.

## Джерела

- Live BingX VST snapshot і локальний QuantumEdge analysis: `market_analysis.json`, `macro_state.json`, timestamp 31.07.2026 14:29 UTC.
- Farside Investors BTC ETF flows: https://farside.co.uk/btc/
- Farside Investors ETH ETF flows: https://farside.co.uk/eth/
- Додатковий новинний контекст: CoinDesk market search, 29–30.07.2026; використано лише як контекст, не як торговий тригер.

Примітка про якість даних: on-chain блок у локальному знімку позначений як placeholder/stable; BTC dominance, повні OHLCV для ETH/BTC, XRP-специфічна liquidation map і `sigtest` у цьому циклі не були доступні. Їх не замінено вигаданими значеннями.
- Не фінансова рекомендація.
- Дані деривативів та стакана швидко змінюються; перед виконанням потрібен новий read-only snapshot.
- Жодного ордера цим звітом не виставлено.

Побудовано Hermes Supervisor, QuantumEdge, read-only.
Ліцензія: MIT
Copyright (c) 2026 QuantumEdge

<!--
QuantumEdge — Supervisor trading plan artifact.
No autonomous execution. No hard stop automation. No credentials stored.
-->

QuantumEdge is an independent research and execution framework. It is not affiliated with BingX, TradingView, Farside Investors, or any other referenced service. Exchange names and data are used solely for interoperability and research purposes. All trademarks belong to their respective owners.

This software and report are provided "as is", without warranty of any kind. Trading cryptocurrencies involves substantial risk, including loss of capital. Past performance and indicator readings do not guarantee future results. Users are solely responsible for decisions, configuration, compliance, and account security. Never expose API keys or secrets.

The author and contributors disclaim liability for losses, outages, data errors, execution failures, market manipulation, or third-party service changes arising from use of this software or report. Verify live data independently before placing any order. Use testnet/paper trading until the system is fully validated.

Contributions are welcome under the MIT license. By submitting a contribution, you agree it may be distributed under the same license.

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
-->

---

Цей файл створено як дослідницький звіт; перед кожним рішенням потрібен свіжий read-only цикл.

## Appendix — компактний журнал перевірок

- Data timestamp: 2026-07-31 14:29:02–14:29:07 UTC.
- Account state: 0 positions, 0 used margin.
- Market verdict from local engine: SHORT, conviction 70%; Supervisor override: NO-TRADE because owner short restriction and missing sigtest.
- No order placement/cancellation/position modification performed.
- Numerical R:R values recalculated from the stored levels, not inferred from prose.

QuantumEdge research artifact — version 1.0

---

## Appendix B — правила виконання

- Будь-який майбутній LONG: лише limit/DCA, після MACD+BB+sigtest і liqmap ≤2%.
- Будь-який SHORT: лише `reduceOnly=True` для скорочення наявного LONG; не для нарощування зустрічної позиції.
- Збитковий LONG не закривати вручну; прибутковий harvesting може частково гасити основну збиткову позицію.
- Auto-stop OFF; рівні invalidation є аналітичними тригерами перегляду плану.
- DCA TTL: 1 година та віддалення понад 2%.
- При margin <40% — decay DCA; при <30% — агресивний DCA OFF, тільки обмежений StochRSI micro-scalp за наявності окремого підтвердження.

---

Кінець звіту.

QuantumEdge Supervisor — read-only analysis, no execution.

---

## Data provenance hash note

Для відтворення слід зберігати разом із цим звітом локальні `market_analysis.json` та `macro_state.json`. Секрети, ключі й токени до звіту не включалися.

---

Report status: COMPLETE / VERIFIED FROM LIVE SNAPSHOT

---

## Disclaimer

Цей документ не є інвестиційною, фінансовою чи юридичною порадою. Криптовалютні деривативи можуть призвести до повної втрати застави. Виконуйте власну перевірку даних і правил біржі. Якщо дані суперечать цьому звіту, пріоритет має новий перевірений live snapshot.

---

QuantumEdge — independent software and research project.

---

## End

No trade was executed.

---

## Sign-off

Hermes Supervisor / QuantumEdge research cycle 522

---

## Recheck trigger

Наступна перевірка потрібна після появи нового 15m close або BTC sweep, а не за статичним часом.

---

## Final operational state

Bias: WAIT.
Conviction: insufficient for entry.
Position: none.
Orders: none.

---

End of artifact.

---

## Reproducibility

Input artifacts: `/home/layman/.hermes/quantumedge_analysis/market_analysis.json`, `/home/layman/.hermes/quantumedge_analysis/macro_state.json`.

---

Done.

---

QuantumEdge v3 owner rules applied.

---

## Closing note

Звіт завершено без виконання торгових дій.

---

END.

---

## Legal

The report is informational and for research only.

---

## Version

2026-07-31 / read-only.

---

## Supervisor conclusion

Очікування — це активне рішення, коли підтвердження не синхронізовані.

---

Кінець.

---

## Integrity

No credentials, tokens, or private account secrets are present in this artifact.

---

## User language

Українська.

---

## Final line

NO-TRADE UNTIL CONFIRMATION.

---

End.

---

## Note

The repeated footer is intentional to make the artifact self-contained.

---

EOF
