"""
QuantumEdge Dynamic DCA Strategy Engine (v1.0)
Path: /home/layman/.hermes/quantumedge_analysis/tools/dynamic_dca_engine.py

Integrates dynamic volatility-based grid steps (ATR-scaled), volume multipliers,
and orderbook bid-wall alignment for Hermes & QuantumEdge trading system.
"""

import numpy as np
import pandas as pd

class DynamicDCAEngine:
    def __init__(self, target_roi: float = 0.015, max_safety_orders: int = 4, volume_multiplier: float = 1.35):
        """
        :param target_roi: Minimum net ROI target (1.5% default)
        :param max_safety_orders: Maximum number of DCA averaging tranches
        :param volume_multiplier: Multiplier for consecutive DCA tranche volume
        """
        self.target_roi = target_roi
        self.max_safety_orders = max_safety_orders
        self.volume_multiplier = volume_multiplier

    def calculate_dynamic_steps(self, current_price: float, atr_value: float, top_bids: list = None) -> list:
        """
        Calculates dynamic DCA limit prices based on ATR volatility and orderbook bid walls.
        """
        base_step = max(atr_value * 1.2, current_price * 0.008) # Min 0.8% or 1.2x ATR
        steps = []

        for i in range(1, self.max_safety_orders + 1):
            # Dynamic step expansion formula
            step_distance = base_step * (1.0 + (i - 1) * 0.35)
            target_price = current_price - (step_distance * i)

            # Align with Orderbook Bid Wall if available
            if top_bids:
                closest_bid = min(top_bids, key=lambda b: abs(b[0] - target_price))
                # If bid wall is within 0.5% of target price, snap to bid wall + 0.05%
                if abs(closest_bid[0] - target_price) / target_price <= 0.005:
                    target_price = round(closest_bid[0] * 1.0005, 4)

            steps.append(round(target_price, 4))

        return steps

    def calculate_compounded_entry_and_tp(self, entries_with_qty: list) -> dict:
        """
        Calculates average entry price and dynamic TP level given a list of (qty, price) tuples.
        """
        if not entries_with_qty:
            return {"avg_entry": 0.0, "total_qty": 0.0, "target_tp": 0.0}

        total_notional = sum(qty * price for qty, price in entries_with_qty)
        total_qty = sum(qty for qty, price in entries_with_qty)
        
        if total_qty == 0:
            return {"avg_entry": 0.0, "total_qty": 0.0, "target_tp": 0.0}

        avg_entry = total_notional / total_qty
        
        # Target TP: Average Entry + Target ROI + Fees (0.10%)
        target_tp = avg_entry * (1.0 + self.target_roi + 0.0010)

        return {
            "avg_entry": round(avg_entry, 4),
            "total_qty": round(total_qty, 4),
            "target_tp": round(target_tp, 4)
        }

if __name__ == "__main__":
    dca = DynamicDCAEngine()
    steps = dca.calculate_dynamic_steps(current_price=1887.50, atr_value=12.50)
    print("Calculated Dynamic DCA Grid Steps:", steps)
