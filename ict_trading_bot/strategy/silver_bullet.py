"""
Silver Bullet Entry Model – dedicated 10‑11 AM NY window.
Requires a sweep on M1, displacement, and retracement into an M1 OB/FVG.
"""

import datetime as dt

def detect_silver_bullet_entry(symbol, current_price, topdown, trend):
    """
    Returns a dict with sl and tp if a valid Silver Bullet setup exists,
    otherwise None.
    """
    execution = topdown.get("EXECUTION") or {}
    m1_candles = topdown.get("m1_candles", [])
    if len(m1_candles) < 20:
        return None

    # Must be inside the Silver Bullet window (10:00‑11:00 AM NY = 14:00‑15:00 UTC)
    now_utc = dt.datetime.now(dt.timezone.utc)
    if not (14 <= now_utc.hour < 15):
        return None

    # Find a recent sweep on M1
    # Simplified: look for a candle that broke a previous swing low (for buys) or high (for sells)
    # and then a displacement candle that closed back.
    # We'll use the same strict logic as the main sweep but on M1 timeframe.
    from strategy.setup_confirmations import liquidity_sweep_or_swing

    # Create a pseudo‑analysis for M1 using the execution timeframe data
    m1_analysis = {
        "MTF": topdown.get("MTF", {}),   # use MTF swings as reference
        "LTF": topdown.get("LTF", {}),
        "EXECUTION": {"recent_candles": m1_candles},
        "HTF": topdown.get("HTF", {}),
    }
    direction = "buy" if trend == "bullish" else "sell"
    liq_state = liquidity_sweep_or_swing(current_price, m1_analysis, direction)
    if not liq_state.get("confirmed"):
        return None

    # Displacement must be strong on M1
    if liq_state.get("displacement_score", 0) < 0.7:
        return None

    # Check retracement into an M1 OB or FVG
    m1_obs = execution.get("order_blocks", [])
    m1_fvgs = execution.get("fvgs", [])

    valid_entry = False
    entry_ob = None
    entry_fvg = None

    for ob in m1_obs:
        if (isinstance(ob, dict) and not ob.get("mitigated", False) and
            ob.get("type") == ("bullish" if trend == "bullish" else "bearish")):
            try:
                ob_low = float(ob["low"])
                ob_high = float(ob["high"])
                if ob_low <= current_price <= ob_high:
                    valid_entry = True
                    entry_ob = ob
                    break
            except Exception:
                continue

    if not valid_entry:
        for fvg in m1_fvgs:
            if (isinstance(fvg, dict) and fvg.get("active", True) and
                not fvg.get("mitigated", False) and
                fvg.get("type") == ("bullish" if trend == "bullish" else "bearish")):
                try:
                    fvg_low = float(fvg["low"])
                    fvg_high = float(fvg["high"])
                    if fvg_low <= current_price <= fvg_high:
                        valid_entry = True
                        entry_fvg = fvg
                        break
                except Exception:
                    continue

    if not valid_entry:
        return None

    # Calculate tight SL and TP
    atr = float(topdown.get("HTF", {}).get("atr", 0) or 0)
    if atr <= 0:
        atr = current_price * 0.001 if current_price > 0 else 0.0001

    if trend == "bullish":
        # SL below the sweep low
        sl = liq_state.get("displacement_score", 0) * 0 + current_price - atr * 0.5  # fallback if no sweep price
        # TP at the next opposing swing high on M1 (closest high above)
        swings = m1_analysis["EXECUTION"]["recent_candles"][-20:]
        highs = [c["high"] for c in swings]
        targets = [h for h in highs if h > current_price]
        if targets:
            tp = min(targets) - atr * 0.2
        else:
            tp = current_price + atr * 2.0
    else:
        sl = current_price + atr * 0.5
        lows = [c["low"] for c in swings]
        targets = [l for l in lows if l < current_price]
        if targets:
            tp = max(targets) + atr * 0.2
        else:
            tp = current_price - atr * 2.0

    return {
        "sl": round(float(sl), 5),
        "tp": round(float(tp), 5),
    }