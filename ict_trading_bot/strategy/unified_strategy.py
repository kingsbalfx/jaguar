"""The exact twelve-state ICT trade decision sequence."""

from ict_concepts.fib import ote_zone
from ict_concepts.fvg import detect_displacement_fvg
from ict_concepts.liquidity import rank_liquidity_zones
from ict_concepts.order_blocks import find_true_order_block
from strategy.setup_confirmations import liquidity_sweep_or_swing, price_action_setup


SEQUENCE = (
    "higher_timeframe_narrative",
    "external_liquidity",
    "liquidity_sweep",
    "strong_displacement",
    "market_structure_shift",
    "displacement_fvg",
    "true_order_block",
    "premium_discount",
    "opposing_liquidity_target",
    "fvg_or_order_block_retracement",
    "lower_timeframe_confirmation",
    "market_order_execution",
)


def _state(name, confirmed, evidence, reason):
    return {"name": name, "confirmed": bool(confirmed), "evidence": evidence or {}, "reason": reason}


def _narrative(analysis):
    htf = analysis.get("HTF") or {}
    d1 = str((analysis.get("DAILY") or {}).get("trend") or htf.get("D1") or analysis.get("daily_trend") or "").lower()
    h4 = str((analysis.get("H4_CONTEXT") or {}).get("trend") or htf.get("H4") or "").lower()
    if d1 == h4 == "bullish":
        return "buy", {"D1": d1, "H4": h4}
    if d1 == h4 == "bearish":
        return "sell", {"D1": d1, "H4": h4}
    return None, {"D1": d1, "H4": h4}


def _touches(price, zone):
    return bool(zone) and float(zone["low"]) <= float(price) <= float(zone["high"])


def _zone_levels(zone):
    low, high = float(zone["low"]), float(zone["high"])
    distance = high - low
    return {
        "low": low,
        "25": low + distance * 0.25,
        "50": low + distance * 0.50,
        "75": low + distance * 0.75,
        "high": high,
    }


def _retracement_zone(price, fvg, order_block):
    for kind, zone in (("fvg", fvg), ("order_block", order_block)):
        if not _touches(price, zone):
            continue
        levels = _zone_levels(zone)
        nearest = min(("25", "50", "75"), key=lambda name: abs(float(price) - levels[name]))
        return {
            **zone,
            "confirmed": True,
            "kind": kind,
            "entry_price": float(price),
            "levels": levels,
            "nearest_reference_level": nearest,
        }
    return {"confirmed": False}


def _external_liquidity(analysis):
    htf = analysis.get("HTF") or {}
    configured_htf = (
        htf.get("timeframe")
        or (analysis.get("timeframes") or {}).get("HTF")
        or "HTF"
    )
    sources = (
        (str(configured_htf).upper(), htf),
        ("H4", analysis.get("H4_CONTEXT") or {}),
        ("D1", analysis.get("DAILY") or analysis.get("D1") or {}),
        ("W1", analysis.get("WEEKLY") or analysis.get("W1") or {}),
    )
    combined = {"EQH": [], "EQL": []}
    seen = set()
    for timeframe, state in sources:
        for side in ("EQH", "EQL"):
            for zone in (state.get("liquidity") or {}).get(side, []):
                if not isinstance(zone, dict):
                    continue
                level = float(zone.get("level", 0.0) or 0.0)
                identity = (side, round(level, 10), timeframe)
                if level <= 0 or identity in seen:
                    continue
                seen.add(identity)
                combined[side].append({
                    **zone,
                    "timeframe": zone.get("timeframe") or timeframe,
                    "source": zone.get("source") or f"{timeframe}_external_liquidity",
                })
    return combined


def _atr(candles, end_index, period=14):
    if end_index is None or not candles:
        return 0.0
    ranges = []
    previous_close = None
    for candle in candles[: int(end_index) + 1]:
        high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])
        ranges.append(high - low if previous_close is None else max(high - low, abs(high - previous_close), abs(low - previous_close)))
        previous_close = close
    window = ranges[-period:]
    return sum(window) / len(window) if window else 0.0


def _market_structure_shift(candles, displacement_index, direction):
    displacement_index = int(displacement_index)
    prior = candles[max(1, displacement_index - 30) : displacement_index]
    opposing = []
    for index in range(1, len(prior) - 1):
        candle = prior[index]
        if direction == "buy" and float(candle["high"]) > float(prior[index - 1]["high"]) and float(candle["high"]) > float(prior[index + 1]["high"]):
            opposing.append(float(candle["high"]))
        if direction == "sell" and float(candle["low"]) < float(prior[index - 1]["low"]) and float(candle["low"]) < float(prior[index + 1]["low"]):
            opposing.append(float(candle["low"]))
    if not opposing:
        return {"confirmed": False, "reason": "no_last_opposing_swing"}
    level = opposing[-1]
    for index in range(displacement_index, min(len(candles), displacement_index + 6)):
        close = float(candles[index]["close"])
        if (direction == "buy" and close > level) or (direction == "sell" and close < level):
            return {"confirmed": True, "level": level, "break_index": index}
    return {"confirmed": False, "level": level, "reason": "opposing_swing_not_broken"}


def _result(symbol, direction, states, plan=None):
    failed = next((state for state in states if not state["confirmed"]), None)
    complete = len(states) == len(SEQUENCE) and failed is None
    return {
        "symbol": symbol,
        "direction": direction or "",
        "trend": "bullish" if direction == "buy" else "bearish" if direction == "sell" else "neutral",
        "states": states,
        "confirmed": complete,
        "executable": complete,
        "status": "confirmed" if complete else "rejected",
        "failed_step": failed["name"] if failed else None,
        "reason": "all twelve states confirmed" if complete else failed["reason"] if failed else "incomplete sequence",
        "plan": plan or {},
        "retracement": (plan or {}).get("confluence_zone", {}),
        "target_liquidity": [(plan or {}).get("target_liquidity", {})] if (plan or {}).get("target_liquidity") else [],
    }


def evaluate_strategy(symbol, price, analysis, *, smt=None, killzone_active=False):
    """Reject immediately on the first failed state. SMT and killzones are informational only."""
    del smt, killzone_active
    states = []

    def require(name, condition, evidence, reason):
        states.append(_state(name, condition, evidence, reason))
        return bool(condition)

    direction, narrative = _narrative(analysis)
    if not require(SEQUENCE[0], direction is not None, narrative, "D1 and H4 must agree"):
        return _result(symbol, direction, states)

    htf = analysis.get("HTF") or {}
    liquidity = _external_liquidity(analysis)
    entry_side = "EQL" if direction == "buy" else "EQH"
    entry_liquidity = list(liquidity.get(entry_side, []))
    targets = rank_liquidity_zones(liquidity, price, direction)
    if not require(SEQUENCE[1], bool(entry_liquidity), {"entry_side": entry_liquidity}, "H1-or-higher external liquidity is required"):
        return _result(symbol, direction, states)

    sweep = liquidity_sweep_or_swing(price, analysis, direction, external_liquidity=liquidity)
    if not require(SEQUENCE[2], sweep.get("confirmed"), sweep, "Price must trade beyond external liquidity and close back inside"):
        return _result(symbol, direction, states)

    candles = (analysis.get("EXECUTION") or {}).get("recent_candles") or []
    displacement_index = sweep.get("displacement_index")
    impulse_range = (
        float(candles[displacement_index]["high"]) - float(candles[displacement_index]["low"])
        if displacement_index is not None and 0 <= int(displacement_index) < len(candles)
        else 0.0
    )
    displacement = (
        bool(sweep.get("displacement"))
        and float(sweep.get("displacement_body_ratio", 0.0)) >= 0.60
        and impulse_range >= _atr(candles, displacement_index)
    )
    if not require(SEQUENCE[3], displacement, {**sweep, "impulse_range": impulse_range, "atr": _atr(candles, displacement_index)}, "Post-sweep candle must be ATR-normalized displacement with body at least 60%"):
        return _result(symbol, direction, states)

    structure = _market_structure_shift(candles, displacement_index, direction)
    if not require(SEQUENCE[4], structure.get("confirmed"), structure, "Displacement must break the last opposing swing"):
        return _result(symbol, direction, states)

    fvg = detect_displacement_fvg(candles, displacement_index, direction, timeframe="M5") if displacement_index is not None else None
    if not require(SEQUENCE[5], bool(fvg), {"fvg": fvg}, "The displacement candle must create a three-candle M5 FVG"):
        return _result(symbol, direction, states)

    order_block = find_true_order_block(candles, displacement_index, direction, timeframe="M5") if displacement_index is not None else None
    if not require(SEQUENCE[6], bool(order_block), {"order_block": order_block}, "The final opposing M5 candle before displacement is required"):
        return _result(symbol, direction, states)

    fib = htf.get("fib") or {}
    equilibrium = float(fib.get("0.5", 0.0) or 0.0)
    fvg_midpoint = float(fvg["midpoint"])
    order_block_midpoint = float(order_block["midpoint"])
    fvg_correct_half = equilibrium > 0 and (fvg_midpoint <= equilibrium if direction == "buy" else fvg_midpoint >= equilibrium)
    order_block_correct_half = equilibrium > 0 and (order_block_midpoint <= equilibrium if direction == "buy" else order_block_midpoint >= equilibrium)
    correct_half = fvg_correct_half or order_block_correct_half
    if not require(SEQUENCE[7], correct_half, {"equilibrium": equilibrium, "fvg_valid": fvg_correct_half, "order_block_valid": order_block_correct_half}, "At least one executable FVG or order block must be in discount for buys or premium for sells"):
        return _result(symbol, direction, states)

    stop = float(sweep["sweep_extreme"])
    risk = abs(float(price) - stop)
    target = next((item for item in targets if abs(float(item["level"]) - float(price)) >= risk * 1.5), None)
    if not require(SEQUENCE[8], target is not None and risk > 0, {"target": target, "risk": risk}, "Opposing external liquidity must provide at least 1.5R"):
        return _result(symbol, direction, states)

    ote = ote_zone(fib, direction) if fib else (0.0, 0.0)
    eligible_fvg = fvg if fvg_correct_half else None
    eligible_order_block = order_block if order_block_correct_half else None
    retracement = _retracement_zone(price, eligible_fvg, eligible_order_block)
    if not require(SEQUENCE[9], retracement.get("confirmed"), {"fvg": eligible_fvg, "order_block": eligible_order_block, "ote": ote, "zone": retracement}, "Price must retrace into either the true FVG at any depth or the true order block"):
        return _result(symbol, direction, states)

    confirmation = price_action_setup(analysis, direction)
    ltf_confirmed = bool(confirmation.get("execution_confirmed"))
    if not require(SEQUENCE[10], ltf_confirmed, confirmation, "M1 or M5 rejection/engulfing confirmation is required"):
        return _result(symbol, direction, states)

    market_order = {"order_type": "market", "entry": float(price), "sl": stop, "tp": float(target["level"])}
    require(SEQUENCE[11], True, market_order, "Market order is required")
    plan = {
        **market_order,
        "direction": direction,
        "entry_type": retracement["kind"].upper(),
        "fvg": fvg,
        "order_block": order_block,
        "confluence_zone": retracement,
        "swept_liquidity": sweep,
        "target_liquidity": target,
    }
    return _result(symbol, direction, states, plan)


def evaluate_unified_setup(*args, **kwargs):
    return evaluate_strategy(*args, **kwargs)
