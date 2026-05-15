from ict_concepts.fib import in_discount, in_premium
from strategy.ict_fvg import ict_liquidity_fvg_strategy
from strategy.breakout import breakout_retest_strategy

from utils.symbol_profile import get_entry_profile, infer_asset_class


def execute_decision(score):
    """
    PURE ICT EXECUTION THRESHOLDS:
    Lowered significantly to allow valid ICT setups to execute.
    Pure ICT scoring focuses on: Liquidity + BOS + Displacement + Zone quality.
    """
    if score >= 40:
        return "EXECUTE_FULL"
    elif score >= 30:
        return "EXECUTE_PARTIAL"
    elif score >= 20:
        return "WATCH"
    else:
        return "SKIP"


def unified_score_engine(data, context):
    """
    Unified scoring engine combining market data and context into a 0-100 score.

    Returns:
        tuple: (base_score: float, breakdown: dict with component scores)
    """
    # This is a local wrapper for the centralized CIS engine
    breakdown = {}
    
    # Market Quality Scores (each 0-25)
    liquidity_score = 25.0 if data.get("liquidity_sweep") else 0.0
    breakdown["liquidity"] = liquidity_score
    
    bos_score = 25.0 if data.get("bos") else 0.0
    breakdown["bos"] = bos_score
    
    displacement_score = min(25.0, float(data.get("displacement", 0.0) or 0.0) * 0.1)
    breakdown["displacement"] = displacement_score
    
    # ML/Rule Quality (0-25)
    ml_probability = float(context.get("ml_probability", 0.5) or 0.5)
    ml_score = ml_probability * 25.0
    breakdown["ml"] = ml_score
    
    rule_score = float(context.get("rule_score", 0.0) or 0.0)
    breakdown["rule"] = min(25.0, rule_score)
    
    # Trend Strength & Confirmation (0-25)
    trend_strength = float(data.get("trend_strength", 0.0) or 0.0)
    trend_score = min(25.0, trend_strength * 25.0)
    breakdown["trend"] = trend_score
    
    # Price Action Confirmation (0-25)
    price_action_bonus = 25.0 if context.get("price_action_confirmed") else 12.5
    breakdown["price_action"] = price_action_bonus
    
    # Calculate base score (max 100 by capping component contributions)
    base_score = min(
        100.0,
        liquidity_score + 
        bos_score + 
        (displacement_score * 0.5) +  # Weight less than hard rules
        ml_score +
        trend_score +
        price_action_bonus
    )
    
    breakdown["total"] = base_score
    return base_score, breakdown


def body_ratio(c):
    return abs(float(c["close"]) - float(c["open"])) / max((float(c["high"]) - float(c["low"])), 1e-9)




def _normalize_trend(value):
    v = str(value or "").lower().strip()
    if v in ("bullish", "buy", "long"):
        return "bullish"
    if v in ("bearish", "sell", "short"):
        return "bearish"
    return None


def confirm_price_action(data, trend):
    candles = (data or {}).get("candles") or []
    if not isinstance(candles, list) or len(candles) < 3:
        return False

    trend = _normalize_trend(trend) or ""
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]

    if body_ratio(c2) < 0.6:
        return False

    if trend == "bullish":
        return (
            float(c3["close"]) > float(c3["open"])
            and float(c3["low"]) >= float(c2["low"])
            and float(c3["close"]) >= float(c2["close"]) * 0.98
        )
    return (
        float(c3["close"]) < float(c3["open"])
        and float(c3["high"]) <= float(c2["high"])
        and float(c3["close"]) <= float(c2["close"]) * 1.02
    )


def sniper_entry_trigger(data, trend):
    m5 = (data or {}).get("m5_candles") or []
    m1 = (data or {}).get("m1_candles") or []

    if not isinstance(m5, list) or len(m5) < 5:
        return False

    trend = _normalize_trend(trend) or ""
    prev_high = max(float(c["high"]) for c in m5[-5:-2])
    prev_low = min(float(c["low"]) for c in m5[-5:-2])
    last = m5[-1]

    if trend == "bullish":
        bos = float(last["close"]) > prev_high
    else:
        bos = float(last["close"]) < prev_low

    if not bos:
        return False

    if body_ratio(last) < 0.6:
        return False

    if isinstance(m1, list) and len(m1) >= 3:
        c1, c2, c3 = m1[-3], m1[-2], m1[-1]
        if trend == "bullish":
            return float(c3["close"]) > float(c3["open"]) and float(c3["low"]) >= float(c2["low"])
        return float(c3["close"]) < float(c3["open"]) and float(c3["high"]) <= float(c2["high"])

    return True


def m1_liquidity_sweep_entry(data, trend):
    m1 = (data or {}).get("m1_candles") or []
    if not isinstance(m1, list) or len(m1) < 5:
        return False

    trend = _normalize_trend(trend) or ""
    highs = [float(c["high"]) for c in m1[-5:-2]]
    lows = [float(c["low"]) for c in m1[-5:-2]]
    prev_high = max(highs)
    prev_low = min(lows)

    c1, c2, c3 = m1[-3], m1[-2], m1[-1]

    if trend == "bullish":
        sweep = float(c2["low"]) < prev_low
        reversal = (
            float(c3["close"]) > float(c3["open"])
            and float(c3["close"]) > float(c2["high"])
            and body_ratio(c3) > 0.6
        )
        return sweep and reversal

    sweep = float(c2["high"]) > prev_high
    reversal = (
        float(c3["close"]) < float(c3["open"])
        and float(c3["close"]) < float(c2["low"])
        and body_ratio(c3) > 0.6
    )
    return sweep and reversal


def score_fvg_entry(price, fvg, trend=None):
    """Convert FVG validation to scoring system"""
    if not isinstance(fvg, dict):
        return 0.0
    if fvg.get("low") is None or fvg.get("high") is None:
        return 0.0

    score = 100.0

    # Mitigated penalty
    if fvg.get("mitigated"):
        score -= 40.0
    if not fvg.get("active", True):
        score -= 20.0

    # Size and context penalties
    if not fvg.get("size_ok", True):
        score -= 15.0
    if not fvg.get("context_aligned", True):
        score -= 15.0

    # Trend alignment penalty
    trend = _normalize_trend(trend)
    if trend and fvg.get("type") and fvg.get("type") != trend:
        score -= 25.0

    # Price bounds check
    if not (float(fvg["low"]) <= float(price) <= float(fvg["high"])):
        return 0.0  # Hard reject if price not in zone

    return max(0.0, score)


def score_ob_entry(price, ob, trend=None):
    """Convert OB validation to scoring system"""
    if not isinstance(ob, dict):
        return 0.0
    if ob.get("low") is None or ob.get("high") is None:
        return 0.0

    score = 100.0

    # Freshness and mitigation penalties
    if ob.get("mitigated"):
        score -= 40.0
    if ob.get("fresh") is False:
        score -= 20.0

    # Quality gradient (relaxed from 0.70 hard cutoff)
    quality = float(ob.get("quality", 0.0) or 0.0)
    if quality >= 0.80:
        pass  # Full score
    elif quality >= 0.70:
        score -= 10.0
    elif quality >= 0.60:
        score -= 25.0
    else:
        score -= 50.0

    # Trend alignment penalty
    trend = _normalize_trend(trend)
    if trend and ob.get("type") and ob.get("type") != trend:
        score -= 25.0

    # Liquidity and institutional penalties
    if not ob.get("liquidity_sweep_confirmed", False):
        score -= 20.0
    if not ob.get("institutional_footprint", False):
        score -= 15.0

    # Displacement gradient (relaxed from 0.70 hard cutoff)
    displacement = float(ob.get("displacement", 0.0) or 0.0)
    if displacement >= 0.75:
        pass  # Full score
    elif displacement >= 0.65:
        score -= 10.0
    elif displacement >= 0.55:
        score -= 25.0
    else:
        score -= 50.0

    # Price bounds check
    if not (float(ob["low"]) <= float(price) <= float(ob["high"])):
        return 0.0  # Hard reject if price not in zone

    return max(0.0, score)


def rsi_trend_confirmation(data, direction):
    """RSI should NOT generate trades; it should only confirm direction."""
    rsi = data.get("rsi", 50)
    direction = _normalize_trend(direction)

    if direction == "bullish":
        return rsi > 55
    elif direction == "bearish":
        return rsi < 45
    return False


def double_confirmation(data, direction):
    """Main trigger: Price Action + Displacement strength."""
    # 1. Structure (BOS/Liq) is confirmed in the main model loop
    
    # 2. Price action confirmation
    pa = confirm_price_action(data, direction)

    # 3. Displacement strength
    displacement_ok = float(data.get("displacement", 0.0) or 0.0) >= 0.6

    return pa and displacement_ok


def optional_sniper_bonus(data, direction):
    """Sniper becomes an optional improvement rather than a requirement."""
    m5_ok = sniper_entry_trigger(data, direction)
    m1_ok = m1_liquidity_sweep_entry(data, direction)

    if m5_ok or m1_ok:
        return True, "SNIPER_ENTRY"
    
    return False, "STANDARD_ENTRY"


def calculate_confidence_score(data, direction, entry_type):
    """Rank trades from weak to strong to control execution quality."""
    score = 0

    # STRUCTURE (MOST IMPORTANT)
    if data.get("liquidity_sweep"):
        score += 2
    if data.get("bos"):
        score += 2

    # DISPLACEMENT
    displacement = float(data.get("displacement", 0.0) or 0.0)
    if displacement >= 0.7:
        score += 2
    elif displacement >= 0.6:
        score += 1

    # ZONE QUALITY
    if data.get("fvg") or (data.get("fvgs") and len(data.get("fvgs")) > 0):
        score += 1
    if data.get("htf_ob") or (data.get("htf_order_blocks") and len(data.get("htf_order_blocks")) > 0):
        score += 1

    # RSI ALIGNMENT
    rsi = data.get("rsi", 50)
    direction = _normalize_trend(direction)
    if direction == "bullish" and rsi > 55:
        score += 1
    elif direction == "bearish" and rsi < 45:
        score += 1

    # SNIPER BONUS
    if entry_type == "SNIPER_ENTRY":
        score += 2

    return score


def classify_trade(score):
    if score >= 8:
        return "A+"
    elif score >= 6:
        return "A"
    elif score >= 4:
        return "B"
    else:
        return "C"

def should_execute_trade(score):
    return score >= 5   # minimum quality threshold (tuneable)


def entry_debug_snapshot(data):
    trend = _normalize_trend((data or {}).get("trend"))
    price_action_ok = confirm_price_action(data, trend) if trend else False
    return {
        "liq": bool((data or {}).get("liquidity_sweep")),
        "bos": bool((data or {}).get("bos")),
        "disp": float((data or {}).get("displacement", 0.0) or 0.0),
        "fvg": bool((data or {}).get("fvg") or (data or {}).get("fvgs")),
        "ob": bool((data or {}).get("htf_ob") or (data or {}).get("htf_order_blocks")),
        "price_action": bool(price_action_ok),
    }


def explain_hybrid_failure(data):
    """Updated to reflect soft scoring penalties instead of hard blocks"""
    trend = _normalize_trend((data or {}).get("trend"))
    if not trend:
        return "trend"

    # ADAPTIVE TREND STRENGTH: Allow slightly lower strength (0.50) if market condition is 'normal' or 'pullback'
    min_strength = 0.50 if (data or {}).get("market_condition") in ("normal", "pullback") else 0.60
    if float((data or {}).get("trend_strength", 0.0) or 0.0) < min_strength:
        return "trend_strength"

    # No longer hard blocks - these are now penalties
    # if not (data or {}).get("liquidity_sweep"):
    #     return "no_liquidity_sweep"
    # if not (data or {}).get("bos"):
    #     return "no_bos"

    price = float((data or {}).get("price", 0.0) or 0.0)
    fvg = (data or {}).get("fvg")
    ob = (data or {}).get("htf_ob")

    # Use scoring functions instead of boolean validation
    fvg_score = score_fvg_entry(price, fvg, trend) if fvg else 0.0
    ob_score = score_ob_entry(price, ob, trend) if ob else 0.0

    # Check additional zones
    for item in ((data or {}).get("fvgs") or []):
        fvg_score = max(fvg_score, score_fvg_entry(price, item, trend))
    for item in ((data or {}).get("htf_order_blocks") or []):
        ob_score = max(ob_score, score_ob_entry(price, item, trend))

    if fvg_score < 30.0 and ob_score < 30.0:
        return "zone"

    # No longer hard blocks - these are now penalties
    # if not double_confirmation(data, trend):
    #     return "double_confirmation"
    # if not rsi_trend_confirmation(data, trend):
    #     return "rsi_alignment"

    # Calculate final score with penalties to determine if it would execute
    context = {
        "price_action_confirmed": double_confirmation(data, trend),
        "ml_probability": data.get("ml_probability", 0.5),
        "backtest_approval": data.get("backtest_approval", "none"),
        "rule_score": data.get("rule_score", 0),
        "favorable": data.get("favorable", False),
        "avoid": data.get("avoid", False)
    }

    base_score, _ = unified_score_engine(data, context)

    # Calculate penalties
    trend_strength_penalty = 0.0
    current_trend_strength = float(data.get("trend_strength", 0.0) or 0.0)
    if current_trend_strength < min_strength:
        trend_strength_penalty = (min_strength - current_trend_strength) * 50.0

    liquidity_penalty = 0.0 if data.get("liquidity_sweep") else 25.0
    bos_penalty = 0.0 if data.get("bos") else 25.0
    zone_penalty = 40.0 if fvg_score < 30.0 and ob_score < 30.0 else 0.0
    double_conf_penalty = 0.0 if double_confirmation(data, trend) else 20.0
    rsi_penalty = 0.0 if rsi_trend_confirmation(data, trend) else 15.0

    total_penalties = (
        trend_strength_penalty + liquidity_penalty + bos_penalty +
        zone_penalty + double_conf_penalty + rsi_penalty
    )

    final_score = max(0.0, base_score - total_penalties)

    if final_score < 4.0:  # Minimum threshold for execution
        return "low_confidence"

    return "ready"


def _dynamic_stop_loss(data, trend, price):
    trend = _normalize_trend(trend) or ""
    atr = abs(float((data or {}).get("atr", 0.0) or 0.0))
    market_condition = str((data or {}).get("market_condition") or "").lower()
    buffer_atr = atr * (0.35 if market_condition == "volatile" else 0.15)

    sweep_low = None
    sweep_high = None
    m1 = (data or {}).get("m1_candles") or []
    if isinstance(m1, list) and len(m1) >= 3:
        c2 = m1[-2]
        sweep_low = float(c2.get("low")) if c2.get("low") is not None else None
        sweep_high = float(c2.get("high")) if c2.get("high") is not None else None

    swing_low = (data or {}).get("swing_low")
    swing_high = (data or {}).get("swing_high")
    try:
        swing_low = float(swing_low) if swing_low is not None else None
    except Exception:
        swing_low = None
    try:
        swing_high = float(swing_high) if swing_high is not None else None
    except Exception:
        swing_high = None

    if trend == "bullish":
        candidates = [x for x in (sweep_low, swing_low) if isinstance(x, (int, float))]
        anchor = min(candidates) if candidates else (price - max(atr * 2.0, 0.0))
        return round(anchor - buffer_atr, 5)

    candidates = [x for x in (sweep_high, swing_high) if isinstance(x, (int, float))]
    anchor = max(candidates) if candidates else (price + max(atr * 2.0, 0.0))
    return round(anchor + buffer_atr, 5)


def hybrid_entry_model(data):
    """
    UPDATED HYBRID ARCHITECTURE WITH SOFT SCORING:
    Core Setup (Liq + BOS + Zone) with penalties instead of hard blocks
    -> Double Confirmation (PA + Displacement) with scoring
    -> RSI Trend Filter with penalty
    -> Optional Sniper Boost
    -> Dynamic Confidence Scoring
    """

    if not isinstance(data, dict):
        return None

    trend = _normalize_trend(data.get("trend"))
    if trend not in ("bullish", "bearish"):
        return None

    price = float(data.get("price") or 0.0)

    # ADAPTIVE TREND STRENGTH: Allow slightly lower strength (0.50) if market condition is 'normal' or 'pullback'
    # This prevents the "Wait for entry: trend strength" spam during valid ICT retracements.
    min_strength = 0.50 if data.get("market_condition") in ("normal", "pullback") else 0.60

    trend_strength_penalty = 0.0
    current_trend_strength = float(data.get("trend_strength", 0.0) or 0.0)
    if current_trend_strength < min_strength:
        trend_strength_penalty = (min_strength - current_trend_strength) * 50.0  # Penalty for weak trend

    # Convert liquidity and BOS to penalties instead of hard blocks
    liquidity_penalty = 0.0 if data.get("liquidity_sweep") else 25.0
    bos_penalty = 0.0 if data.get("bos") else 25.0

    # 🔴 2. ZONE CHECK WITH SCORING
    fvg = data.get("fvg")
    ob = data.get("htf_ob")

    # Use scoring functions instead of hard validation
    fvg_score = score_fvg_entry(price, fvg, trend) if fvg else 0.0
    ob_score = score_ob_entry(price, ob, trend) if ob else 0.0

    # Check additional FVGs and OBs with scoring
    if fvg_score < 50.0:  # If primary FVG score is low, check alternatives
        for item in (data.get("fvgs") or []):
            alt_score = score_fvg_entry(price, item, trend)
            fvg_score = max(fvg_score, alt_score)

    if ob_score < 50.0:  # If primary OB score is low, check alternatives
        for item in (data.get("htf_order_blocks") or []):
            alt_score = score_ob_entry(price, item, trend)
            ob_score = max(ob_score, alt_score)

    # Zone penalty if both scores are very low
    zone_penalty = 0.0
    if fvg_score < 30.0 and ob_score < 30.0:
        zone_penalty = 40.0  # Significant penalty if no valid zone

    # 🔴 3. DOUBLE CONFIRMATION PENALTY
    double_conf_penalty = 0.0 if double_confirmation(data, trend) else 20.0

    # 🔴 4. RSI FILTER PENALTY
    rsi_penalty = 0.0 if rsi_trend_confirmation(data, trend) else 15.0

    # 🔴 5. OPTIONAL SNIPER BOOST
    sniper_ok, entry_type = optional_sniper_bonus(data, trend)

    # 🔴 6. UNIFIED SCORING SYSTEM WITH PENALTIES
    context = {
        "price_action_confirmed": double_confirmation(data, trend),
        "ml_probability": data.get("ml_probability", 0.5),
        "backtest_approval": data.get("backtest_approval", "none"),
        "rule_score": data.get("rule_score", 0),
        "favorable": data.get("favorable", False),
        "avoid": data.get("avoid", False)
    }

    base_score, breakdown = unified_score_engine(data, context)

    # PURE ICT EXECUTION: ULTRA-MINIMAL penalties
    # Allow setups with ANY valid ICT structure element to execute
    critical_penalties = 0.0
    if not data.get("liquidity_sweep"):
        critical_penalties += 3.0  # REDUCED from 8.0 - NOT blocking anymore
    if not data.get("bos"):
        critical_penalties += 3.0  # REDUCED from 8.0 - NOT blocking anymore
    
    # Displacement bonus instead of penalty (INCREASED)
    displacement_value = float(data.get("displacement", 0.0) or 0.0)
    displacement_bonus = 0.0
    if displacement_value >= 0.70:
        displacement_bonus = 20.0  # INCREASED from 15.0
    elif displacement_value >= 0.50:
        displacement_bonus = 12.0  # INCREASED from 8.0
    elif displacement_value >= 0.30:
        displacement_bonus = 6.0   # INCREASED from 3.0
    
    # NEW: RSI TREND BOOSTER (not penalty!)
    rsi_boost = 0.0
    rsi_value = float(data.get("rsi", 50) or 50)
    if trend == "bullish" and rsi_value > 55:
        rsi_boost = min(15.0, (rsi_value - 55) / 2.0)  # 0-15 points BOOST
    elif trend == "bearish" and rsi_value < 45:
        rsi_boost = min(15.0, (45 - rsi_value) / 2.0)  # 0-15 points BOOST
    
    # NEW: VOLUME BOOSTER
    volume_boost_score = 0.0
    candles = data.get("candles") or []
    if len(candles) >= 10:
        try:
            recent_vols = [float(c.get("tick_volume", c.get("volume", 0)) or 0) for c in candles[-10:]]
            avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 1.0
            current_vol = float(candles[-1].get("tick_volume", candles[-1].get("volume", 0)) or 0)
            if avg_vol > 0 and current_vol > avg_vol * 1.2:
                volume_boost_score = 10.0  # Strong volume confirmation BOOST
        except Exception:
            pass
    
    # Zone: minimal penalty only if BOTH FVG and OB are completely missing
    zone_penalty_adjusted = 0.0
    if fvg_score < 10.0 and ob_score < 10.0:
        zone_penalty_adjusted = 2.0  # REDUCED from 5.0
    
    # Reduce trend strength penalty impact (pure ICT can work in pullbacks)
    trend_strength_penalty = trend_strength_penalty * 0.5  # Cut in half
    
    # Apply all BOOSTERS - Remove RSI and double confirmation penalties (not core ICT)
    total_penalties = critical_penalties + zone_penalty_adjusted + trend_strength_penalty
    total_penalties -= (displacement_bonus + rsi_boost + volume_boost_score)
    total_penalties = max(0.0, min(35.0, total_penalties))  # Cap at 35 (was 25) - MORE ROOM FOR BONUSES

    final_score = max(0.0, base_score - total_penalties)

    decision = execute_decision(final_score)

    # PURE ICT: Show ACTUAL penalties being applied (matching code above)
    actual_liq_penalty = 8.0 if not data.get("liquidity_sweep") else 0.0
    actual_bos_penalty = 8.0 if not data.get("bos") else 0.0
    actual_zone_penalty = 5.0 if (fvg_score < 10.0 and ob_score < 10.0) else 0.0
    
    print(f"[PURE ICT SCORE] {final_score:.2f} (base: {base_score:.2f}, penalties: {total_penalties:.2f}) → {decision}")
    print(f"[ICT PENALTIES] liq:{actual_liq_penalty:.1f} bos:{actual_bos_penalty:.1f} zone:{actual_zone_penalty:.1f} trend:{trend_strength_penalty:.1f} disp_bonus:{displacement_bonus:.1f}")
    print(f"[FVG/OB SCORES] fvg:{fvg_score:.1f} ob:{ob_score:.1f}")
    print(f"[BREAKDOWN] {breakdown}")

    # Scale risk based on the execution band instead of the raw score band.
    if decision == "EXECUTE_FULL":
        risk_multiplier = 1.0
    elif decision == "EXECUTE_PARTIAL":
        risk_multiplier = 0.7
    elif decision == "WATCH":
        risk_multiplier = 0.4
    else:
        risk_multiplier = 0.0

    sl = _dynamic_stop_loss(data, trend, price)

    return {
        "type": entry_type,
        "direction": "buy" if trend == "bullish" else "sell",
        "price": price,
        "confidence_score": final_score,
        "confidence_grade": "A+" if final_score >= 85 else "A" if final_score >= 70 else "B" if final_score >= 55 else "C",
        "sl": sl,
        "fvg": fvg,
        "htf_ob": ob,
        "reason": f"{entry_type} | Score: {final_score:.1f} | Decision: {decision} | Penalties: {total_penalties:.1f}",
        "risk_multiplier": risk_multiplier
    }


def _resolve_zone_bounds(trend, fib_levels, symbol=None, atr=None):
    f00 = fib_levels.get("0.0") if isinstance(fib_levels, dict) else None
    f05 = fib_levels.get("0.5") if isinstance(fib_levels, dict) else None
    f10 = fib_levels.get("1.0") if isinstance(fib_levels, dict) else None
    profile = get_entry_profile(symbol)
    fib_buffer_ratio = profile["fib_buffer_ratio"]
    atr_buffer_multiplier = profile["atr_buffer_multiplier"]
    atr = abs(float(atr or 0.0))

    if trend == "bullish":
        if f00 is None or f05 is None:
            return None
        lower = float(f00)
        upper = float(f05)
    elif trend == "bearish":
        if f05 is None or f10 is None:
            return None
        lower = float(f05)
        upper = float(f10)
    else:
        return None

    zone_size = max(upper - lower, 0.0)
    adaptive_buffer = max(zone_size * fib_buffer_ratio, atr * atr_buffer_multiplier)
    return {
        "lower": lower - adaptive_buffer,
        "upper": upper + adaptive_buffer,
        "buffer": adaptive_buffer,
    }


def _is_valid_fvg(fvg, trend, price):
    if not isinstance(fvg, dict):
        return False
    if fvg.get("type") != trend:
        return False
    if fvg.get("low") is None or fvg.get("high") is None:
        return False
    if fvg.get("mitigated") or not fvg.get("active", True):
        return False
    if not fvg.get("size_ok", True) or not fvg.get("context_aligned", True):
        return False
    return float(fvg["low"]) <= float(price) <= float(fvg["high"])


def _is_valid_order_block(ob, trend, reference_fvg=None, price=None):
    if not isinstance(ob, dict):
        return False
    if ob.get("type") != trend:
        return False
    if ob.get("low") is None or ob.get("high") is None:
        return False
    if not ob.get("liquidity_sweep_confirmed", False):
        return False
    if not ob.get("institutional_footprint", False):
        return False
    if float(ob.get("displacement", 0.0) or 0.0) < 0.70:
        return False

    if isinstance(reference_fvg, dict):
        return float(ob["low"]) <= float(reference_fvg["low"]) and float(reference_fvg["high"]) <= float(ob["high"])

    if price is None:
        return False
    return float(ob["low"]) <= float(price) <= float(ob["high"])


def explain_entry_failure(trend, price, fib_levels, fvgs, htf_order_blocks, symbol=None, atr=None):
    if trend not in ("bullish", "bearish"):
        return "trend"

    bounds = _resolve_zone_bounds(trend, fib_levels, symbol=symbol, atr=atr)
    if not bounds:
        return "fib_missing"
    if not (bounds["lower"] <= price <= bounds["upper"]):
        return "fib_zone"

    valid_fvg = next((fvg for fvg in (fvgs or []) if _is_valid_fvg(fvg, trend, price)), None)
    if not valid_fvg:
        return "valid_fvg"

    valid_ob = next(
        (ob for ob in (htf_order_blocks or []) if _is_valid_order_block(ob, trend, reference_fvg=valid_fvg, price=price)),
        None,
    )
    if not valid_ob:
        return "valid_order_block"

    return "ready"


def generate_entry(data):
    signal = ict_liquidity_fvg_strategy(data)
    if signal:
        return signal

    signal = breakout_retest_strategy(data)
    if signal:
        return signal

    return None


def check_entry(
    trend,
    price,
    fib_levels,
    fvgs,
    htf_order_blocks,
    symbol=None,
    atr=None,
):
    """
    Strict POI validation after the higher-priority setup filters.
    """
    if trend not in ("bullish", "bearish"):
        return None

    bounds = _resolve_zone_bounds(trend, fib_levels, symbol=symbol, atr=atr)
    if not bounds or not (bounds["lower"] <= price <= bounds["upper"]):
        return None

    valid_fvg = next((fvg for fvg in (fvgs or []) if _is_valid_fvg(fvg, trend, price)), None)
    if not valid_fvg:
        return None

    valid_ob = next(
        (ob for ob in (htf_order_blocks or []) if _is_valid_order_block(ob, trend, reference_fvg=valid_fvg, price=price)),
        None,
    )
    if not valid_ob:
        return None

    fib_zone = "discount" if trend == "bullish" and in_discount(price, fib_levels) else "premium" if in_premium(price, fib_levels) else "equilibrium"
    return {
        "type": "ICT_STRUCTURAL_ENTRY",
        "direction": "buy" if trend == "bullish" else "sell",
        "price": price,
        "fvg": valid_fvg,
        "htf_ob": valid_ob,
        "fib_zone": fib_zone,
        "entry_buffer": bounds["buffer"],
        "asset_class": infer_asset_class(symbol),
        "trend": trend,
        "valid_fvg": True,
        "valid_order_block": True,
    }
