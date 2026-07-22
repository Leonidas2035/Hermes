# QuantumEdge Analysis — Hermes Workspace

Папка з ізольованим аналітичним контуром Супервізора.
Створена окремо від проєкту QuantumEdge, щоб НЕ зачіпати робочий код бота,
але використовує ті самі ключі (`.env` проєкту) і ту саму біржу (BingX VST).

## Структура

```
~/.hermes/quantumedge_analysis/
├── indicators.py          # RSI(14), MACD(12,26,9), Bollinger(20,2), ATR(14)
│                           # + trend_score (-3..+3 -> LONG/SHORT/NEUTRAL)
├── market_data.py         # Збір з біржі: klines, funding, OI, стакан, BTC, TV, новини
├── analysis.py            # Агрегація всього -> структурований звіт
├── latest.json            # ОСТАННІЙ звіт (завжди актуальний, для читання агентом)
├── history/               # Архів звітів по таймстемпу (до 200 файлів)
└── README.md
```

## Джерела даних

| Джерело | Що дає | Де |
|---------|--------|-----|
| ccxt.bingx (testnet) | XRP klines 15m, funding, OI, mark, стакан | market_data.py |
| TradingView (Puppeteer) | Технічний рейтинг (osc/MA/rating) | tv_analyzer/tv_parse.js |
| Firecrawl (Free Tier) | Новинний sentiment | FIRECRAWL_API_KEY |
| BTC/USDT | Провідний індикатор + XRP/BTC ratio | market_data.py |

## Запуск

```bash
cd ~/.hermes/quantumedge_analysis
~/QuantumEdge/.venv/bin/python3 analysis.py
```

Результат: оновлює `latest.json` + кладе копію в `history/`.

## Як агент читає дані для рішення

1. Відкрити `latest.json` -> блок `synthesis.final_bias` (LONG/SHORT/NEUTRAL)
   + `confidence` (0..1) + `votes` (скільки джерел за який bias).
2. Деталі в `data.technicals`: RSI zone, MACD state, BB position, ATR%.
3. `data.funding_oi` — фандинг (хто платить), OI (тиск).
4. `data.order_book` — стінки + imbalance (мікроструктура для рівнів входу).
5. `data.btc` — провідний сигнал (корекція/пробій за відео-зонами).
6. `data.tv` / `data.news` — підтвердження/спростування bias.

## Важливо

- Індикатори RSI/MACD/BB/ATR ВИТЯГНУТІ зі старого BTC-пайплайну
  (QuantumEdge/monitor_adjust.py) і ТЕПЕР підключені до XRP-аналізу.
- Не залежить від QuestDB / MarketDataHub daemon — klines беруться
  напряму з біржі. Якщо daemon лежить, аналіз усе одно працює.
- Авто-стоп вимкнено (рішення власника) — захист через цей аналіз + план.
- Звіт НЕ ставить ордери. Тільки дані для рішення Супервізора.
