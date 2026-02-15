# Common symbol alternatives to try when a requested symbol is unavailable in MT5
# Add mappings as needed for your broker naming conventions.
MAPPINGS = {
    "BTCUSD": ["BTCUSD", "XBTUSD", "BTCUSD.i", "BTCUSD-IDEAL"],
    "ETHBTC": ["ETHBTC", "ETHBTC.i", "ETH/BTC", "ETHUSD"],
}

# Fallback candidate generator for unknown symbols
def candidates_for(symbol):
    base = symbol
    candidates = [base, "X" + base, base + ".i", base + "-i"]
    mapped = MAPPINGS.get(symbol, [])
    # keep uniqueness and order: mapped first, then generated
    out = []
    for s in mapped + candidates:
        if s not in out:
            out.append(s)
    return out
