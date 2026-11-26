#!/bin/bash
set -o pipefail
export PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/home/layman/.local/bin
VENV_PYTHON="/home/layman/.hermes/quantumedge_analysis/venv/bin/python3"
PROJECT="/home/layman/.hermes/quantumedge_analysis"
ANALYSIS_SCRIPT="$PROJECT/market_analysis.py"
RUNTIME_SNAPSHOT="$PROJECT/runtime/live_snapshot.json"
RUNTIME_JOURNAL="$PROJECT/runtime/trade_journal.jsonl"
QETRADE="$PROJECT/tools/qe_trade.py"
CYCLE_INTERVAL=300
RETRY_SLEEP=15

echo "================================================================="
echo " 🧠 HERMES TRADING DNA v3.0 (CONTROLLED 24/7 LOOP)"
echo "================================================================="
echo "Проєкт: $PROJECT"
echo "Цикл: $CYCLE_INTERVAL sec"
echo "Журнал: $RUNTIME_JOURNAL"
echo "Своп-файл снимка: $RUNTIME_SNAPSHOT"

ensure_snapshot() {
    if [ ! -s "$RUNTIME_SNAPSHOT" ]; then
        echo "[snapshot] initial snapshot..."
        $VENV_PYTHON "$QETRADE" snapshot > "$RUNTIME_SNAPSHOT" 2>&1 || true
    fi
}

append_context_marker() {
    local cycle_ts
    cycle_ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[cycle] $cycle_ts start" >> "$RUNTIME_JOURNAL"
}

write_cycle_marker() {
    local outcome="$1"
    local cycle_ts
    cycle_ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[cycle] $cycle_ts $outcome" >> "$RUNTIME_JOURNAL"
}

safe_qe() {
    local cmd="$1"
    shift
    local out
    out=$($VENV_PYTHON "$QETRADE" $cmd "$@" 2>&1) || true
    echo "$out"
}

# 1. Стартова прошивка
INIT_PROMPT="ІНІЦІАЛІЗАЦІЯ СИСТЕМИ: HERMES TRADING DNA v3.0 (CONTROLLED EXECUTION MODE)
Ти — Hermes, професійний автономний Quant-трейдер. Ти працюєш у цій активній сесії.
ТВОЇ ПРАВИЛА (HERMES DNA):
1. Можливі індикатори: MACD, BB, RSI, ATR, OBV, VWAP, StochRSI, ADX. Додаткові сигнали не вигадуй.
2. Використовуй реальні дані біржі, НЕ моделі з paper_trader_loop.
3. BTC: ЗАМОРОЖЕНІ. Tолько моніторинг.
4. XRP LONG: без агресивного відкриття нових лонгів без попереднього узгодження з планом.
5. Виконуй тільки дозволені qe_trade.py команди: snapshot, place, market, cancel, cancel_all, modify_sl, trades, grid.
6. Не закривати збиткові позиції по маркету на 100%.
7. Перш ніж ставити ордер, перевір у runtime/trade_journal.jsonl останні угоди і уникни конфліктів.
8. Якщо ринок не дає чіткого сигналу — [HOLD].
Дай коротке підтвердження готовності. Потім цикл продовжиться автоматично."

echo -e "\n[init] Запуск ініціалізаційного агента..."
agy --model "Gemini 3.6 Flash (High)" --dangerously-skip-permissions --add-dir "$PROJECT" --print "$INIT_PROMPT"

ensure_snapshot
append_context_marker
echo -e "\n✅ Ініціалізація успішна. Перехід у бойовий цикл."
echo "Щоб зупинити торгівлю, натисни Ctrl+C."
echo "================================================================="

# 2. Безкінечний контрольований цикл
while true; do
    cycle_start_rc=0
    echo -e "\n[$(date +'%H:%M:%S')] 🔄 Оновлення ринкової аналітики..."
    if ! $VENV_PYTHON "$ANALYSIS_SCRIPT" > /dev/null 2>&1; then
        echo "[warn] market_analysis.py failed, retry after $RETRY_SLEEP s"
        sleep "$RETRY_SLEEP"
        continue
    fi

    if [ -f "$PROJECT/latest.json" ]; then
        cp -f "$PROJECT/latest.json" "$PROJECT/runtime/latest_cycle.json" 2>/dev/null || true
    fi
    ensure_snapshot

    TRIGGER="[СИСТЕМНИЙ ТРИГЕР 5m CYCLE]: Дані оновлено. Використовуй:
1) $PROJECT/latest.json
2) $PROJECT/runtime/live_snapshot.json для стану ордерів/позицій
3) $PROJECT/runtime/trade_journal.jsonl для контексту попередніх угод
Застосуй правила Hermes DNA. За потреби виконуй дії через $VENV_PYTHON $QETRADE. Якщо дію не потрібно — відповідай '[HOLD] Аналіз прийнято'."

    if ! agy -c --model "Gemini 3.6 Flash (High)" --dangerously-skip-permissions --add-dir "$PROJECT" --print "$TRIGGER"; then
        cycle_start_rc=1
        echo "[warn] agent cycle failed, retry after $RETRY_SLEEP s"
        sleep "$RETRY_SLEEP"
        continue
    fi

    echo -e "\n⏳ Очікування наступного циклу (${CYCLE_INTERVAL} sec)..."
    sleep "$CYCLE_INTERVAL"
done
