def calculate_sl_tp(
    direction,
    entry_price,
    htf_ob,
    rr=3,
    manual_sl=None,
    manual_tp=None
):
    if manual_sl and manual_tp:
        return manual_sl, manual_tp

    if direction == "buy":
        sl = htf_ob["low"]
        tp = entry_price + (entry_price - sl) * rr
    else:
        sl = htf_ob["high"]
        tp = entry_price - (sl - entry_price) * rr

    return sl, tp
