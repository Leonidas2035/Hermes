# QuantumEdge — AGY ↔ Trader Wiring (знання від 2026-07-27)

Контур повністю мігровано в `/home/layman/.hermes/quantumedge_analysis/`
(НЕ в `/home/layman/QuantumEdge` — старий шлях у доках застарів).

## Архітектура зв'язку (data flow)
```
market_data.py + indicators.py
   -> market_analysis.py  (пише latest.json + market_analysis.json у КОРІНЬ каталогу)
   -> trader.py  ← ЄДИНЕ легітимне ядро прийняття рішень
        ├─ qe_trade.py snapshot  (баланс, маржа, позиції)
        ├─ trader_journal.jsonl  (пам'ять останніх 5 дій)
        ├─ будує промпт (HERMES DNA v4.0) -> agy CLI --print
        ├─ regex-парс ```json блоку -> список команд
        ├─ виконує кожну через tools/qe_trade.py (з hardware guardrails)
        └─ HTML-звіт у Telegram
```

`trader.py::decide_and_act()` — ключова функція. Викликає:
`agy --model "Gemini 3.6 Flash (High)" --dangerously-skip-permissions --print <prompt>`
Потім `re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response)` → JSON-масив команд
`[["place"|"market"|"cancel", ...]]`, кожну передає у `qe([action]+args)`.

## Типові режими РОЗРИВУ зв'язку (перевіряти за цим чек-листом)
1. **Живий цикл не викликає trader.py.** `hermes_self_cycle.sh` може крутити
   лише read-only (market_analysis + qe_trade snapshot + mtf.py) → система в режимі
   "пасивний спостерігач", AGY не викликається, ордерів нема. Фікс: підключити
   `trader.py` як оркестратор у тіло циклу (5m loop).
2. **Помилка шляху latest.json.** Скрипти крону (cron_5m_agy_shared.sh) можуть
   посилатися на `runtime/latest.json`, якого НЕ ІСНУЄ — `market_analysis.save()`
   пише `latest.json` у КОРІНЬ. Фікс: шлях → root `latest.json`.
3. **Дрейф версій ДНК.** Промпт trader.py міг мати зашиту HERMES DNA v3.0, тоді як
   аналіз (market_analysis.py, HERMES_DISTILLED_SOUL.md, START_TRADING_PROMPT.md) —
   v4.0. Директиви v4.0, які МУСЯТЬ бути в промпті AGY:
   - Margin<10% free → жорсткий MARGIN LOCK (лише reduceOnly / cancel, НЕ нові позиції).
   - 5m StochRSI <20 = bottom entry; >80 = top exit / short-scalp.
   - SOL swing ROI ≥ +30.0%; XRP/BTC DCA/Scalp ROI ≥ +1.5%.
   - BTC FROZEN; XRP long manual (не чіпати), XRP short scalp при перегріві.
   - Заборона 100% закриття збиткової позиції (uPnL<0); макс 50% частково.
4. **Блукаючий agy-процес** (--dangerously-skip-permissions, не прив'язаний до циклу)
   → ризик дублювання ордерів. Перед kill -9 спершу з'ясувати джерело (ppid-ланцюг,
   логи ~/.gemini/antigravity-cli/).

## Прийом: попросити сам AGY зробити READ-ONLY аудит кодової бази
Скласти промпт із strict constraints (жодних змін файлів, жодних qe_trade
place/market/cancel, жодних kill процесів) і передати через `agy --print`.
AGY повертає: mermaid data-flow + діагностику розриву + покроковий план wiring.
Зразок промпту: `/tmp/agy_audit_prompt.md` (збережено в сесії 2026-07-27).
Виклик:
```
agy --model "Gemini 3.6 Flash (High)" --dangerously-skip-permissions \
  --add-dir /home/layman/.hermes/quantumedge_analysis --print "$(cat /tmp/agy_audit_prompt.md)"
```

## Ad-hoc верифікація зміни промпту (БЕЗ реальних ордерів)
Мокнути `trader.qe` і `subprocess.run`, прогнати `decide_and_act(fake_report, state)`
із фейковим звітом. Ствердження:
- промпт містить "HERMES TRADING DNA v4.0 NATIVE" (не v3.0);
- присутні BTC FROZEN MODE / XRP SHORT SCALP / SOL ROI≥30%;
- margin-гілка: free 5% → "MARGIN LOCK ACTIVE"; free 25% → "Free margin OK";
- AGY повернув `[]` → decision HOLD; реальних trade-qe_calls не було (лише snapshot).
Зразок скрипта: `/tmp/hermes-verify-trader-wiring.py` (hermes-verify- префікс).
Користувач БЛОКУЄ `rm` та `python3 -c` one-liners — писати файл-верифікатор у /tmp.

## Чого НЕ робити без прямої команди власника (режим QE)
- Не підключати автономну торгівлю (не міняти hermes_self_cycle.sh на виклик trader.py
  і не запускати його) без явного "старт".
- Не зупиняти блукаючі процеси (kill) без з'ясування джерела.
- Не редагувати .env / креденшіали напряму.
