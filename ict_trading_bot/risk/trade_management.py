def manage_trade(trade, price, market_rhythm=None):
    """
    Dynamically manage an open trade.

    The baseline plan is still 1R -> breakeven, 2R -> partial, 3R -> trail,
    but market rhythm can tighten protection when reversal risk is rising or
    give trend trades a bit more room to run.
    """
    if not trade:
        return None

    risk_distance = abs(float(trade["entry"]) - float(trade["sl"]))
    if risk_distance <= 0:
        return None

    current_r = abs(float(price) - float(trade["entry"])) / risk_distance
    direction = str(trade.get("direction") or "").lower()

    management_plan = {}
    if isinstance(market_rhythm, dict):
        management_plan = market_rhythm.get("management_plan") or {}

    breakeven_r = float(management_plan.get("breakeven_r", 1.0) or 1.0)
    partial_r = float(management_plan.get("partial_r", 2.0) or 2.0)
    trail_r = float(management_plan.get("trail_r", 3.0) or 3.0)
    mode = str(management_plan.get("mode", "balanced") or "balanced")
    reversal_score = float((market_rhythm or {}).get("reversal_score", 0.0) or 0.0)

    # ENHANCED: Protect aggressively if Reversal Risk is high or Displacement is against us
    # ICT Principle: Take profit at the 'Draw on Liquidity'
    if reversal_score >= 70:
        breakeven_r = min(breakeven_r, 0.4) # Move to BE earlier
        partial_r = min(partial_r, 0.8)    # Take partials before the turn
        trail_r = min(trail_r, 1.2)

    if trade.get("stage", 0) == 0 and current_r >= breakeven_r:
        # Move SL to Breakeven + minor buffer to cover commissions
        buffer = 0.05 * risk_distance if mode == "trend" and reversal_score < 60 else 0.01 * risk_distance
        if direction == "buy":
            new_sl = max(float(trade["sl"]), float(trade["entry"]) + buffer)
        else:
            new_sl = min(float(trade["sl"]), float(trade["entry"]) - buffer)
        trade["stage"] = 1
        return {"action": "move_sl", "sl": new_sl}

    if trade.get("stage", 0) == 1 and current_r >= partial_r:
        # ICT logic: Close 50-80% at first major liquidity pool
        trade["stage"] = 2
        close_percent = 0.70 if reversal_score > 50 else 0.50
        return {"action": "partial_close", "percent": close_percent}

    if trade.get("stage", 0) >= 2 and current_r >= trail_r:
        trail_multiple = 1.0
        if mode == "trend":
            trail_multiple = 1.2
        elif mode in ("tight", "defensive", "protective"):
            trail_multiple = 0.75

        if direction == "buy":
            new_sl = max(float(trade["sl"]), float(price) - (risk_distance * trail_multiple))
        else:
            new_sl = min(float(trade["sl"]), float(price) + (risk_distance * trail_multiple))

        return {"action": "trail", "sl": new_sl}

    return None
