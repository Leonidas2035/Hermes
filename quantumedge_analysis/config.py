"""
QuantumEdge Trading System - Configuration & Strategy Definitions
Path: /home/layman/.hermes/quantumedge_analysis/config.py
"""

ASSET_STRATEGIES = {
    "XRP": {
        "strategy": "DCA_RECOVERY",
        "description": "Limit grid execution and DCA recovery",
        "min_roi": 0.015,  # 1.5% ROI
        "type": "DCA",
    },
    "SOL": {
        "strategy": "SWING",
        "description": "Trend holding swing trading",
        "min_roi": 0.30,  # 30.0% ROI
        "type": "SWING",
    },
    "BTC": {
        "strategy": "HYBRID",
        "description": "Hybrid DCA + Scalp",
        "min_roi": 0.015,  # 1.5% ROI
        "type": "HYBRID",
    },
}

GLOBAL_LIMITS = {
    "MIN_FREE_MARGIN_PCT": 0.10,  # 10% minimum free margin
    "MAX_PARTIAL_LOSS_REDUCTION_PCT": 0.50,  # Max 50% qty reduction when uPnL < 0
}
