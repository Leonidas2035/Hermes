#!/bin/bash
export PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/home/layman/.local/bin
VENV_PYTHON="/home/layman/.hermes/quantumedge_analysis/venv/bin/python3"
ANALYSIS_SCRIPT="/home/layman/.hermes/quantumedge_analysis/market_analysis.py"

echo "================================================================="
echo " 🧠 HERMES TRADING DNA v3.0 (АВТОНОМНИЙ ТЕРМІНАЛЬНИЙ ЦИКЛ)"
echo "================================================================="
echo "Ініціалізація..."

# 1. Стартова прошивка (Створює нову чисту сесію)
INIT_PROMPT="ІНІЦІАЛІЗАЦІЯ СИСТЕМИ: HERMES TRADING DNA v3.0 (DIRECT EXECUTION MODE)
Ти — Hermes, професійний автономний Quant-трейдер. Ти працюєш у цій активній сесії.
ТВОЇ ПРАВИЛА (HERMES DNA):
1. Коли отримуєш тригер, читай /home/layman/.hermes/quantumedge_analysis/latest.json.
2. Якщо потрібні дії, САМОСТІЙНО виконуй bash-команди: /home/layman/.hermes/quantumedge_analysis/venv/bin/python3 /home/layman/.hermes/quantumedge_analysis/tools/qe_trade.py <subcommand> <args>.
3. BTC ПОЗИЦІЇ: ЗАМОРОЖЕНІ. Не міняти та не торкатися позицій BTC до прямої вказівки власника.
4. XRP LONG: РУЧНЕ КЕРУВАННЯ ВЛАСНИКОМ. Не усереднювати та не торкатися лонгу XRP.
5. XRP SHORT & SOL SWING: ДОЗВОЛЕНО АГРЕСИВНУ ТОРГІВЛЮ з дотриманням 10% подушки вільної маржі.
6. ROI ПОРОГИ: SOL Swing LONG закриття ЛИШЕ при ROI >= 30.0%. XRP Short / DCA закриття при ROI >= 1.5%.
7. Не закривати збиткові позиції по маркету на 100%.
8. Не скасовувати лімітки циклічно, якщо ціна не відхилилася >2%.
Підтверди готовність до роботи."

agy --model "Gemini 3.6 Flash (High)" --dangerously-skip-permissions --add-dir /home/layman/.hermes/quantumedge_analysis --print "$INIT_PROMPT"

echo -e "\n✅ Ініціалізація успішна. Перехід у бойовий цикл (кожні 5 хв)."
echo "Щоб зупинити торгівлю, натисни Ctrl+C."
echo "================================================================="

# 2. Безкінечний цикл
while true; do
    echo -e "\n[$(date +'%H:%M:%S')] 🔄 Оновлення ринкової аналітики..."
    $VENV_PYTHON $ANALYSIS_SCRIPT > /dev/null 2>&1
    
    TRIGGER="[СИСТЕМНИЙ ТРИГЕР 5m CYCLE]: Дані оновлено. Проаналізуй /home/layman/.hermes/quantumedge_analysis/latest.json. Застосуй правила Hermes DNA. Якщо потрібні зміни — виконай bash-команди через qe_trade.py. Якщо ні — відповідай '[HOLD] Аналіз прийнято'."
    
    # Прапорець -c (--continue) підтягує пам'ять з першого кроку
    agy -c --model "Gemini 3.6 Flash (High)" --dangerously-skip-permissions --add-dir /home/layman/.hermes/quantumedge_analysis --print "$TRIGGER"
    
    echo -e "\n⏳ Очікування наступного циклу (5 хвилин)..."
    sleep 300
done
