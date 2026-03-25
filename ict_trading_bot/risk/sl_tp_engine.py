import os


def calculate_sl_tp(
    direction,
    entry_price,
    htf_ob,
    rr=None,
    manual_sl=None,
    manual_tp=None
):
    if manual_sl and manual_tp:
        return manual_sl, manual_tp

    if rr is None:
        rr = float(os.getenv("DEFAULT_RR_RATIO", "3.0"))
    rr = max(rr, float(os.getenv("MIN_RR_RATIO", "2.0")))

    if direction == "buy":
        sl = htf_ob["low"]
        tp = entry_price + (entry_price - sl) * rr
    else:
        sl = htf_ob["high"]
        tp = entry_price - (sl - entry_price) * rr

    return sl, tp
