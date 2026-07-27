#!/bin/bash
export PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/home/layman/.local/bin
VENV_PYTHON="/home/layman/.hermes/quantumedge_analysis/venv/bin/python3"
ANALYSIS_SCRIPT="/home/layman/.hermes/quantumedge_analysis/market_analysis.py"
LOG_FILE="/home/layman/.hermes/quantumedge_analysis/cron_agy.log"

# Оновлюємо аналітику (без виводу в консоль)
$VENV_PYTHON $ANALYSIS_SCRIPT > /dev/null 2>&1

# Формуємо тригер
PROMPT="[СИСТЕМНИЙ ТРИГЕР 5m CYCLE]: Дані оновлено. Проаналізуй /home/layman/.hermes/quantumedge_analysis/runtime/latest.json. Застосуй Hermes DNA. Якщо потрібні зміни — самостійно виконай bash-команди через qe_trade.py. Якщо дій не потрібно — відповідай '[HOLD]'. Нічого не виводь зайвого."

# Фоновий запуск AGY зі спільним ID сесії (записує контекст у SQLite)
agy --model "Gemini 3.6 Flash (High)" --conversation "hermes_live_01" --dangerously-skip-permissions --add-dir /home/layman/.hermes/quantumedge_analysis --print "$PROMPT" >> "$LOG_FILE" 2>&1
