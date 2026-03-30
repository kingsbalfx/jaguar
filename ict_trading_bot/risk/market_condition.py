"""
Per-Pair Market Condition Analysis
===================================
Analyzes EACH pair for:
1. Volatility Index (0.0-1.0): How volatile is this pair?
2. Market Condition: "volatile", "consolidating", "stable"
3. ATR Trend: Is volatility increasing or decreasing?
4. Recent Range: How much did price move in last N bars?

Used by Intelligence System to decide:
- Should we trade volatile pairs or consolidating pairs?
- Should we adjust position sizes based on volatility?
- Is this a high-opportunity or high-risk environment per pair?

STRATEGY:
- HIGH volatility (0.7-1.0): Good for breakouts, risky for range trades
- MEDIUM volatility (0.4-0.7): Balanced, good for most strategies  
- LOW volatility (0.0-0.4): Good for consolidation trades, avoid breakouts
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional

import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

VOLATILITY_STATS_FILE = Path(__file__).resolve().parent.parent / "data" / "pair_volatility_analysis.json"


def load_volatility_analysis():
    """Load volatility analysis for all pairs from disk."""
    if VOLATILITY_STATS_FILE.exists():
        try:
            with open(VOLATILITY_STATS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load volatility analysis: {e}")
            return {}
    return {}


def save_volatility_analysis(analysis: dict):
    """Save volatility analysis to disk."""
    try:
        VOLATILITY_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(VOLATILITY_STATS_FILE, 'w') as f:
            json.dump(analysis, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save volatility analysis: {e}")


def calculate_atr(symbol: str, timeframe: str, periods: int = 14) -> Optional[float]:
    """
    Calculate Average True Range for a symbol.
    
    Args:
        symbol: Trading pair (e.g., "EURUSD")
        timeframe: Timeframe string (e.g., "H1", "M15", "D1")
        periods: ATR period (default 14)
    
    Returns:
        ATR value or None if fetch failed
    """
    try:
        tf = mt5.TIMEFRAME_H1 if timeframe == "H1" else mt5.TIMEFRAME_M15
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, periods + 5)
        
        if rates is None or len(rates) < periods:
            return None
        
        atrs = []
        for i in range(periods, len(rates)):
            high = rates[i][1]  # high
            low = rates[i][2]   # low
            prev_close = rates[i-1][4]  # previous close
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            atrs.append(tr)
        
        return sum(atrs[-14:]) / 14 if atrs else None
    except Exception as e:
        logger.debug(f"ATR calculation failed for {symbol}: {e}")
        return None


def analyze_market_condition_per_pair(symbol: str, timeframe: str = "H1") -> Dict:
    """
    Comprehensive market condition analysis for a single pair.
    
    Returns:
        {
            "symbol": "EURUSD",
            "analyzed_at": "2026-03-29T14:30:00",
            "volatility_index": 0.65,  # 0-1 scale
            "market_condition": "volatile",  # "volatile" / "consolidating" / "stable"
            "atr": 0.0045,
            "atr_percent": 0.041,  # ATR as % of price
            "recent_range": 0.0052,  # H-L of last 20 bars
            "recent_range_percent": 0.048,
            "consolidation_strength": 0.35,  # 0-1, if consolidating  
            "volatility_trend": "increasing",  # or "decreasing" or "stable"
            "opportunity_type": "breakout",  # "breakout" / "range" / "balanced"
            "position_size_adjustment": 0.95,  # Multiply normal size by this
            "confidence_adjustment": -0.05,  # Add to confirmation score
            "trades_should_avoid_in_last_hours": 2,  # Hours to avoid this pair if highly volatile
        }
    """
    try:
        # Fetch rates
        tf_map = {
            "H1": mt5.TIMEFRAME_H1,
            "M15": mt5.TIMEFRAME_M15,
            "M5": mt5.TIMEFRAME_M5,
            "D1": mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe, mt5.TIMEFRAME_H1)
        
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, 60)  # Last 60 bars
        if rates is None or len(rates) < 20:
            return {
                "symbol": symbol,
                "analyzed_at": datetime.utcnow().isoformat(),
                "volatility_index": 0.5,
                "market_condition": "unknown",
                "atr": 0.0,
                "atr_percent": 0.0,
                "recent_range": 0.0,
                "recent_range_percent": 0.0,
                "consolidation_strength": 0.0,
                "volatility_trend": "unknown",
                "opportunity_type": "unknown",
                "position_size_adjustment": 0.8,
                "confidence_adjustment": 0.0,
                "trades_should_avoid_in_last_hours": 0,
            }
        
        # Calculate metrics
        current_price = rates[-1][4]  # Last close
        
        # ATR calculation
        atrs = []
        for i in range(1, len(rates)):
            high = rates[i][1]
            low = rates[i][2]
            prev_close = rates[i-1][4]
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            atrs.append(tr)
        
        atr = sum(atrs[-14:]) / 14 if len(atrs) >= 14 else sum(atrs) / len(atrs) if atrs else 0.0
        atr_percent = (atr / current_price * 100) if current_price > 0 else 0.0
        
        # Recent range (last 20 bars)
        recent_20 = rates[-20:]
        recent_high = max(r[1] for r in recent_20)
        recent_low = min(r[2] for r in recent_20)
        recent_range = recent_high - recent_low
        recent_range_percent = (recent_range / current_price * 100) if current_price > 0 else 0.0
        
        # ATR trend (is volatility increasing?)
        recent_atr = sum(atrs[-7:]) / 7 if len(atrs) >= 7 else atr
        older_atr = sum(atrs[-20:-7]) / 13 if len(atrs) >= 20 else atr
        volatility_trend = (
            "increasing" if recent_atr > older_atr * 1.1
            else "decreasing" if recent_atr < older_atr * 0.9
            else "stable"
        )
        
        # Consolidation detection (are prices clustered?)
        consolidation_range = recent_range / atr if atr > 0 else 0.0
        consolidation_strength = max(0.0, 1.0 - (consolidation_range / 3.0))  # 0-1 scale
        
        # Volatility Index (0-1)
        # High ATR % = high volatility
        volatility_index = min(1.0, atr_percent / 0.5)  # Normalize to 50 pips
        if volatility_trend == "increasing":
            volatility_index = min(1.0, volatility_index * 1.2)
        
        # Market condition classification
        if volatility_index > 0.7:
            market_condition = "volatile"
            opportunity_type = "breakout"
            position_size_adjustment = 0.8  # Reduce for volatility
            confidence_adjustment = -0.1
            avoid_hours = 1
        elif volatility_index < 0.3:
            market_condition = "consolidating"
            opportunity_type = "range"
            position_size_adjustment = 0.95  # Slight reduction for range
            confidence_adjustment = 0.05
            avoid_hours = 0
        else:
            market_condition = "stable"
            opportunity_type = "balanced"
            position_size_adjustment = 1.0
            confidence_adjustment = 0.0
            avoid_hours = 0
        
        return {
            "symbol": symbol,
            "analyzed_at": datetime.utcnow().isoformat(),
            "volatility_index": round(volatility_index, 3),
            "market_condition": market_condition,
            "atr": round(atr, 6),
            "atr_percent": round(atr_percent, 3),
            "recent_range": round(recent_range, 6),
            "recent_range_percent": round(recent_range_percent, 3),
            "consolidation_strength": round(consolidation_strength, 3),
            "volatility_trend": volatility_trend,
            "opportunity_type": opportunity_type,
            "position_size_adjustment": position_size_adjustment,
            "confidence_adjustment": confidence_adjustment,
            "trades_should_avoid_in_last_hours": avoid_hours,
        }
    
    except Exception as e:
        logger.warning(f"Market condition analysis failed for {symbol}: {e}")
        return {
            "symbol": symbol,
            "analyzed_at": datetime.utcnow().isoformat(),
            "volatility_index": 0.5,
            "market_condition": "unknown",
            "atr": 0.0,
            "atr_percent": 0.0,
            "recent_range": 0.0,
            "recent_range_percent": 0.0,
            "consolidation_strength": 0.0,
            "volatility_trend": "unknown",
            "opportunity_type": "unknown",
            "position_size_adjustment": 0.8,
            "confidence_adjustment": 0.0,
            "trades_should_avoid_in_last_hours": 0,
        }


def analyze_all_pairs(symbols: list, timeframe: str = "H1") -> Dict[str, Dict]:
    """
    Analyze market conditions for all trading pairs.
    
    Returns:
        {
            "EURUSD": { ...analysis... },
            "GBPJPY": { ...analysis... },
            ...
        }
    """
    analysis = {}
    for symbol in symbols:
        analysis[symbol] = analyze_market_condition_per_pair(symbol, timeframe)
    
    # Save to disk
    existing = load_volatility_analysis()
    existing.update(analysis)
    save_volatility_analysis(existing)
    
    return analysis


def get_volatility_summary(symbols: list = None) -> str:
    """
    Generate human-readable volatility summary for logging.
    
    Example output:
    EURUSD: STABLE (0.32 volatility index) | GBPJPY: VOLATILE (0.78) | XAUUSD: CONSOLIDATING (0.18)
    """
    analysis = load_volatility_analysis()
    
    if not analysis:
        return "[VOLATILITY] No analysis data yet"
    
    summaries = []
    target_symbols = symbols or list(analysis.keys())
    
    for symbol in sorted(target_symbols):
        if symbol not in analysis:
            continue
        
        data = analysis[symbol]
        condition = data.get("market_condition", "unknown").upper()
        vol_index = data.get("volatility_index", 0.0)
        atr = data.get("atr_percent", 0.0)
        
        summaries.append(f"{symbol}: {condition} ({vol_index:.2f} vol, {atr:.2f}% ATR)")
    
    return " | ".join(summaries) if summaries else "[VOLATILITY] No analysis"


def should_trade_pair_based_on_volatility(symbol: str) -> tuple:
    """
    Determine if the pair should be traded based on current market condition.
    
    Returns:
        (should_trade: bool, reason: str, adjustments: dict)
        
    Example:
        (True, "STABLE market for EURUSD, good for any trade", {"position_size": 1.0, "confidence": +0.0})
        (False, "VOLATILE EURUSD, avoid for next 1 hour", {"position_size": 0.8, "confidence": -0.1})
    """
    analysis = load_volatility_analysis()
    
    if symbol not in analysis:
        return True, f"No volatility data for {symbol}, trading allowed", {
            "position_size_adjustment": 1.0,
            "confidence_adjustment": 0.0,
        }
    
    data = analysis[symbol]
    condition = data.get("market_condition", "unknown")
    volatility = data.get("volatility_index", 0.5)
    avoid_hours = data.get("trades_should_avoid_in_last_hours", 0)
    
    if avoid_hours > 0:
        return False, f"VOLATILE {symbol} ({volatility:.2f}), avoid for {avoid_hours}h", {
            "position_size_adjustment": data.get("position_size_adjustment", 0.8),
            "confidence_adjustment": data.get("confidence_adjustment", -0.1),
        }
    
    reason = f"{condition.upper()} {symbol} ({volatility:.2f}), trade allowed"
    return True, reason, {
        "position_size_adjustment": data.get("position_size_adjustment", 1.0),
        "confidence_adjustment": data.get("confidence_adjustment", 0.0),
    }
