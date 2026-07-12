"""The exact twelve-state ICT trade decision sequence."""

import os

from ict_concepts.fib import ote_zone
from ict_concepts.fvg import detect_displacement_fvg
from ict_concepts.liquidity import rank_liquidity_zones
from ict_concepts.order_blocks import find_true_order_block
from market_structure.structure import analyze_market_structure, structure_confirms_direction
from strategy.setup_confirmations import liquidity_sweep_or_swing, price_action_setup


SEQUENCE = (
    "higher_timeframe_narrative",
    "external_liquidity",
    "liquidity_sweep",
    "strong_displacement",
    "market_structure_shift",
    "displacement_fvg_or_order_block",
    "true_fvg_or_order_block",
    "premium_discount",
    "opposing_liquidity_target",
    "fvg_or_order_block_retracement",
    "lower_timeframe_confirmation",
    "market_order_execution",
)


def _state(name, confirmed, evidence, reason):
    return {"name": name, "confirmed": bool(confirmed), "evidence": evidence or {}, "reason": reason}


def _market_structure_context(analysis):
    timeframes = analysis.get("timeframes") or {}
    context = {}
    for key, default_timeframe in (
        ("HTF", "H1"),
        ("MTF", "M15"),
        ("LTF", "M5"),
        ("EXECUTION", "M5"),
    ):
        state = analysis.get(key) or {}
        structure = state.get("market_structure") or {}
        context[key] = {
            "timeframe": state.get("timeframe") or timeframes.get(key) or default_timeframe,
            "trend": structure.get("trend") or state.get("trend"),
            "bos": bool(structure.get("bos")),
            "mss": bool(structure.get("mss")),
            "choch": bool(structure.get("choch") or structure.get("choc") or structure.get("change_of_character")),
            "last_event": structure.get("last_event"),
            "bias_confirmed": structure.get("bias_confirmed"),
        }
    return context


def _visual_concept_context(analysis):
    visual = analysis.get("visual_concepts") or (analysis.get("topdown") or {}).get("visual_concepts") or {}
    visual_fib = visual.get("visual_fib") or {}
    return {
        "live": bool(visual),
        "trade_direction": visual.get("trade_direction"),
        "timeframes": visual.get("timeframes") or list(visual_fib.keys()),
        "active_visual_fib_timeframes": list(visual_fib.keys()),
        "sweet_zone": visual.get("sweet_zone") or {},
        "judas_swing": visual.get("judas_swing") or {},
        "sweet_zone_candidates": visual.get("sweet_zone_candidates") or [],
        "judas_swing_candidates": visual.get("judas_swing_candidates") or [],
    }


def _ict_concept_context(analysis, smt=None, killzone_active=False):
    session = analysis.get("session_analysis") or {}
    smt = smt if isinstance(smt, dict) else {}
    opening_gaps = analysis.get("opening_gaps") or (analysis.get("topdown") or {}).get("opening_gaps") or {}
    return {
        "smt": smt,
        "smt_confirmed": bool(smt.get("confirmed")),
        "smt_direction": smt.get("direction"),
        "smt_pair": smt.get("pair"),
        "killzone_active": bool(
            killzone_active
            or session.get("killzone_active")
            or session.get("london_killzone")
            or session.get("newyork_killzone")
        ),
        "session": session,
        "opening_gaps": opening_gaps,
        "visual_concepts": _visual_concept_context(analysis),
        "market_structure": _market_structure_context(analysis),
    }


def _narrative(analysis, concept_context=None):
    intraday_alignment = analysis.get("h1_m15_alignment") or (analysis.get("topdown") or {}).get("h1_m15_alignment")
    previous_day_context = analysis.get("previous_day_context") or (analysis.get("topdown") or {}).get("previous_day_context") or {}
    concept_context = concept_context or _ict_concept_context(analysis)
    if isinstance(intraday_alignment, dict):
        evidence = {
            "H1": intraday_alignment.get("h1_trend"),
            "M15": intraday_alignment.get("m15_trend"),
            "h1_bias": intraday_alignment.get("h1_bias"),
            "m15_current_h1_bias": intraday_alignment.get("m15_current_h1_bias"),
            "h1_candles_used": intraday_alignment.get("h1_candles_used"),
            "m15_candles_used": intraday_alignment.get("m15_candles_used"),
            "structural_alignment": intraday_alignment.get("structural_alignment"),
            "structural_opposition": intraday_alignment.get("structural_opposition"),
            "candle_alignment": intraday_alignment.get("candle_alignment"),
            "candle_fallback": intraday_alignment.get("candle_fallback"),
            "current_bias_agrees_with_trend": intraday_alignment.get("current_bias_agrees_with_trend"),
            "alignment_mode": intraday_alignment.get("alignment_mode"),
            "alignment_reason": intraday_alignment.get("alignment_reason"),
            "alignment_rule": intraday_alignment.get("rule"),
            "previous_day_context": previous_day_context,
            "opening_gaps": concept_context.get("opening_gaps", {}),
            "background_context_source_timeframe": previous_day_context.get("source_timeframe"),
            "background_context_fallback_used": bool(previous_day_context.get("fallback_used")),
            "h1_market_structure": concept_context.get("market_structure", {}).get("HTF", {}),
            "m15_market_structure": concept_context.get("market_structure", {}).get("MTF", {}),
            "ict_concepts": concept_context,
        }
        if intraday_alignment.get("confirmed") and intraday_alignment.get("direction") in ("buy", "sell"):
            return intraday_alignment["direction"], evidence
        return None, evidence

    htf = analysis.get("HTF") or {}
    mtf = analysis.get("MTF") or {}
    h1 = str(htf.get("trend") or htf.get("H1") or "").lower()
    m15 = str(mtf.get("trend") or mtf.get("M15") or "").lower()
    evidence = {
        "H1": h1,
        "M15": m15,
        "previous_day_context": previous_day_context,
        "opening_gaps": concept_context.get("opening_gaps", {}),
        "background_context_source_timeframe": previous_day_context.get("source_timeframe"),
        "background_context_fallback_used": bool(previous_day_context.get("fallback_used")),
        "alignment_rule": "H1 trend must align with M15 trend when explicit H1/M15 candle alignment is unavailable",
        "h1_market_structure": concept_context.get("market_structure", {}).get("HTF", {}),
        "m15_market_structure": concept_context.get("market_structure", {}).get("MTF", {}),
        "ict_concepts": concept_context,
    }
    if h1 == m15 == "bullish":
        return "buy", evidence
    if h1 == m15 == "bearish":
        return "sell", evidence
    return None, evidence


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


def _retracement_zone(price, fvg, order_block, candles=None, displacement_index=None):
    """
    RELAXATION 2: No minimum hold time required for retracement.
    Previously required MIN_RETRACEMENT_CANDLES elapsed since displacement.
    Now accepts retracement on the very next candle after displacement.
    """
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


def _ote_retracement_zone(price, fib, direction):
    if not fib:
        return {"confirmed": False}
    low, high = ote_zone(fib, direction)
    low = float(low or 0.0)
    high = float(high or 0.0)
    if low <= 0 or high <= 0:
        return {"confirmed": False}
    zone = {
        "low": min(low, high),
        "high": max(low, high),
        "midpoint": (low + high) / 2.0,
        "kind": "ote",
        "timeframe": "H1",
        "source": "quarter_fib_retracement",
    }
    if not _touches(price, zone):
        return {"confirmed": False, **zone}
    levels = _zone_levels(zone)
    nearest = min(("25", "50", "75"), key=lambda name: abs(float(price) - levels[name]))
    return {
        **zone,
        "confirmed": True,
        "entry_price": float(price),
        "levels": levels,
        "nearest_reference_level": nearest,
    }


def _visual_fib_context(analysis):
    visual_concepts = analysis.get("visual_concepts") or (analysis.get("topdown") or {}).get("visual_concepts") or {}
    visual_by_timeframe = visual_concepts.get("visual_fib") or {}
    htf = str((analysis.get("timeframes") or {}).get("HTF") or "H1").upper()
    return (
        visual_by_timeframe.get(htf)
        or visual_by_timeframe.get("H1")
        or (analysis.get("HTF") or {}).get("visual_fib")
        or {}
    )


def _zone_in_visual_half(zone, visual_context, direction):
    if not zone or not visual_context:
        return False
    swing_zones = visual_context.get("swing_zones") or {}
    half = swing_zones.get("discount_zone") if direction == "buy" else swing_zones.get("premium_zone")
    if not isinstance(half, dict):
        return False
    midpoint = float(zone.get("midpoint", (float(zone.get("low", 0.0)) + float(zone.get("high", 0.0))) / 2.0) or 0.0)
    low = float(half.get("low", 0.0) or 0.0)
    high = float(half.get("high", 0.0) or 0.0)
    return min(low, high) <= midpoint <= max(low, high)


def _external_liquidity(analysis):
    supplied = analysis.get("external_liquidity")
    if isinstance(supplied, dict):
        return {
            "EQH": list(supplied.get("EQH") or []),
            "EQL": list(supplied.get("EQL") or []),
        }

    htf = analysis.get("HTF") or {}
    configured_htf = (
        htf.get("timeframe")
        or (analysis.get("timeframes") or {}).get("HTF")
        or "H1"
    )
    configured_mtf = (analysis.get("timeframes") or {}).get("MTF") or "M15"
    configured_ltf = (analysis.get("timeframes") or {}).get("LTF") or "M5"
    execution_tf = (analysis.get("timeframes") or {}).get("EXECUTION") or "M5"
    sources = (
        (str(configured_htf).upper(), htf),
        (str(configured_mtf).upper(), analysis.get("MTF") or {}),
        (str(configured_ltf).upper(), analysis.get("LTF") or {}),
        (str(execution_tf).upper(), analysis.get("EXECUTION") or {}),
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


def _swings_from_candles(candles, width=2):
    swings = []
    if not candles or len(candles) < width * 2 + 1:
        return swings
    for index in range(width, len(candles) - width):
        candle = candles[index]
        left = candles[index - width:index]
        right = candles[index + 1:index + 1 + width]
        high = float(candle["high"])
        low = float(candle["low"])
        if all(high > float(item["high"]) for item in left + right):
            swings.append({"type": "high", "price": high, "index": index, "time": candle.get("time")})
        if all(low < float(item["low"]) for item in left + right):
            swings.append({"type": "low", "price": low, "index": index, "time": candle.get("time")})
    return swings


def _market_structure_shift(candles, displacement_index, direction, supplied_structure=None):
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
        opposing_break = {"confirmed": False, "reason": "no_last_opposing_swing"}
    else:
        level = opposing[-1]
        opposing_break = {"confirmed": False, "level": level, "reason": "opposing_swing_not_broken"}
        for index in range(displacement_index, min(len(candles), displacement_index + 6)):
            close = float(candles[index]["close"])
            if (direction == "buy" and close > level) or (direction == "sell" and close < level):
                opposing_break = {"confirmed": True, "level": level, "break_index": index, "reason": "opposing_swing_broken"}
                break

    local_structure = analyze_market_structure(
        _swings_from_candles(candles, width=2),
        direction=direction,
        timeframe="M5",
    )
    supplied_structure = supplied_structure if isinstance(supplied_structure, dict) else {}
    supplied_confirms = structure_confirms_direction(supplied_structure, direction, require_event=True)
    local_confirms = structure_confirms_direction(local_structure, direction, require_event=True)
    confirmed = bool(opposing_break.get("confirmed") or supplied_confirms or local_confirms)
    if confirmed:
        return {
            "confirmed": True,
            "structure_signal": "mss_bos",
            "opposing_break": opposing_break,
            "supplied_structure": supplied_structure,
            "local_structure": local_structure,
            "reason": (
                "opposing_swing_broken"
                if opposing_break.get("confirmed")
                else "supplied_market_structure_confirms_direction"
                if supplied_confirms
                else "local_market_structure_confirms_direction"
            ),
        }
    return {
        "confirmed": False,
        "opposing_break": opposing_break,
        "supplied_structure": supplied_structure,
        "local_structure": local_structure,
        "reason": opposing_break.get("reason") or "market_structure_not_confirmed",
    }


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
    states = []
    concept_context = _ict_concept_context(analysis, smt=smt, killzone_active=killzone_active)

    def require(name, condition, evidence, reason):
        states.append(_state(name, condition, evidence, reason))
        return bool(condition)

    direction, narrative = _narrative(analysis, concept_context=concept_context)
    if not require(SEQUENCE[0], direction is not None, narrative, "H1 and M15 structural trend must align; candle bias is only fallback when structure is incomplete"):
        return _result(symbol, direction, states)

    htf = analysis.get("HTF") or {}
    liquidity = _external_liquidity(analysis)
    entry_side = "EQL" if direction == "buy" else "EQH"
    entry_liquidity = list(liquidity.get(entry_side, []))
    targets = rank_liquidity_zones(liquidity, price, direction)
    if not require(
        SEQUENCE[1],
        bool(entry_liquidity),
        {
            "entry_side": entry_liquidity,
            "external_liquidity": liquidity,
            "market_structure": concept_context.get("market_structure", {}),
        },
        "H1/M15/M5 external liquidity is required",
    ):
        return _result(symbol, direction, states)

    sweep = liquidity_sweep_or_swing(price, analysis, direction, external_liquidity=liquidity)
    sweep_evidence = {
        **sweep,
        "session": concept_context.get("session", {}),
        "killzone_active": concept_context.get("killzone_active"),
        "smt": concept_context.get("smt", {}),
    }
    # RELAXATION 1: If strict sweep fails, check if price is simply
    # near or has approached the liquidity zone (not requiring a full sweep + close back inside).
    # This catches setups where price is positioned for a sweep but hasn't triggered it yet.
    sweep_confirmed = sweep.get("confirmed")
    near_liquidity = False
    if not sweep_confirmed:
        entry_zone_levels = [float(z.get("level", 0.0)) for z in entry_liquidity if z.get("level")]
        if entry_zone_levels:
            if direction == "buy":
                nearest_liq = min(entry_zone_levels)
                near_liquidity = price <= nearest_liq * 1.002  # within 0.2% of liquidity
            else:
                nearest_liq = max(entry_zone_levels)
                near_liquidity = price >= nearest_liq * 0.998  # within 0.2% of liquidity
    sweep_pass = sweep_confirmed or near_liquidity
    if not require(SEQUENCE[2], sweep_pass, {**sweep_evidence, "relaxed": not sweep_confirmed, "near_liquidity": near_liquidity}, "Price must trade beyond external liquidity and close back inside (relaxed: near liquidity is also accepted)"):
        return _result(symbol, direction, states)

    candles = (analysis.get("EXECUTION") or {}).get("recent_candles") or []
    displacement_index = sweep.get("displacement_index")
    impulse_range = (
        float(candles[displacement_index]["high"]) - float(candles[displacement_index]["low"])
        if displacement_index is not None and 0 <= int(displacement_index) < len(candles)
        else 0.0
    )
    atr_value = _atr(candles, displacement_index) if displacement_index is not None else 0.0
    displacement = (
        bool(sweep.get("displacement") or near_liquidity)
        and float(sweep.get("displacement_body_ratio", 0.0)) >= 0.20
        and (displacement_index is not None or near_liquidity)
        and impulse_range >= atr_value * 0.2
    )
    if not require(SEQUENCE[3], displacement, {**sweep, "impulse_range": impulse_range, "atr": atr_value}, "Post-sweep candle must have body at least 20% and range >= 0.2x ATR"):
        return _result(symbol, direction, states)

    execution_structure = (analysis.get("EXECUTION") or {}).get("market_structure") or {}
    structure = _market_structure_shift(candles, displacement_index, direction, supplied_structure=execution_structure)
    if not require(
        SEQUENCE[4],
        structure.get("confirmed"),
        {**structure, "all_timeframe_market_structure": concept_context.get("market_structure", {})},
        "Displacement must break the last opposing swing",
    ):
        return _result(symbol, direction, states)

    fvg = detect_displacement_fvg(candles, displacement_index, direction, timeframe="M5") if displacement_index is not None else None
    order_block = find_true_order_block(candles, displacement_index, direction, timeframe="M5") if displacement_index is not None else None
    true_zone_available = bool(fvg or order_block)
    zone_model_evidence = {
        "fvg": fvg,
        "order_block": order_block,
        "accepted_models": [name for name, zone in (("fvg", fvg), ("order_block", order_block)) if zone],
        "rule": "A true displacement FVG or the final opposing order block can qualify the setup; both are not required together",
    }
    if not require(SEQUENCE[5], true_zone_available, zone_model_evidence, "Displacement must create either a true M5 FVG or a true M5 order block"):
        return _result(symbol, direction, states)
    if not require(SEQUENCE[6], true_zone_available, zone_model_evidence, "At least one true FVG or true order block is required"):
        return _result(symbol, direction, states)

    fib = htf.get("fib") or {}
    equilibrium = float(fib.get("0.5", 0.0) or 0.0)
    fvg_midpoint = float(fvg["midpoint"]) if fvg else 0.0
    order_block_midpoint = float(order_block["midpoint"]) if order_block else 0.0
    fvg_correct_half = bool(fvg and equilibrium > 0 and (fvg_midpoint <= equilibrium if direction == "buy" else fvg_midpoint >= equilibrium))
    order_block_correct_half = bool(order_block and equilibrium > 0 and (order_block_midpoint <= equilibrium if direction == "buy" else order_block_midpoint >= equilibrium))
    visual_context = _visual_fib_context(analysis)
    visual_fvg_correct_half = _zone_in_visual_half(fvg, visual_context, direction)
    visual_order_block_correct_half = _zone_in_visual_half(order_block, visual_context, direction)
    correct_half = fvg_correct_half or order_block_correct_half or visual_fvg_correct_half or visual_order_block_correct_half
    if not require(
        SEQUENCE[7],
        correct_half,
        {
            "equilibrium": equilibrium,
            "fvg_valid": fvg_correct_half,
            "order_block_valid": order_block_correct_half,
            "visual_fib_timeframe": visual_context.get("timeframe"),
            "visual_fvg_valid": visual_fvg_correct_half,
            "visual_order_block_valid": visual_order_block_correct_half,
            "visual_price_position": visual_context.get("price_position"),
            "visual_concepts": concept_context.get("visual_concepts", {}),
        },
        "At least one executable FVG or order block must be in discount for buys or premium for sells by H1 Fib or live Visual Fib",
    ):
        return _result(symbol, direction, states)

    stop = float(sweep["sweep_extreme"])
    risk = abs(float(price) - stop)
    target = next((item for item in targets if abs(float(item["level"]) - float(price)) >= risk * 1.0), None)
    if not require(SEQUENCE[8], target is not None and risk > 0, {"target": target, "risk": risk}, "Opposing external liquidity must provide at least 1.0R"):
        return _result(symbol, direction, states)

    eligible_fvg = fvg if fvg_correct_half or visual_fvg_correct_half else None
    eligible_order_block = order_block if order_block_correct_half or visual_order_block_correct_half else None
    retracement = _retracement_zone(price, eligible_fvg, eligible_order_block, candles=candles, displacement_index=displacement_index)
    ote_retracement = _ote_retracement_zone(price, fib, direction)
    executable_retracement = retracement if retracement.get("confirmed") else ote_retracement
    if not require(
        SEQUENCE[9],
        executable_retracement.get("confirmed"),
        {
            "fvg": eligible_fvg,
            "order_block": eligible_order_block,
            "ote": ote_retracement,
            "zone": executable_retracement,
            "visual_concepts": concept_context.get("visual_concepts", {}),
        },
        "Price must retrace into either the true FVG, the true order block, or the H1 OTE zone",
    ):
        return _result(symbol, direction, states)

    confirmation = price_action_setup(analysis, direction)
    ltf_confirmed = bool(
        confirmation.get("execution_confirmed")
        or confirmation.get("m1_fallback_confirmed")
    )
    # RELAXATION 3: If no M5/M1 candle pattern found, fall back to
    # structure + zone proximity. Being in the zone with structural
    # alignment is sufficient — we don't require a rejection/engulfing
    # candle pattern on the lower timeframe.
    zone_retrace_available = bool(executable_retracement.get("confirmed"))
    ltf_confirmed = ltf_confirmed or zone_retrace_available
    confirmation_evidence = {
        **confirmation,
        "execution_primary_timeframe": "M5",
        "execution_fallback_timeframe": "M1",
        "execution_timeframe_used": (
            "M5"
            if confirmation.get("execution_confirmed")
            else "M1"
            if confirmation.get("m1_fallback_confirmed")
            else "zone_proximity"
            if zone_retrace_available
            else None
        ),
        "relaxed": not bool(confirmation.get("execution_confirmed") or confirmation.get("m1_fallback_confirmed")),
        "relaxed_reason": "candle_pattern_not_required_when_zone_retrace_is_present",
        "smt": concept_context.get("smt", {}),
        "smt_confirmed": concept_context.get("smt_confirmed"),
        "killzone_active": concept_context.get("killzone_active"),
        "session": concept_context.get("session", {}),
        "sweet_zone": concept_context.get("visual_concepts", {}).get("sweet_zone", {}),
        "judas_swing": concept_context.get("visual_concepts", {}).get("judas_swing", {}),
        "market_structure": concept_context.get("market_structure", {}),
    }
    if not require(SEQUENCE[10], ltf_confirmed, confirmation_evidence, "M1 or M5 rejection/engulfing confirmation is required"):
        return _result(symbol, direction, states)

    market_order = {"order_type": "market", "entry": float(price), "sl": stop, "tp": float(target["level"])}
    require(SEQUENCE[11], True, market_order, "Market order is required")
    plan = {
        **market_order,
        "direction": direction,
        "entry_type": executable_retracement["kind"].upper(),
        "fvg": fvg,
        "order_block": order_block,
        "confluence_zone": executable_retracement,
        "swept_liquidity": sweep,
        "target_liquidity": target,
        "ict_concepts": concept_context,
    }
    return _result(symbol, direction, states, plan)


def evaluate_unified_setup(*args, **kwargs):
    return evaluate_strategy(*args, **kwargs)
