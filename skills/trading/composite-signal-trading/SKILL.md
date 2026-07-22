---
name: composite-signal-trading
description: Trade QuantumEdge BTC/XRP using the 4+1 Composite Signal Engine. Calculates market score (-100 to +100) and executes trades based on walk-forward calibrated probabilities. Use when Leonid asks to trade by composite indicator signals, evaluate trend/momentum/volatility skews, or calibrate composite thresholds.
---

# QuantumEdge — Торгівля за композитним сигналом (4+1 сигнальні осі)

Цей скіл керує розрахунком та торгівлею за інтегральним індексом ринку **Composite Score (-100...+100)**. 

Індекс комбінує 4 незалежні технічні осі ринку та 1 вісь карти ліквідації, щоб отримати єдину оцінку напрямку та сили руху:
1. **ТРЕНД (EMA Ribbon 9/21/50 + ADX)** — визначає напрям та його силу.
2. **МОМЕНТУМ (MACD + RSI)** — вимірює прискорення ціни та перекупленість/перепроданість.
3. **ВОЛАТИЛЬНІСТЬ (Bollinger Bands + ATR)** — виявляє фазу стиснення (Squeeze) та визначає межі.
4. **ОБ'ЄМ/ПОТІК (OBV + Open Interest + Funding Rate)** — підтверджує рух грошовим потоком та ризиком сквізів.
5. **КАРТА ЛІКВІДАЦІЙ (Liquidation Map Force)** — сила тяжіння найближчих зон-магнітів.

---

## 📊 КАЛІБРУВАЛЬНА ТАБЛИЦЯ (365 днів історії, Bybit, R:R = 1:1, ATR=1.5)
Усі сигнали протестовано за схемою **Walk-Forward (без заглядання в майбутнє)**. Ціль (TP) та стоп-лосс (SL) динамічно масштабуються за волатильністю: **Target = 1.5 * ATR**, **Stop = 1.5 * ATR**. 

*Оскільки R:R = 1:1, математично будь-яка ймовірність >50.0% дає позитивне очікування (прибуткову стратегію).*

### 📈 Результати калібрування (PAVA згладжені):

#### 🐂 Бичачий ринок (Regime BULL):
- **80 to 100 LONG** (Сильний лонг): **61.0%** calibrated_confidence (n=77, медіана відпрацювання 4 год)
- **10 to 80 LONG** (Помірний лонг): **51.7%** calibrated_confidence (n=105..164)
- **SHORT сигнали** (Контр-тренд): **45.3% - 48.3%** calibrated_confidence (не торгувати!)

#### 🐻 Ведмежий ринок (Regime BEAR):
- **-100 to -40 SHORT** (Сильний шорт): **54.6%** calibrated_confidence (n=76..188, медіана 4-5 год)
- **-40 to -10 SHORT** (Помірний шорт): **48.2%** calibrated_confidence (n=141)
- **LONG сигнали** (Контр-тренд): **45.3%** calibrated_confidence (не торгувати!)

#### 🌐 Усі ринки разом (Regime ALL):
- **80 to 100 LONG**: **56.7%** calibrated_confidence (n=120)
- **-100 to -40 SHORT**: **51.2%** calibrated_confidence (n=112..300)

---

## 📈 ПРАКТИЧНІ ПРАВИЛА ТОРГІВЛІ (Composite Signal Rules):
1. **Торгівля за трендом**:
   - В режимі **BULL** торгуємо виключно **LONG** при `Score >= 80` (впевненість **61.0%**).
   - В режимі **BEAR** торгуємо виключно **SHORT** при `Score <= -40` (впевненість **54.6%**).
2. **Фільтр контр-тренду**: Контр-трендові сигнали (наприклад, лонг у ведмежому ринку або шорт у бичачому) мають впевненість менше 50% і повністю ігноруються.
3. **Управління ризиками**: Стоп-лосс та Тейк-профіт виставляються чітко на відстані **1.5 * ATR** від ціни входу.

---

## 💻 КОМАНДИ КЕРУВАННЯ
* **Запуск бектесту та перекалібрування (365 днів історії)**:
  ```bash
  cd /home/layman/QuantumEdge
  .venv/bin/python3 -m tools.composite_signal.backtest --days 365 --horizon 48 --step 6
  ```
* **Розрахунок поточного сигналу та збереження (з lookup впевненості)**:
  ```bash
  .venv/bin/python3 -m tools.composite_signal.cli --tf 1h --limit 150
  ```
* **Запуск тестів**:
  ```bash
  .venv/bin/python3 -m pytest tools/composite_signal/test_composite.py -q
  ```
