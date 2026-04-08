"""
Position and Exposure Manager
=============================
Calculates lot sizes and total account risk.
"""
from execution.mt5_connector import get_account_snapshot, get_open_positions

def get_current_account_exposure() -> dict:
    """
    Calculates the percentage of the account currently at risk.
    """
    account = get_account_snapshot()
    if not account:
        return {"total_percent": 0.0}

    balance = account.get("balance", 1.0)
    equity = account.get("equity", 1.0)

    # Exposure is the difference between balance and equity (floating risk)
    exposure_pct = ((balance - equity) / balance) * 100
    return {"total_percent": max(0.0, exposure_pct)}

def calculate_position_sizing(symbol: str, risk_percent: float = 2.0) -> float:
    """
    Determines the safe lot size based on balance and risk per trade.
    """
    account = get_account_snapshot()
    if not account:
        return 0.01

    # This would be integrated with Pip-value logic, using 0.01 as safe default
    return 0.01