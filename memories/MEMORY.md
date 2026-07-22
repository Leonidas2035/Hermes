Користувач має персональний HFT-проєкт QuantumEdge, який повністю мігровано в контур Hermes за шляхом /home/layman/.hermes/quantumedge_analysis/ (оркестратор + боти: AI Scalper, DynDCA, LockBotBTC; MarketDataHub, SupervisorAgent, QuestDB). Роль агента — Orchestrator/Supervisor (аналіз ринку, торговий план, ризик-контроль, делегування до agy).
§
TG-ЗВІТИ QE(258): ТІЛЬКИ по рухах позицій/ордерів (place/market/modify_sl/cancel). Формат: 1-2 рядки: дія/символ/сторона/розмір/ціна; закриття+PnL+баланс. Без оглядів/пояснень. Нема угоди → [SILENT]. Leonid вимагає граничної стислості для економії токенів.
§
ДЕЛЕГУВАННЯ КОДЕРУ (agy/Codex): Для модифікації коду, тестів або дебагу збоїв запускай agy: `agy --print "Опис завдання" --dangerously-skip-permissions`. Обов'язково перевіряй результати (cronjob list, pgrep, config.yaml, dumps ~/.hermes/sessions/).
§
ТЕХНІЧНИЙ ОПЕРАЦІЙНИЙ КОНТЕКСТ: Будильник 258abcced588 (5m, deliver=local) запускає автономну клон-сесію Hermes без пам'яті. Розрахунок PnL вести тільки за фактичними угодами через `qe_trade.py trades` (а не за equity). За потреби перевизначити BTC: `MARKET_DATA_SYMBOLS=BTCUSDT qe_trade.py`. Директиви власника виконувати миттєво.
§
КОНТРОЛЬ ЗБИТКОВИХ ПОЗИЦІЙ: У режимі сторожа постійно звіряти trade_journal.jsonl на наявність несанкціонованих або збиткових угод. Посадка не є приводом для паніки при великому балансі та далекій ліквідації.
§
QE РЕЖИМ (2026-07-22, ЧИННИЙ): Контур повністю самодостатній та мігрований у /home/layman/.hermes/quantumedge_analysis/. Написано сильний SOUL.md із трейдерською ДНК. Усі виклики торгівлі делегуються 2T+ моделі Antigravity через `agy`. Локальні крони та будильники наразі PAUSED — запуск та керування здійснюються у чаті з факт-чеком. Дистиляція гілки: /home/layman/.hermes/quantumedge_analysis/SESSION_DISTILL.md — читати ПЕРШИМ після reboot.