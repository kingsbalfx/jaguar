import time

TRADE_MEMORY = {}

def can_trade(symbol, ob_id, cooldown=1800):
    key = f"{symbol}_{ob_id}"
    last_trade = TRADE_MEMORY.get(key)

    if not last_trade:
        return True

    if time.time() - last_trade < cooldown:
        return False

    return True


def register_trade(symbol, ob_id):
    TRADE_MEMORY[f"{symbol}_{ob_id}"] = time.time()


def resize_lot(balance, risk_percent=1.0, stop_loss_pips=50, pip_value=1.0, min_lot=0.01, max_lot=100.0):
    """
    Conservative placeholder for lot sizing.

    Parameters:
    - balance: account balance in account currency (float)
    - risk_percent: percent of balance to risk per trade (float, e.g. 1.0 for 1%)
    - stop_loss_pips: stop loss distance in pips (float)
    - pip_value: monetary value per pip for 1 lot (float)
    - min_lot, max_lot: bounds for the returned lot size

    Returns:
    - lot size (float)

    Note: This is a simple, conservative formula. Replace with broker/symbol-specific
    calculations for production (consider currency pair, quote currency, leverage).
    """
    try:
        balance = float(balance)
        risk_percent = float(risk_percent)
        stop_loss_pips = float(stop_loss_pips)
        pip_value = float(pip_value)
    except Exception:
        return min_lot

    if stop_loss_pips <= 0 or pip_value <= 0:
        return min_lot

    risk_amount = balance * (risk_percent / 100.0)
    lot = risk_amount / (stop_loss_pips * pip_value)

    # Clamp to sensible bounds
    if lot < min_lot:
        return min_lot
    if lot > max_lot:
        return max_lot
    return round(lot, 2)
