# Common symbol alternatives to try when a requested symbol is unavailable in MT5
# Add mappings as needed for your broker naming conventions.
MAPPINGS = {
    "BTCUSD": ["BTCUSD", "BTC", "BTCUSDm", "XBTUSD", "BTCUSD.i", "BTCUSD-IDEAL"],
    "ETHUSD": ["ETHUSD", "ETH", "ETHUSDm", "ETHUSD.i", "ETH/USD"],
    "BTC": ["BTC", "BTCUSD", "BTCUSDm", "XBTUSD", "BTCUSD.i", "BTCUSD-IDEAL"],
    "ETH": ["ETH", "ETHUSD", "ETHUSDm", "ETHUSD.i", "ETH/USD"],
    "ETHBTC": ["ETHBTC", "ETHBTC.i", "ETH/BTC", "ETHUSD", "ETH"],
}


def candidates_for(symbol):
    base = symbol
    candidates = [base, "X" + base, base + ".i", base + "-i"]
    mapped = MAPPINGS.get(symbol, [])

    out = []
    for s in mapped + candidates:
        if s not in out:
            out.append(s)
    return out
