# QuantumEdge — Дистиляція сесії (для відновлення після reboot)
Дата: 2026-07-22 ~09:50 EEST

## РЕЖИМ (ГОЛОВНЕ)
- ТОРГУЄМО НАЖИВО. Всі 3 крони PAUSED: 258abcced588 (будильник), 02c3d45bd603, 8ea10dca157c.
- Причина: cron-сесія = "мозок з амнезією" (нова сесія Hermes без контексту розмови, читає лише сухий промпт → торгує шаблонно, метушиться). Живий діалог (з повним контекстом + Tencent/hy3 + факт-чек) торгує якісніше.
- НЕ вмикати крони без явної команди власника.

## ПІДСУМОК НІЧНОЇ АВТОНОМІЇ (урок)
- Будильник за ніч: 51 дія (place 22, cancel 24, modify_sl 5), close = 0.
- Реалізований профіт за ніч = 0 (біржа: `qe_trade.py trades 12` → realized_pnl 0.0).
- Приріст балансу 576k→654k = НЕ прибуток, а рух equity (uPnL short + маржа), паперовий.
- Висновок: багато метушні, нуль фіксації. Автономний cron у режимі активного трейдера працює гірше.

## ПОЗИЦІЯ (на момент дистиляції)
- LONG 700 002 @1.1594, uPnL ~ -19 000 (глибоко в мінусі, XRP впав)
- SHORT 350 000 @1.1316, uPnL ~ -200 (майже BE)
- Баланс: total ~654k / free ~250k / used(маржа) ~404k
- XRP ~1.1316, BTC(BingX) ~65 914
- Відкриті ордери: sell 350k@1.16, sell 350k@1.163 (long TP), buy 150k@1.125, buy 200k@1.113 (long DCA/short TP)

## КАРТА ЛІКВІДАЦІЙ (свіжа, BTC, ціна 65916)
- ВГОРУ (шорт-ліквідації, магніти): 67074 (int 1.0, +1.78% НАЙСИЛЬНІШИЙ), 67536 (0.90), 67882 (0.60)
- ВНИЗУ (лонг-ліквідації): 65691 (0.36, -0.32%), 65345 (0.45, -0.85%)
- Читання: сильніший магніт ВГОРУ → ставка на відскок, але можливий стоп-хант вниз (65345) спершу.
- XRP стакан: підтримка bid-стіна 1.1285-1.1291 (~1.4M XRP, міцна), опір ask 1.134-1.1349 (~1M). Imbalance -0.143.
- Індикатори XRP: RSI 32.9 (BEARISH/перепроданий), MACD BEARISH, BB_pos 0.12 (біля нижньої).

## ТОРГОВІ ІДЕЇ (обговорені, НЕ виконані — чекають команди)
1. ГОЛОВНА: карта=магніт вгору 67074 + RSI перепроданий → відскок. Тримати long 700k, short як страховка; при відбої від 1.1285 фіксувати short у профіт, long відпливає з мінусу.
2. СКАЛЬП дна: long 100-150k @1.1285-1.1290 (bid-стіна) TP 1.134 (ask) — реальний профіт, покриває просадку long.
3. DCA long: при проколі до 1.125-1.128 долив 150k (ордер buy 150k@1.125 вже стоїть) — знизити середню.
4. SHORT-харвест: якщо XRP пробиває 1.1285 вниз → short 350k у профіт, фіксувати (rule #2).
- РЕКОМЕНДАЦІЯ: тримати long (rule#1), скальп-long від 1.1285, short тримати як страховку.

## ВІДКЛАДЕНЕ ЗАВДАННЯ
- Написати сильний SOUL.md (~/.hermes/SOUL.md зараз порожній/дефолтний) — трейдерська ДНК QuantumEdge: правила власника, читання ліквідацій/стакану, дисципліна (менше метушні, якісні входи). Щоб будь-яка сесія стартувала "трейдером", а не чистим аркушем.

## ІНСТРУМЕНТИ (перевірені)
- BTC ціна з BingX: `cd /home/layman/QuantumEdge && MARKET_DATA_SYMBOLS=BTCUSDT .venv/bin/python3 tools/qe_trade.py snapshot` → mark_price. (НЕ Kraken/CoinGecko.)
- Realized PnL: `.venv/bin/python3 tools/qe_trade.py trades <hours>`
- Liqmap build (хардкодить BTC): `cd /home/layman/QuantumEdge && .venv/bin/python3 -m tools.liqmap.cli build --tf 1h --limit 500` → runtime/liqmap_latest.json + liqmap_dashboard.html
- Індикатори: `cd /home/layman/.hermes/quantumedge_analysis && /home/layman/QuantumEdge/.venv/bin/python3 analysis.py` → latest.json
- Browser Use працює (TradingView скрейп OK).
- agy: `/home/layman/.local/bin/agy --dangerously-skip-permissions --effort high --add-dir /home/layman/QuantumEdge --add-dir /home/layman/.hermes/quantumedge_analysis --print "<промпт>"`
- Ollama: systemd user-unit (автостарт після reboot; перевірити `systemctl --user is-active ollama.service` після reboot).

## ПІСЛЯ REBOOT — ПЕРШІ КРОКИ
1. Перевірити Ollama: `systemctl --user is-active ollama.service` (для watchdog, якщо треба).
2. snapshot XRP + BTC(BingX) + свіжий liqmap + analysis.py.
3. Порівняти позицію з цим файлом (long 700k, short 350k мали лишитись — ордери на біржі живуть після reboot).
4. Крони ЗАЛИШАЮТЬСЯ paused (торгуємо наживо), доки власник не скаже інакше.
5. Чекати команду власника по торговій ідеї.
