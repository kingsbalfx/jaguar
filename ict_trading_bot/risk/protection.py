import time
import os

TRADE_MEMORY = {}
SYMBOL_CONFIDENCE = {}  # Track per-symbol performance for conditional backtesting

def can_trade(symbol, ob_id, cooldown=300):
    """
    Per-symbol trade protection.
    Only prevents multiple trades on the SAME symbol within cooldown period.
    Different symbols trade independently without interference.
    """
    symbol_key = f"{symbol}_last"
    last_trade = TRADE_MEMORY.get(symbol_key)

    if not last_trade:
        return True

    # Allow new trade if cooldown passed for this symbol
    if time.time() - last_trade < cooldown:
        return False

    return True


def register_trade(symbol, ob_id):
    """Register trade for symbol (not per order block)."""
    symbol_key = f"{symbol}_last"
    TRADE_MEMORY[symbol_key] = time.time()


def update_symbol_confidence(symbol, win=True, confirmation_score=0.0):
    """
    Track symbol-specific performance for conditional backtesting.
    High confidence = skip backtest. Low confidence = require backtest.
    """
    if symbol not in SYMBOL_CONFIDENCE:
        SYMBOL_CONFIDENCE[symbol] = {
            "wins": 0,
            "losses": 0,
            "avg_confirmation": 0.0,
            "recent_scores": []
        }
    
    stats = SYMBOL_CONFIDENCE[symbol]
    if win:
        stats["wins"] += 1
    else:
        stats["losses"] += 1
    
    stats["recent_scores"].append(confirmation_score)
    if len(stats["recent_scores"]) > 20:
        stats["recent_scores"].pop(0)
    
    stats["avg_confirmation"] = sum(stats["recent_scores"]) / len(stats["recent_scores"]) if stats["recent_scores"] else 0.0


def should_skip_backtest(symbol, confirmation_score):
    """
    Conditionally skip backtest based on symbol confidence.
    High confirmations + good symbol history = skip backtest.
    """
    skip_backtest_env = os.getenv("CONDITIONAL_BACKTESTING_ENABLED", "true").lower() in ("1", "true", "yes")
    if not skip_backtest_env:
        return False
    
    if symbol not in SYMBOL_CONFIDENCE:
        return False  # No history, require backtest
    
    stats = SYMBOL_CONFIDENCE[symbol]
    total_trades = stats["wins"] + stats["losses"]
    
    if total_trades == 0:
        return False
    
    win_rate = stats["wins"] / total_trades
    confidence_threshold = float(os.getenv("CONFIDENCE_SCORE_FOR_BACKTEST_SKIP", "7.0"))
    min_win_rate = float(os.getenv("SYMBOL_WIN_RATE_FOR_BACKTEST_SKIP", "0.60"))
    
    # Skip backtest if:
    # 1. High confirmation score AND
    # 2. Symbol has good historical win rate AND
    # 3. Recent confirmations are consistently high
    skip = (
        confirmation_score >= confidence_threshold
        and win_rate >= min_win_rate
        and stats["avg_confirmation"] >= confidence_threshold
    )
    
    return skip


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
