"""
Correlation Risk Manager
=======================
Detects when symbols share base or quote currencies to prevent systemic risk.
"""
from execution.mt5_connector import get_open_positions

def get_pair_correlation_risk(symbol: str) -> float:
    """
    Calculates a risk factor (0.0 - 1.0) based on current open positions.
    """
    positions = get_open_positions()
    if not positions:
        return 0.0

    base = symbol[:3]
    quote = symbol[3:6]

    conflicts = 0
    for pos in positions:
        pos_symbol = pos.get('symbol', '')
        if base in pos_symbol or quote in pos_symbol:
            conflicts += 1

    # Penalize risk by 0.2 for every existing correlated pair
    risk = conflicts * 0.2
    return min(1.0, risk)