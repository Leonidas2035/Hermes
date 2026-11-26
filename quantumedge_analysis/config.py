"""
QuantumEdge Trading System - Configuration & Strategy Definitions
Path: /home/layman/.hermes/quantumedge_analysis/config.py
"""

ASSET_STRATEGIES = {
    "BTC": {
        "strategy": "ACTIVE",
        "description": "BTC Long target adjusted to 66000",
        "min_roi": 0.05,
        "mode": "ACTIVE",
    },
    "XRP": {
        "strategy": "ISOLATED_50X_XRP_PING_PONG_SCALP",
        "description": "50x High Leverage Isolated Bi-Directional Ping-Pong Scalp with 1000.0 VST Max Margin Cap",
        "leverage": 50,
        "max_allocated_margin_vst": 1000.0,
        "max_notional_volume_vst": 50000.0,
        "min_roi": 0.020,  # 2.0% minimum ROI target
        "mode": "ACTIVE",
    },
    "SOL": {
        "strategy": "ACTIVE_BI_DIRECTIONAL_HEDGE",
        "description": "Full automated bi-directional swing/scalp trading",
        "min_roi": 0.15,  # lowered to 15.0% ROI for target adjustment
        "mode": "ACTIVE",
    },
    "ETH": {
        "strategy": "ACTIVE_BI_DIRECTIONAL_HEDGE",
        "description": "50x High Leverage Isolated Bi-Directional Scalp/Swing with 1448.50 VST Compounded Margin Cap",
        "leverage": 50,
        "max_allocated_margin_vst": 1448.5,
        "max_notional_volume_vst": 75000.0,
        "min_roi": 0.015,  # 1.5% minimum ROI target
        "mode": "ACTIVE",
    },
}

GLOBAL_LIMITS = {
    "MIN_FREE_MARGIN_PCT": 0.20,  # Enforce 20%+ minimum free margin buffer (currently 42.7%)
    "MAX_PARTIAL_LOSS_REDUCTION_PCT": 0.50,  # 50% position size cap enforced
    "ENABLE_BI_DIRECTIONAL_HEDGING": True,  # Full Long & Short Hedge Mode active
    "HEDGE_DELTA_NEUTRAL_TARGET_PCT": 1.0,  # 1:1 Long:Short ratio target
    "RE_HEDGE_ORDERBOOK_WALL_SNAP": True,  # Snap counter-hedge orders to Orderbook Bid/Ask walls
}
