# Common symbol alternatives to try when a requested symbol is unavailable in MT5
# Add mappings as needed for your broker naming conventions.
MAPPINGS = {
    "BTCUSD": ["BTCUSD", "BTC", "BTCUSDm", "XBTUSD", "BTCUSD.i", "BTCUSD-IDEAL"],
    "ETHUSD": ["ETHUSD", "ETH", "ETHUSDm", "ETHUSD.i", "ETH/USD"],
    "DOGEUSD": ["DOGEUSD", "DOGUSD", "DOGE", "DOGEUSDm", "DOGE/USD"],
    "BNBUSD": ["BNBUSD", "BNB", "BNBUSDm", "BNB/USD"],
    "SOLUSD": ["SOLUSD", "SOL", "SOLUSDm", "SOL/USD"],
    "XRPUSD": ["XRPUSD", "XRP", "XRPUSDm", "XRP/USD"],
    "TRXUSD": ["TRXUSD", "TRX", "TRXUSDm", "TRX/USD"],
    "TONUSD": ["TONUSD", "TON", "TONUSDm", "TON/USD"],
    "ADAUSD": ["ADAUSD", "ADA", "ADAUSDm", "ADA/USD"],
    "AVAXUSD": ["AVAXUSD", "AVAX", "AVAXUSDm", "AVAX/USD"],
    "LTCUSD": ["LTCUSD", "LTC", "LTCUSDm", "LTC/USD"],
    "BCHUSD": ["BCHUSD", "BCH", "BCHUSDm", "BCH/USD"],
    "EOSUSD": ["EOSUSD", "EOS", "EOSUSDm", "EOS/USD"],
    "MATICUSD": ["MATICUSD", "MATIC", "MATICUSDm", "MATIC/USD"],
    "LINKUSD": ["LINKUSD", "LINK", "LINKUSDm", "LINK/USD"],
    "UNIUSD": ["UNIUSD", "UNI", "UNIUSDm", "UNI/USD"],
    "BTC": ["BTC", "BTCUSD", "BTCUSDm", "XBTUSD", "BTCUSD.i", "BTCUSD-IDEAL"],
    "ETH": ["ETH", "ETHUSD", "ETHUSDm", "ETHUSD.i", "ETH/USD"],
    "DOGE": ["DOGE", "DOGEUSD", "DOGUSD", "DOGEUSDm", "DOGE/USD"],
    "BNB": ["BNB", "BNBUSD", "BNBUSDm", "BNB/USD"],
    "SOL": ["SOL", "SOLUSD", "SOLUSDm", "SOL/USD"],
    "XRP": ["XRP", "XRPUSD", "XRPUSDm", "XRP/USD"],
    "TRX": ["TRX", "TRXUSD", "TRXUSDm", "TRX/USD"],
    "TON": ["TON", "TONUSD", "TONUSDm", "TON/USD"],
    "ADA": ["ADA", "ADAUSD", "ADAUSDm", "ADA/USD"],
    "AVAX": ["AVAX", "AVAXUSD", "AVAXUSDm", "AVAX/USD"],
    "LTC": ["LTC", "LTCUSD", "LTCUSDm", "LTC/USD"],
    "BCH": ["BCH", "BCHUSD", "BCHUSDm", "BCH/USD"],
    "EOS": ["EOS", "EOSUSD", "EOSUSDm", "EOS/USD"],
    "MATIC": ["MATIC", "MATICUSD", "MATICUSDm", "MATIC/USD"],
    "LINK": ["LINK", "LINKUSD", "LINKUSDm", "LINK/USD"],
    "UNI": ["UNI", "UNIUSD", "UNIUSDm", "UNI/USD"],
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
