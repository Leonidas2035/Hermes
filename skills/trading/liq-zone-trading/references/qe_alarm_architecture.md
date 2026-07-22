# QE АРХІТЕКТУРА (оновлено 2026-07-21)

## МІСТО Watchdog → чат (замість автономних кронів)

Стара проблема: крони `02c3d45bd603` (5хв) + `8ea10dca157c` (15хв) торгували
САМІ через `trader.py` і скорочували лонг без Hermes — порушення волі власника.

### Нова архітектура (працює):
1. **Watchdog** (hermes3:8b Q5_K_M на RTX4060, systemd user-unit `watchdog.service`)
   — лише ПИШЕ `runtime/watchdog_signal.json` + LLM-аналіз ринку.
   НЕ торгує. After=ollama.service (стартує ПІСЛЯ Ollama).
2. **Ollama** — systemd user-unit `ollama.service` (enabled+active), автостарт
   після reboot. `Environment=LD_LIBRARY_PATH=/home/layman/.local/lib/ollama` + `HOME=/home/layman`.
3. **Будильник `258abcced588`** (every 5m, `deliver=local`) — прокидає Hermes У ЧАТІ.
   Hermes САМ читає snapshot + watchdog_signal + викликає agy і торгує через qe_trade.py.
   Це і є міст Watchdog→чат.

### ЧОМУ deliver=local (не origin/Telegram):
Якщо deliver=origin — звіт іде в Telegram → Telegram-Hermes бачить його і
САМ починає торгувати → ДВІ СЕСІЇ паралельно (колізія ордерів/позицій).
`deliver=local` — Hermes у чаті веде все сам, без Telegram-паралелі.

### Логіка будильника (активний режим, варіант А):
- Контроль-сторож: читати `trade_journal.jsonl` — якщо збиткове закриття
  (realized_pnl<0) = порушення #1; чужі дії = скасувати (cancel_all).
- Кожен цикл: snapshot XRP + BTC (`MARKET_DATA_SYMBOLS=BTCUSDT qe_trade.py`).
- agy ОБОВ'ЯЗКОВО кожні 15хв (або при vol_spike / US-сесії) — НЕ лише [SILENT].
- Browser Use (TradingView) — для глибокого аналізу при сумнівах.
- Після кожного ордера — snapshot, перевір legs/open_orders (BingX hedge-mode іноді бреше про success).

### ФАКТ-ЧЕК (не на слово):
- `systemctl --user is-active ollama.service watchdog.service` — обидва active.
- `cronjob list` — старі крони PAUSED, будильник enabled.
- `qe_trade.py snapshot` — реальний стан позиції (НЕ calibration.json!).
- `trade_journal.jsonl` — ДОКАЗ закриттів (realized_pnl).
