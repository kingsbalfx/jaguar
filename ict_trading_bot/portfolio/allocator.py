MAX_TOTAL_RISK = 2.0  # % account
MAX_SYMBOL_RISK = 0.75
CORRELATED_GROUPS = [
    ["EURUSD", "GBPUSD"],
    ["USDJPY", "USDCHF"],
    ["AUDUSD", "NZDUSD"],
    ["BTCUSD", "ETHUSD"]
]

def allocate_risk(symbol, open_positions):
    used_risk = sum(p["risk"] for p in open_positions)

    if used_risk >= MAX_TOTAL_RISK:
        return 0.0

    symbol_risk = sum(
        p["risk"] for p in open_positions
        if p["symbol"] == symbol
    )

    if symbol_risk >= MAX_SYMBOL_RISK:
        return 0.0

    # Correlation penalty
    for group in CORRELATED_GROUPS:
        if symbol in group:
            group_risk = sum(
                p["risk"] for p in open_positions
                if p["symbol"] in group
            )
            if group_risk >= 1.0:
                return 0.25  # reduced risk

    return min(
        MAX_SYMBOL_RISK - symbol_risk,
        MAX_TOTAL_RISK - used_risk
    )
