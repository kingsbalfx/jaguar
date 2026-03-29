"""
STRATEGY MEMORY SYSTEM
======================
Tracks which STRATEGIES work best for each symbol/pair/metal/crypto.

This system learns:
1. Which setup types (liquidity, BOS, price_action) are most profitable per symbol
2. Which execution routes (weighted, 4-confirmation, direct) work best
3. Which confirmation types succeed best for each asset class
4. Which trading sessions are most profitable
5. Which strategy combinations give highest win rates

Auto-selects best strategy for each signal based on historical memory!
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

STRATEGY_MEMORY_FILE = Path(__file__).resolve().parent.parent / "data" / "strategy_memory.json"


def load_strategy_memory():
    """Load strategy performance history from disk."""
    if STRATEGY_MEMORY_FILE.exists():
        try:
            with open(STRATEGY_MEMORY_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return _init_empty_memory()
    return _init_empty_memory()


def save_strategy_memory(memory):
    """Save strategy performance history to disk."""
    try:
        STRATEGY_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STRATEGY_MEMORY_FILE, 'w') as f:
            json.dump(memory, f, indent=2)
    except Exception as e:
        print(f"[WARNING] Failed to save strategy memory: {e}")


def _init_empty_memory():
    """Initialize empty memory structure."""
    return {
        "setup_strategies": {},      # Liquidity, BOS, Price Action performance
        "execution_routes": {},       # Weighted, 4-Con, Direct performance
        "session_strategies": {},     # London, NY, Asian session performance  
        "asset_class_strategies": {}, # Forex, Metals, Crypto differences
        "symbol_strategy_matrix": {}, # Best strategy per symbol
        "last_updated": None,
        "total_trades_tracked": 0,
    }


def record_strategy_execution(
    symbol: str,
    setup_types: List[str],        # ["liquidity", "bos", "price_action"]
    execution_route: str,          # "weighted", "4_confirmation", "direct", "conditional_backtest"
    confirmation_type: str,        # "2_confirmation", "4_confirmation", "weighted", etc.
    session: str,                  # "london", "us", "asia"
    asset_class: str,              # "forex", "metals", "crypto"
    confirmation_score: float,     # 0-10
    entry_price: float,
    sl: float,
    tp: float,
    win: bool,
    pnl: float = 0.0,
    bars_held: int = 0,
):
    """
    Record a trade outcome with full strategy context.
    Used to build memory of which strategies work best.
    
    Args:
        symbol: Trading pair (e.g., "GBPJPY")
        setup_types: List of confirmed setups ["liquidity", "bos", "price_action"]
        execution_route: How trade was executed
        confirmation_type: Type of confirmation used
        session: Trading session when trade opened
        asset_class: Asset class (forex, metals, crypto)
        confirmation_score: Quality score at entry
        entry_price: Entry price
        sl: Stop loss
        tp: Take profit
        win: True if profitable
        pnl: Profit/loss amount
        bars_held: Bars held before close
    """
    memory = load_strategy_memory()
    
    # 1. SETUP TYPE PERFORMANCE
    if "setup_strategies" not in memory:
        memory["setup_strategies"] = {}
    
    for setup in setup_types:
        if setup not in memory["setup_strategies"]:
            memory["setup_strategies"][setup] = {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
                "avg_confirmation": 0.0,
                "per_symbol": {}
            }
        
        stat = memory["setup_strategies"][setup]
        stat["total_trades"] += 1
        if win:
            stat["wins"] += 1
        else:
            stat["losses"] += 1
        stat["win_rate"] = stat["wins"] / stat["total_trades"] if stat["total_trades"] > 0 else 0.0
        
        # Track per symbol
        if symbol not in stat["per_symbol"]:
            stat["per_symbol"][symbol] = {"wins": 0, "losses": 0, "total": 0}
        stat["per_symbol"][symbol]["total"] += 1
        if win:
            stat["per_symbol"][symbol]["wins"] += 1
        else:
            stat["per_symbol"][symbol]["losses"] += 1
    
    # 2. EXECUTION ROUTE PERFORMANCE
    if "execution_routes" not in memory:
        memory["execution_routes"] = {}
    
    if execution_route not in memory["execution_routes"]:
        memory["execution_routes"][execution_route] = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "confirmation_types": {}
        }
    
    route_stat = memory["execution_routes"][execution_route]
    route_stat["total_trades"] += 1
    if win:
        route_stat["wins"] += 1
    else:
        route_stat["losses"] += 1
    route_stat["win_rate"] = route_stat["wins"] / route_stat["total_trades"]
    
    # Track confirmation type within route
    if confirmation_type not in route_stat["confirmation_types"]:
        route_stat["confirmation_types"][confirmation_type] = {"wins": 0, "losses": 0, "total": 0}
    route_stat["confirmation_types"][confirmation_type]["total"] += 1
    if win:
        route_stat["confirmation_types"][confirmation_type]["wins"] += 1
    else:
        route_stat["confirmation_types"][confirmation_type]["losses"] += 1
    
    # 3. SESSION PERFORMANCE
    if "session_strategies" not in memory:
        memory["session_strategies"] = {}
    
    if session not in memory["session_strategies"]:
        memory["session_strategies"][session] = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "per_asset_class": {}
        }
    
    session_stat = memory["session_strategies"][session]
    session_stat["total_trades"] += 1
    if win:
        session_stat["wins"] += 1
    else:
        session_stat["losses"] += 1
    session_stat["win_rate"] = session_stat["wins"] / session_stat["total_trades"]
    
    # Track per asset class per session
    if asset_class not in session_stat["per_asset_class"]:
        session_stat["per_asset_class"][asset_class] = {"wins": 0, "losses": 0, "total": 0}
    session_stat["per_asset_class"][asset_class]["total"] += 1
    if win:
        session_stat["per_asset_class"][asset_class]["wins"] += 1
    else:
        session_stat["per_asset_class"][asset_class]["losses"] += 1
    
    # 4. ASSET CLASS PERFORMANCE
    if "asset_class_strategies" not in memory:
        memory["asset_class_strategies"] = {}
    
    if asset_class not in memory["asset_class_strategies"]:
        memory["asset_class_strategies"][asset_class] = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "best_session": None,
            "best_setup": None
        }
    
    ac_stat = memory["asset_class_strategies"][asset_class]
    ac_stat["total_trades"] += 1
    if win:
        ac_stat["wins"] += 1
    else:
        ac_stat["losses"] += 1
    ac_stat["win_rate"] = ac_stat["wins"] / ac_stat["total_trades"]
    
    # 5. SYMBOL-SPECIFIC STRATEGY MATRIX
    if "symbol_strategy_matrix" not in memory:
        memory["symbol_strategy_matrix"] = {}
    
    if symbol not in memory["symbol_strategy_matrix"]:
        memory["symbol_strategy_matrix"][symbol] = {
            "best_setup": None,
            "best_execution_route": None,
            "best_session": None,
            "setup_performance": {},
            "route_performance": {},
            "win_rate": 0.0,
            "trades": 0
        }
    
    sym_matrix = memory["symbol_strategy_matrix"][symbol]
    sym_matrix["trades"] += 1
    if win:
        sym_matrix["wins"] = sym_matrix.get("wins", 0) + 1
    else:
        sym_matrix["losses"] = sym_matrix.get("losses", 0) + 1
    sym_matrix["win_rate"] = sym_matrix.get("wins", 0) / sym_matrix["trades"]
    
    # Track setup performance for this symbol
    for setup in setup_types:
        if setup not in sym_matrix["setup_performance"]:
            sym_matrix["setup_performance"][setup] = {"wins": 0, "losses": 0}
        if win:
            sym_matrix["setup_performance"][setup]["wins"] += 1
        else:
            sym_matrix["setup_performance"][setup]["losses"] += 1
    
    # Track route performance for this symbol
    if execution_route not in sym_matrix["route_performance"]:
        sym_matrix["route_performance"][execution_route] = {"wins": 0, "losses": 0}
    if win:
        sym_matrix["route_performance"][execution_route]["wins"] += 1
    else:
        sym_matrix["route_performance"][execution_route]["losses"] += 1
    
    # Find and update best strategy for this symbol
    if sym_matrix["setup_performance"]:
        best_setup = max(
            sym_matrix["setup_performance"].items(),
            key=lambda x: x[1]["wins"] / (x[1]["wins"] + x[1]["losses"] + 0.001)
        )
        sym_matrix["best_setup"] = best_setup[0]
    
    if sym_matrix["route_performance"]:
        best_route = max(
            sym_matrix["route_performance"].items(),
            key=lambda x: x[1]["wins"] / (x[1]["wins"] + x[1]["losses"] + 0.001)
        )
        sym_matrix["best_execution_route"] = best_route[0]
    
    # 6. OVERALL TRACKING
    memory["last_updated"] = datetime.now().isoformat()
    memory["total_trades_tracked"] += 1
    
    save_strategy_memory(memory)


def get_best_strategy_for_symbol(symbol: str) -> Dict:
    """
    Get the best-performing strategy for a specific symbol.
    
    Returns:
        {
            "symbol": "GBPJPY",
            "best_setup": "liquidity",          # Most reliable setup type
            "best_execution_route": "weighted", # Most reliable execution
            "best_session": "london",           # Most profitable session
            "win_rate": 0.65,
            "trades": 15,
            "recommendation": "Use liquidity setup with weighted execution during London"
        }
    """
    memory = load_strategy_memory()
    
    if "symbol_strategy_matrix" not in memory or symbol not in memory["symbol_strategy_matrix"]:
        return {
            "symbol": symbol,
            "status": "learning",
            "message": "Not enough trades yet to determine best strategy",
            "trades": 0
        }
    
    sym_matrix = memory["symbol_strategy_matrix"][symbol]
    
    return {
        "symbol": symbol,
        "best_setup": sym_matrix.get("best_setup", "any"),
        "best_execution_route": sym_matrix.get("best_execution_route", "any"),
        "best_session": sym_matrix.get("best_session", "any"),
        "win_rate": sym_matrix.get("win_rate", 0.0),
        "trades": sym_matrix.get("trades", 0),
        "wins": sym_matrix.get("wins", 0),
        "losses": sym_matrix.get("losses", 0),
        "recommendation": _generate_recommendation(symbol, sym_matrix, memory)
    }


def get_best_setup_types() -> List[Tuple[str, float]]:
    """Get all setup types ranked by win rate."""
    memory = load_strategy_memory()
    
    if "setup_strategies" not in memory:
        return []
    
    setups = []
    for setup, stat in memory["setup_strategies"].items():
        if stat["total_trades"] > 0:
            setups.append((setup, stat["win_rate"]))
    
    return sorted(setups, key=lambda x: x[1], reverse=True)


def get_best_execution_routes() -> List[Tuple[str, float]]:
    """Get all execution routes ranked by win rate."""
    memory = load_strategy_memory()
    
    if "execution_routes" not in memory:
        return []
    
    routes = []
    for route, stat in memory["execution_routes"].items():
        if stat["total_trades"] > 0:
            routes.append((route, stat["win_rate"]))
    
    return sorted(routes, key=lambda x: x[1], reverse=True)


def get_best_session() -> Dict:
    """Get trading session performance ranking."""
    memory = load_strategy_memory()
    
    if "session_strategies" not in memory:
        return {}
    
    sessions = {}
    for session, stat in memory["session_strategies"].items():
        if stat["total_trades"] > 0:
            sessions[session] = {
                "win_rate": stat["win_rate"],
                "trades": stat["total_trades"],
                "wins": stat["wins"],
                "losses": stat["losses"]
            }
    
    return sessions


def get_asset_class_best_practices() -> Dict:
    """Get best practices for each asset class."""
    memory = load_strategy_memory()
    
    if "asset_class_strategies" not in memory:
        return {}
    
    practices = {}
    for asset_class, stat in memory["asset_class_strategies"].items():
        if stat["total_trades"] > 0:
            # Find best session for this asset class
            best_session = None
            if "session_strategies" in memory:
                for session, s_stat in memory["session_strategies"].items():
                    if asset_class in s_stat.get("per_asset_class", {}):
                        ac_sessions = [(session, s_stat["per_asset_class"][asset_class])]
            
            practices[asset_class] = {
                "win_rate": stat["win_rate"],
                "trades": stat["total_trades"],
                "wins": stat["wins"],
                "losses": stat["losses"],
                "best_session": stat.get("best_session"),
                "best_setup": stat.get("best_setup")
            }
    
    return practices


def get_strategy_memory_report() -> str:
    """Generate comprehensive strategy memory report."""
    memory = load_strategy_memory()
    
    report = "\n" + "=" * 100 + "\n"
    report += "[STRATEGY MEMORY REPORT]\n"
    report += "=" * 100 + "\n\n"
    
    # Setup types ranking
    report += "[SETUP TYPES - Ranked by Win Rate]\n"
    report += "-" * 50 + "\n"
    setups = get_best_setup_types()
    for setup, wr in setups:
        stat = memory["setup_strategies"][setup]
        report += f"  🎯 {setup:15} WR: {wr*100:5.1f}% ({stat['wins']}-{stat['losses']}) "
        report += f"Avg: {stat['avg_confirmation']*10:.1f}pts\n"
    
    # Execution routes ranking
    report += "\n[EXECUTION ROUTES - Ranked by Win Rate]\n"
    report += "-" * 50 + "\n"
    routes = get_best_execution_routes()
    for route, wr in routes:
        stat = memory["execution_routes"][route]
        report += f"  🎯 {route:20} WR: {wr*100:5.1f}% ({stat['wins']}-{stat['losses']})\n"
    
    # Session performance
    report += "\n[SESSION PERFORMANCE]\n"
    report += "-" * 50 + "\n"
    sessions = get_best_session()
    for session, stat in sorted(sessions.items(), key=lambda x: x[1]["win_rate"], reverse=True):
        report += f"  🎯 {session:10} WR: {stat['win_rate']*100:5.1f}% ({stat['wins']}-{stat['losses']})\n"
    
    # Asset class practices
    report += "\n[ASSET CLASS BEST PRACTICES]\n"
    report += "-" * 50 + "\n"
    practices = get_asset_class_best_practices()
    for asset_class, stat in practices.items():
        report += f"  🎯 {asset_class:10} WR: {stat['win_rate']*100:5.1f}% ({stat['wins']}-{stat['losses']})\n"
    
    # Per-symbol summary
    report += "\n[TOP SYMBOLS BY STRATEGY CLARITY]\n"
    report += "-" * 50 + "\n"
    if "symbol_strategy_matrix" in memory:
        symbols = sorted(
            memory["symbol_strategy_matrix"].items(),
            key=lambda x: x[1].get("trades", 0),
            reverse=True
        )
        for symbol, matrix in symbols[:10]:
            if matrix.get("trades", 0) >= 5:
                report += f"  🎯 {symbol:10} {matrix.get('wins', 0)}-{matrix.get('losses', 0)} "
                report += f"WR: {matrix.get('win_rate', 0)*100:5.1f}% "
                report += f"Best: {matrix.get('best_setup', '?')}\n"
    
    report += "\n" + "=" * 100 + "\n"
    report += f"Total Trades Tracked: {memory.get('total_trades_tracked', 0)}\n"
    report += f"Last Updated: {memory.get('last_updated', 'Never')}\n"
    report += "=" * 100 + "\n"
    
    return report


def _generate_recommendation(symbol: str, matrix: Dict, memory: Dict) -> str:
    """Generate actionable recommendation for trading this symbol."""
    if matrix.get("trades", 0) < 5:
        return "Keep collecting data (need 5+ trades)"
    
    best_setup = matrix.get("best_setup", "liquidity")
    best_route = matrix.get("best_execution_route", "weighted")
    wr = matrix.get("win_rate", 0)
    
    if wr >= 0.70:
        confidence = "STRONG - High confidence"
    elif wr >= 0.60:
        confidence = "GOOD - Decent confidence"
    elif wr >= 0.50:
        confidence = "NEUTRAL - Need more data"
    else:
        confidence = "WEAK - Avoid or re-evaluate"
    
    setup_desc = {
        "liquidity": "liquidity sweeps",
        "bos": "break of structure",
        "price_action": "price action patterns"
    }.get(best_setup, best_setup)
    
    return f"{confidence}: Trade {symbol} using {setup_desc} with {best_route} execution"


def reset_strategy_memory(symbol: str = None):
    """Reset strategy memory entirely or for specific symbol."""
    memory = load_strategy_memory()
    
    if symbol:
        if "symbol_strategy_matrix" in memory and symbol in memory["symbol_strategy_matrix"]:
            memory["symbol_strategy_matrix"].pop(symbol)
            print(f"[STRATEGY MEMORY] Reset memory for {symbol}")
    else:
        memory = _init_empty_memory()
        print("[STRATEGY MEMORY] Reset all strategy memory")
    
    save_strategy_memory(memory)
