import os

def calculate_sl_tp(
    direction,
    entry_price,
    htf_ob,
    rr=None,
    manual_sl=None,
    manual_tp=None,
    atr=0.0,
    symbol_info=None
):
    """
    Precise SL/TP based on Structure + ATR Buffer.
    SL is hidden behind HTF Order Block or Swing point.
    """
    if manual_sl and manual_tp:
        return manual_sl, manual_tp

    if rr is None:
        rr = float(os.getenv("DEFAULT_RR_RATIO", "3.0"))
    rr = max(rr, float(os.getenv("MIN_RR_RATIO", "2.0")))

    # ATR Buffer for precision (Standard 0.5 - 1.5 ATR)
    atr_buffer = atr * float(os.getenv("SL_ATR_MULTIPLIER", "1.0"))

    if direction == "buy":
        # Precise SL: Lowest of OB or Swing - ATR Buffer
        struct_low = htf_ob.get("low", entry_price)
        sl = struct_low - atr_buffer

        # Safety: Ensure SL is below entry
        if sl >= entry_price:
            sl = entry_price - (atr * 2.0)

        tp = entry_price + (entry_price - sl) * rr
    else:
        struct_high = htf_ob.get("high", entry_price)
        sl = struct_high + atr_buffer

        if sl <= entry_price:
            sl = entry_price + (atr * 2.0)

        tp = entry_price - (sl - entry_price) * rr

    return sl, tp
