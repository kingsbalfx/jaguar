def detect_structure(swings):
    structure = []
    last_high = None
    last_low = None

    for s in swings:
        t, idx, price = s

        if t == "high":
            if last_high and price > last_high:
                structure.append(("BOS", idx, price))
            last_high = price

        if t == "low":
            if last_low and price < last_low:
                structure.append(("BOS", idx, price))
            last_low = price

    return structure
