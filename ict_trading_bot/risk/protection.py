import json
import time
import os
from pathlib import Path
from utils.persistent_json import load_json_file, save_json_file
from utils.symbol_profile import canonical_symbol, infer_asset_class

TRADE_MEMORY = {}


def _get_trade_memory_file() -> Path:
    env_path = os.getenv("TRADE_MEMORY_STORAGE_PATH")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parent.parent / "data" / "trade_memory_runtime.json"


def _load_trade_memory():
    return load_json_file(_get_trade_memory_file(), {"setups": {}, "day": None, "day_start_equity": None})


def _save_trade_memory(data):
    save_json_file(_get_trade_memory_file(), data)

def _get_confidence_file() -> Path:
    env_path = os.getenv("CONFIDENCE_STORAGE_PATH")
    if env_path: return Path(env_path)
    return Path(__file__).resolve().parent.parent / "data" / "symbol_confidence_runtime.json"


def _load_symbol_confidence():
    """Load persistent symbol confidence memory from disk."""
    return load_json_file(_get_confidence_file(), {})


def _save_symbol_confidence(data):
    """Persist symbol confidence memory so restart/network issues do not wipe it."""
    try:
        save_json_file(_get_confidence_file(), data)
    except Exception:
        pass


SYMBOL_CONFIDENCE = _load_symbol_confidence()  # Track per-symbol performance for conditional backtesting


def _symbol_key(symbol):
    return canonical_symbol(symbol)


def _build_symbol_confidence_bucket(symbol_key):
    return {
        "symbol": symbol_key,
        "asset_class": infer_asset_class(symbol_key),
        "wins": 0,
        "losses": 0,
        "avg_confirmation": 0.0,
        "recent_scores": [],
    }


def _normalize_confirmation_score(score):
    """Normalize legacy 0-10 and weighted 0-100 confirmation scores to 0-10."""
    try:
        value = float(score)
    except Exception:
        return 0.0

    if value <= 0:
        return 0.0
    if value <= 10.0:
        return max(0.0, min(value, 10.0))
    return max(0.0, min(value, 100.0)) / 10.0


def can_trade(symbol, ob_id=None, cooldown=300, **_ignored):
    """
    Per-symbol trade protection.
    Only prevents multiple trades on the SAME symbol within cooldown period.
    Different symbols trade independently without interference.
    """
    memory = _load_trade_memory()
    setup_key = str(ob_id or f"{_symbol_key(symbol)}_general")
    last_trade = (memory.get("setups") or {}).get(setup_key)

    if not last_trade:
        return True

    # Allow new trade if cooldown passed for this symbol
    if time.time() - last_trade < cooldown:
        return False

    return True


def register_trade(symbol, ob_id):
    """Persist a setup identity so restarts cannot duplicate the same trade."""
    memory = _load_trade_memory()
    setup_key = str(ob_id or f"{_symbol_key(symbol)}_general")
    memory.setdefault("setups", {})[setup_key] = time.time()
    _save_trade_memory(memory)


def setup_identity(symbol, direction, retracement=None):
    zone = retracement or {}
    return "|".join(
        [
            _symbol_key(symbol),
            str(direction or "").lower(),
            str(round(float(zone.get("low", 0.0) or 0.0), 8)),
            str(round(float(zone.get("high", 0.0) or 0.0), 8)),
            str(zone.get("kind") or "general"),
        ]
    )


def daily_loss_allows_trade(account_snapshot):
    """Hard safety gate based on equity loss from the first snapshot of the UTC day."""
    if not account_snapshot:
        return False, "account_snapshot_missing"
    today = time.strftime("%Y-%m-%d", time.gmtime())
    equity = float(account_snapshot.get("equity") or account_snapshot.get("balance") or 0.0)
    memory = _load_trade_memory()
    if memory.get("day") != today or not memory.get("day_start_equity"):
        memory["day"] = today
        memory["day_start_equity"] = equity
        _save_trade_memory(memory)
    start = float(memory.get("day_start_equity") or equity)
    max_loss = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "5.0"))
    loss_pct = max(0.0, (start - equity) / max(start, 1e-9) * 100.0)
    return loss_pct < max_loss, f"daily_loss={loss_pct:.2f}% max={max_loss:.2f}%"


def update_symbol_confidence(symbol, win=True, confirmation_score=0.0):
    """
    Track symbol-specific performance for conditional backtesting.
    High confidence = skip backtest. Low confidence = require backtest.
    """
    global SYMBOL_CONFIDENCE
    symbol_key = _symbol_key(symbol)
    SYMBOL_CONFIDENCE = _load_symbol_confidence()

    if symbol_key not in SYMBOL_CONFIDENCE:
        SYMBOL_CONFIDENCE[symbol_key] = _build_symbol_confidence_bucket(symbol_key)

    stats = SYMBOL_CONFIDENCE[symbol_key]
    stats["symbol"] = symbol_key
    stats["asset_class"] = infer_asset_class(symbol_key)
    if win:
        stats["wins"] += 1
    else:
        stats["losses"] += 1
    
    normalized_score = _normalize_confirmation_score(confirmation_score)
    stats["recent_scores"] = [_normalize_confirmation_score(score) for score in stats["recent_scores"]]
    stats["recent_scores"].append(normalized_score)
    if len(stats["recent_scores"]) > 20:
        stats["recent_scores"].pop(0)
    
    stats["avg_confirmation"] = sum(stats["recent_scores"]) / len(stats["recent_scores"]) if stats["recent_scores"] else 0.0
    _save_symbol_confidence(SYMBOL_CONFIDENCE)


def should_skip_backtest(symbol, confirmation_score):
    """
    Conditionally skip backtest based on symbol confidence.
    High confirmations + good symbol history = skip backtest.
    """
    skip_backtest_env = os.getenv("CONDITIONAL_BACKTESTING_ENABLED", "true").lower() in ("1", "true", "yes")
    if not skip_backtest_env:
        return False
    
    global SYMBOL_CONFIDENCE
    symbol_key = _symbol_key(symbol)
    SYMBOL_CONFIDENCE = _load_symbol_confidence()

    if symbol_key not in SYMBOL_CONFIDENCE:
        return False  # No history, require backtest

    stats = SYMBOL_CONFIDENCE[symbol_key]
    total_trades = stats["wins"] + stats["losses"]
    
    if total_trades == 0:
        return False
    
    win_rate = stats["wins"] / total_trades
    confidence_threshold = float(os.getenv("CONFIDENCE_SCORE_FOR_BACKTEST_SKIP", "7.0"))
    if confidence_threshold > 10.0:
        confidence_threshold = confidence_threshold / 10.0
    min_win_rate = float(os.getenv("SYMBOL_WIN_RATE_FOR_BACKTEST_SKIP", "0.60"))
    normalized_score = _normalize_confirmation_score(confirmation_score)
    
    # Skip backtest if:
    # 1. High confirmation score AND
    # 2. Symbol has good historical win rate AND
    # 3. Recent confirmations are consistently high
    skip = (
        normalized_score >= confidence_threshold
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
