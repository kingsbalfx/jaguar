"""Central SMT correlation definitions."""


SMT_CORRELATION_GROUPS = (
    ("XAUUSD", "XAGUSD", "positive"),
    ("EURUSD", "GBPUSD", "positive"),
    ("AUDUSD", "NZDUSD", "positive"),
    ("AUDCAD", "NZDCAD", "positive"),
    ("EURCAD", "GBPCAD", "positive"),
    ("DXY", "USDJPY", "inverse"),
    ("DXY", "USDCHF", "inverse"),
    ("EURAUD", "GBPAUD", "positive"),
    ("EURNZD", "GBPNZD", "positive"),
    ("EURCHF", "GBPCHF", "positive"),
    ("EURJPY", "GBPJPY", "positive"),
    ("AUDJPY", "NZDJPY", "positive"),
    ("AUDCHF", "NZDCHF", "positive"),
    ("BTCUSD", "ETHUSD", "positive"),
    ("NAS100", "US500", "positive"),
)


def correlated_markets(symbol: str):
    canonical = str(symbol or "").upper()
    result = []
    for left, right, mode in SMT_CORRELATION_GROUPS:
        if canonical == left:
            result.append({"symbol": right, "mode": mode})
        elif canonical == right:
            result.append({"symbol": left, "mode": mode})
    return result
