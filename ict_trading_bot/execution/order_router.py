def choose_order_type(price, fvg, mode="auto"):
    if mode == "market":
        return "market"

    if mode == "limit":
        return "limit"

    # AUTO MODE
    midpoint = (fvg["low"] + fvg["high"]) / 2

    if fvg["low"] <= price <= fvg["high"]:
        return "market"

    return "limit"
