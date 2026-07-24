# QuantumEdge — Дистиляція сесії та Пам'ять системи (Оновлено 2026-07-23)

## 📌 ПОТОЧНИЙ РЕЖИМ І АРХІТЕКТУРА ТОРГІВЛІ
- **Основний Виконавчий контур:** Автономний 5-хвилинний системний Linux Crontab (`*/5 * * * *`).
- **Скрипт-Оркестратор:** `/home/layman/.hermes/quantumedge_analysis/cron_15m_agy.sh` -> `trader.py`.
- **Головний AI Мозок (AGY):** Antigravity CLI з моделлю **`Gemini 3.6 Flash (High)`** (прямий виклик `agy --model "Gemini 3.6 Flash (High)"`).
- **Hermes Gateway:** Вимкнений/призупинений. Вся торгівля переведена на Antigravity AGY з прямою відправкою звітів у Telegram.
- **Пам'ять (Memory Persistence):** Функція `get_recent_actions()` підтягує останні 5 дій з `trader_journal.jsonl`, що повністю ліквідувало "амнезію" та зациклені заміни ордерів.

---

## 📋 ОНОВЛЕНИЙ МАНІФЕСТ ТРАНСФОРМАЦІЇ (HERMES TRADING DNA v3.0)
Збережено у `/home/layman/.hermes/SOUL.md`:
1. **VWAP & StochRSI:** 
   - **VWAP:** Фіксація справедливої ціни. Набір LONG суворо пріоритетний у зону уцінки (`Price < VWAP`).
   - **StochRSI (5m/15m):** Снайперський виклик екстремумів (<20 для дна, >80 для вершини) для розстановки DCA та скальпінгу.
2. **Min ROI Gate (SOL):**
   - Заборонено передчасний panic-close позиції SOL LONG по маркету за дрібний прибуток. Мінімальний поріг закриття в мікро-скальпі: **>= +1.5% ROI per trade**. Тейк-профіти виставляються на рівнях **$79.10** та **$80.30**.
3. **BingX Protection & Harvesting:**
   - Жодна збиткова позиція не закривається повністю в мінус (Rule #1).
   - Скорочення збиткових ног здійснюється лише через парний харвест із прибутку протилежної legs + `reduceOnly=True` для запобігання помилок 101209/109400.
4. **Drawdown Micro-Scalping (Rule #4):**
   - При просадках вільна маржа (ліміт вільної маржі = 10%) задіюється під бліц-скальпи за сигналами StochRSI, а прибуток йде на відкушування основного мінуса.

---

## 📊 СТАН АКАУНТА ТА ПОЗИЦІЙ (Станом на 2026-07-23 14:30 EEST)
- **Баланс (BingX VST):** Total `~566,500 VST` | Free `~84,600 VST` (15% free margin buffer).
- **XRP LONG:** `912,417 XRP` @ `1.1501` (mark `1.1352`, uPnL `-13,621 VST`).
- **XRP SHORT (Harvest):** `611,928 XRP` @ `1.1352` (uPnL `+30 VST`). Частково виконано TP-ордер на 300,000 XRP @ `1.1365`.
- **SOL LONG:** Серія DCA-ордерів із цільовими ТР на **$79.10** та **$80.30**.
- **BTC Context:** Торгується біля **$65,745**. Магніт шорт-ліквідацій знаходиться на **$66,978 (+1.89%)**, що готує імпульс вгору на US-сесії.

---

## 📁 КЛЮЧОВІ ФАЙЛИ ТА ШЛЯХИ
- `FULL_SYSTEM_CONTEXT.txt`: `/home/layman/.hermes/quantumedge_analysis/FULL_SYSTEM_CONTEXT.txt`
- `SOUL.md` (Маніфест v3.0): `/home/layman/.hermes/SOUL.md`
- `Торговий план`: `/home/layman/.hermes/quantumedge_analysis/runtime/trader_plan.md`
- `Стартовий промпт`: `/home/layman/Desktop/START_TRADING_PROMPT.md`
- `Код оркестрації`: `/home/layman/.hermes/quantumedge_analysis/trader.py`
- `Код індикаторів`: `/home/layman/.hermes/quantumedge_analysis/indicators.py`
