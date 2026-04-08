"""
Order Validation Helpers
"""

def calculate_risk_reward_for_trade(entry: float, sl: float, tp: float) -> float:
    """
    Calculates the R:R ratio.
    """
    risk = abs(entry - sl)
    reward = abs(tp - entry)

    if risk == 0:
        return 0.0
    return reward / risk