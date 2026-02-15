from ict_concepts.fib import in_discount, in_premium

def check_entry(
    trend,
    price,
    fib_levels,
    fvgs,
    htf_order_blocks
):
    """
    trend: 'bullish' or 'bearish'
    price: current market price
    fib_levels: dict { '0.25': x, '0.5': y, '0.75': z }
    fvgs: list of LTF FVGs
    htf_order_blocks: list of HTF Order Blocks
    """

    # -------------------------
    # 1️⃣ FIB FILTER
    # -------------------------
    # Defensive fib access
    f025 = fib_levels.get("0.25") if isinstance(fib_levels, dict) else None
    f05 = fib_levels.get("0.5") if isinstance(fib_levels, dict) else None
    f075 = fib_levels.get("0.75") if isinstance(fib_levels, dict) else None

    if trend == "bullish":
        if f025 is None or f05 is None or not (f025 <= price <= f05):
            return None

    if trend == "bearish":
        if f05 is None or f075 is None or not (f05 <= price <= f075):
            return None

    # -------------------------
    # 2️⃣ FIND VALID FVG
    # -------------------------
    # Defensive FVG lookup
    valid_fvg = None
    try:
        for fvg in (fvgs or []):
            if not isinstance(fvg, dict):
                continue
            if fvg.get("type") == trend and fvg.get("low") is not None and fvg.get("high") is not None:
                if fvg["low"] <= price <= fvg["high"]:
                    valid_fvg = fvg
                    break
    except Exception:
        valid_fvg = None

    if not valid_fvg:
        return None

    # -------------------------
    # 3️⃣ HTF OB CONFIRMATION
    # -------------------------
    # Defensive OB lookup
    valid_ob = None
    try:
        for ob in (htf_order_blocks or []):
            if not isinstance(ob, dict):
                continue
            if ob.get("type") == trend and ob.get("low") is not None and ob.get("high") is not None:
                if valid_fvg and ob["low"] <= valid_fvg["low"] and valid_fvg["high"] <= ob["high"]:
                    valid_ob = ob
                    break
    except Exception:
        valid_ob = None

    if not valid_ob:
        return None

    # -------------------------
    # ✅ ENTRY CONFIRMED
    # -------------------------
    return {
        "direction": "buy" if trend == "bullish" else "sell",
        "price": price,
        "fvg": valid_fvg,
        "htf_ob": valid_ob,
        "fib_zone": "discount" if trend == "bullish" else "premium"
    }

