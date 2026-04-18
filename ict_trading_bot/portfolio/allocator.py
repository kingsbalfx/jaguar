import re


MAX_TOTAL_RISK = 2.0  # % account
MAX_SYMBOL_RISK = 0.75
MAX_CURRENCY_RISK = 1.25  # % account, across all open positions sharing the currency
MAX_SAME_DIRECTION_TRADES = 5
CORRELATED_GROUPS = [
    ["EURUSD", "GBPUSD"],
    ["USDJPY", "USDCHF"],
    ["AUDUSD", "NZDUSD"],
    ["BTCUSD", "ETHUSD"]
]


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _extract_pair(symbol: str):
    s = str(symbol or "").upper().strip()
    match = re.match(r"^([A-Z]{3})([A-Z]{3})", s)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _currency_exposure(open_positions):
    exposure = {}
    for pos in open_positions or []:
        sym = pos.get("symbol")
        base, quote = _extract_pair(sym)
        if not base or not quote:
            continue
        risk = _safe_float(pos.get("risk", 0.0), 0.0)
        exposure[base] = exposure.get(base, 0.0) + risk
        exposure[quote] = exposure.get(quote, 0.0) + risk
    return exposure


def allocate_risk(symbol, open_positions, direction=None):
    open_positions = open_positions or []
    used_risk = sum(_safe_float(p.get("risk", 0.0), 0.0) for p in open_positions)

    if used_risk >= MAX_TOTAL_RISK:
        return 0.0

    symbol_risk = sum(
        _safe_float(p.get("risk", 0.0), 0.0)
        for p in open_positions
        if str(p.get("symbol", "")).upper() == str(symbol).upper()
    )

    if symbol_risk >= MAX_SYMBOL_RISK:
        return 0.0

    penalty = 1.0

    # Currency exposure guard (forex-style symbols, e.g., EURUSD, GBPJPY).
    base, quote = _extract_pair(symbol)
    exposure = _currency_exposure(open_positions)
    for cur in (base, quote):
        if not cur:
            continue
        cur_risk = exposure.get(cur, 0.0)
        if cur_risk >= MAX_CURRENCY_RISK:
            return 0.0
        if cur_risk >= MAX_CURRENCY_RISK * 0.80:
            penalty = min(penalty, 0.5)

    # Same-direction clustering penalty (prevents stacking too many buys or sells at once).
    direction_norm = str(direction or "").lower().strip()
    if direction_norm in ("buy", "sell"):
        same_dir = [
            p
            for p in open_positions
            if str(p.get("direction", "")).lower().strip() == direction_norm
        ]
        if len(same_dir) >= MAX_SAME_DIRECTION_TRADES:
            return 0.0
        if len(same_dir) >= max(2, MAX_SAME_DIRECTION_TRADES - 2):
            penalty = min(penalty, 0.5)

    # Correlation penalty
    for group in CORRELATED_GROUPS:
        if symbol in group:
            group_risk = sum(
                _safe_float(p.get("risk", 0.0), 0.0)
                for p in open_positions
                if str(p.get("symbol", "")).upper() in group
            )
            if group_risk >= 1.0:
                penalty = min(penalty, 0.25)

    base_allowance = min(
        MAX_SYMBOL_RISK - symbol_risk,
        MAX_TOTAL_RISK - used_risk
    )
    return round(max(0.0, base_allowance * penalty), 2)
