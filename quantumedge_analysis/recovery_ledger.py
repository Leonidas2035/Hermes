"""
QuantumEdge Trading System - Recovery Ledger Manager
Path: /home/layman/.hermes/quantumedge_analysis/recovery_ledger.py
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from config import ASSET_STRATEGIES

LEDGER_PATH = Path("/home/layman/.hermes/quantumedge_analysis/runtime/recovery_ledger.json")

def load_ledger() -> dict:
    if not LEDGER_PATH.exists():
        return {}
    try:
        with open(LEDGER_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_ledger(data: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "w") as f:
        json.dump(data, f, indent=2)

def record_partial_loss(symbol: str, realized_loss_usd: float) -> dict:
    """Record positive USD amount representing loss to be recovered for symbol."""
    ledger = load_ledger()
    symbol_base = symbol.upper().replace("/USDT:USDT", "").replace("USDT", "").replace(":", "").strip()
    if symbol_base not in ledger:
        ledger[symbol_base] = {"accumulated_loss": 0.0, "records": []}
    
    loss_amount = abs(float(realized_loss_usd))
    ledger[symbol_base]["accumulated_loss"] += loss_amount
    ledger[symbol_base]["records"].append({
        "loss_usd": loss_amount,
        "ts": datetime.now(timezone.utc).isoformat()
    })
    save_ledger(ledger)
    return ledger[symbol_base]

def get_accumulated_loss(symbol: str) -> float:
    ledger = load_ledger()
    symbol_base = symbol.upper().replace("/USDT:USDT", "").replace("USDT", "").replace(":", "").strip()
    return float(ledger.get(symbol_base, {}).get("accumulated_loss", 0.0))

def clear_accumulated_loss(symbol: str) -> None:
    ledger = load_ledger()
    symbol_base = symbol.upper().replace("/USDT:USDT", "").replace("USDT", "").replace(":", "").strip()
    if symbol_base in ledger:
        ledger[symbol_base]["accumulated_loss"] = 0.0
        save_ledger(ledger)

def get_recovery_target(symbol: str, entry_price: float, current_size: float, side: str = "LONG", leverage: float = 50.0) -> dict:
    symbol_base = symbol.upper().replace("/USDT:USDT", "").replace("USDT", "").replace(":", "").strip()
    accumulated_loss = get_accumulated_loss(symbol_base)
    strat = ASSET_STRATEGIES.get(symbol_base, {"min_roi": 0.015})
    min_roi = strat["min_roi"]
    
    if current_size <= 0 or entry_price <= 0:
        return {"accumulated_loss": accumulated_loss, "tp_price": entry_price, "target_pnl": 0.0}
    
    initial_margin = (entry_price * current_size) / max(leverage, 1.0)
    target_pnl = accumulated_loss + (initial_margin * min_roi)
    
    delta_price = target_pnl / current_size
    if side.upper() == "LONG":
        tp_price = entry_price + delta_price
    else:
        tp_price = entry_price - delta_price
        
    return {
        "symbol": symbol_base,
        "side": side.upper(),
        "accumulated_loss": round(accumulated_loss, 4),
        "entry_price": round(entry_price, 4),
        "current_size": round(current_size, 4),
        "min_roi": min_roi,
        "target_pnl": round(target_pnl, 4),
        "tp_price": round(tp_price, 4)
    }
