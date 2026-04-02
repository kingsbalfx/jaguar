"""
Per-symbol confidence tracking for conditional backtesting.
Maintains historical performance stats for each trading pair.
"""
from datetime import datetime
from pathlib import Path
from utils.persistent_json import load_json_file, save_json_file
from utils.symbol_profile import canonical_symbol, infer_asset_class

STATS_FILE = Path(__file__).resolve().parent.parent / "data" / "symbol_stats.json"


def load_symbol_stats():
    """Load per-symbol statistics from disk."""
    return load_json_file(STATS_FILE, {})


def save_symbol_stats(stats):
    """Save per-symbol statistics to disk."""
    try:
        save_json_file(STATS_FILE, stats)
    except Exception as e:
        print(f"[WARNING] Failed to save symbol stats: {e}")


def _symbol_key(symbol):
    return canonical_symbol(symbol)


def _build_symbol_stats(symbol_key):
    return {
        "symbol": symbol_key,
        "asset_class": infer_asset_class(symbol_key),
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "confidence_scores": [],
        "avg_confidence": 0.0,
        "last_updated": None,
        "backtests_skipped": 0,
        "backtests_required": 0,
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


def record_symbol_trade(symbol, win=True, confirmation_score=0.0):
    """
    Record a trade outcome for a symbol.
    
    Args:
        symbol: Trading pair (e.g., "GBPJPY")
        win: True if trade was profitable
        confirmation_score: Confirmation score (0-10) at trade entry
    """
    stats = load_symbol_stats()
    symbol_key = _symbol_key(symbol)

    if symbol_key not in stats:
        stats[symbol_key] = _build_symbol_stats(symbol_key)

    sym_stats = stats[symbol_key]
    sym_stats["symbol"] = symbol_key
    sym_stats["asset_class"] = infer_asset_class(symbol_key)
    sym_stats["total_trades"] += 1
    
    if win:
        sym_stats["wins"] += 1
    else:
        sym_stats["losses"] += 1
    
    sym_stats["win_rate"] = sym_stats["wins"] / sym_stats["total_trades"] if sym_stats["total_trades"] > 0 else 0.0
    normalized_score = _normalize_confirmation_score(confirmation_score)
    sym_stats["confidence_scores"] = [
        _normalize_confirmation_score(score) for score in sym_stats.get("confidence_scores", [])
    ]
    sym_stats["confidence_scores"].append(normalized_score)
    
    # Keep only last 50 scores for recent average
    if len(sym_stats["confidence_scores"]) > 50:
        sym_stats["confidence_scores"] = sym_stats["confidence_scores"][-50:]
    
    sym_stats["avg_confidence"] = sum(sym_stats["confidence_scores"]) / len(sym_stats["confidence_scores"]) if sym_stats["confidence_scores"] else 0.0
    sym_stats["last_updated"] = datetime.now().isoformat()
    
    save_symbol_stats(stats)
    return sym_stats


def record_backtest_skip(symbol):
    """Record that we skipped backtest for this symbol."""
    stats = load_symbol_stats()
    symbol_key = _symbol_key(symbol)
    if symbol_key not in stats:
        stats[symbol_key] = _build_symbol_stats(symbol_key)
    stats[symbol_key]["backtests_skipped"] = stats[symbol_key].get("backtests_skipped", 0) + 1
    save_symbol_stats(stats)


def record_backtest_required(symbol):
    """Record that we required backtest for this symbol."""
    stats = load_symbol_stats()
    symbol_key = _symbol_key(symbol)
    if symbol_key not in stats:
        stats[symbol_key] = _build_symbol_stats(symbol_key)
    stats[symbol_key]["backtests_required"] = stats[symbol_key].get("backtests_required", 0) + 1
    save_symbol_stats(stats)


def get_symbol_summary(compact=True):
    """
    Get summary of all symbol stats for logging.
    
    Args:
        compact: If True, return one-liner for heartbeat. If False, return detailed table.
    """
    stats = load_symbol_stats()
    
    if not stats:
        return None
    
    if compact:
        # One-liner for heartbeat: "GBPJPY(9-6:60%), EURUSD(5-2:71%)"
        pairs = []
        for symbol in sorted(stats.keys()):
            s = stats[symbol]
            if s['total_trades'] > 0:
                win_pct = int(s['win_rate'] * 100)
                pairs.append(f"{symbol}({s['wins']}-{s['losses']}:{win_pct}%)")
        
        return " ".join(pairs) if pairs else None
    else:
        # Detailed table
        summary = "\n[SYMBOL STATS SUMMARY]\n"
        summary += "-" * 80 + "\n"
        summary += f"{'Symbol':<12} {'W-L':<10} {'Win%':<8} {'Avg Conf':<10} {'Backtests':<15}\n"
        summary += "-" * 80 + "\n"
        
        for symbol in sorted(stats.keys()):
            s = stats[symbol]
            win_loss = f"{s['wins']}-{s['losses']}"
            win_pct = f"{s['win_rate']*100:.1f}%" if s['total_trades'] > 0 else "N/A"
            avg_conf = f"{s['avg_confidence']:.1f}"
            backtests = f"Skip: {s['backtests_skipped']} | Req: {s['backtests_required']}"
            
            summary += f"{symbol:<12} {win_loss:<10} {win_pct:<8} {avg_conf:<10} {backtests:<15}\n"
        
        summary += "-" * 80 + "\n"
        return summary


def reset_symbol_stats(symbol=None):
    """Reset stats for a symbol or all symbols."""
    stats = load_symbol_stats()
    
    if symbol:
        symbol_key = _symbol_key(symbol)
        if symbol_key in stats:
            stats.pop(symbol_key)
            print(f"[SYMBOL STATS] Reset stats for {symbol_key}")
    else:
        stats.clear()
        print("[SYMBOL STATS] Reset all stats")
    
    save_symbol_stats(stats)
