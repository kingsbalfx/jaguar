def choose_order_type(price, fvg, mode="auto"):
    if mode == "market":
        return "market"

    if mode == "limit":
        return "limit"

    # AUTO MODE
    if not isinstance(fvg, dict):
        return "market"

    low = fvg.get("low")
    high = fvg.get("high")
    if low is None or high is None:
        return "market"

    if low <= price <= high:
        return "market"

    return "limit"
