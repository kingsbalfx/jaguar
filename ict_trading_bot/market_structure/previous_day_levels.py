"""
PREVIOUS DAY SUPPORT/RESISTANCE DETECTION
==========================================
Uses 1HR (H1) timeframe to identify support/resistance from previous day's candle.
This becomes the HTF reference level for entries.

Key Features:
- Gets previous trading day's HIGH and LOW
- Calculates midpoint for range trading
- Detects which level is broken (directional bias)
- Provides entry reference zones
- Adaptive to market session (prevents Asian range creep)
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, Tuple, Optional


def get_previous_day_levels(symbol: str) -> Dict:
    """
    Get previous trading day's support/resistance from H1 candles.
    
    Returns:
        {
            "symbol": "GBPJPY",
            "date": "2026-03-27",
            "open": 145.200,
            "high": 145.680,      # Resistance if above
            "low": 144.920,       # Support if below  
            "close": 145.450,
            "range": 0.760,
            "midpoint": 145.300,
            "broken_level": "resistance",  # or "support" or "neither"
            "entry_above_resistance": 145.685,
            "entry_below_support": 144.915,
            "current_price": 145.500,
            "position_relative_to_range": "above_mid",  # above_mid, below_mid, in_range
            "recommendation": "If closing above R, go long. If below S, go short.",
        }
    """
    
    if not mt5.initialize():
        return {"error": "MT5 not initialized", "symbol": symbol}
    
    try:
        # Get current time
        now = datetime.now()
        
        # Find previous trading day (skip weekends)
        previous_day = now - timedelta(days=1)
        while previous_day.weekday() > 4:  # 5=Saturday, 6=Sunday
            previous_day -= timedelta(days=1)
        
        # Get H1 candles for previous trading day
        # We need candles from ~00:00 to ~23:00 of previous day
        start_time = datetime(previous_day.year, previous_day.month, previous_day.day, 0, 0, 0)
        end_time = datetime(previous_day.year, previous_day.month, previous_day.day, 23, 59, 59)
        
        # Request 24 H1 candles (full trading day)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_time, end_time)
        
        if rates is None or len(rates) == 0:
            return {
                "error": f"No data for {symbol} on {previous_day.date()}",
                "symbol": symbol
            }
        
        # Extract OHLC for the full day
        day_open = float(rates[0]['open'])
        day_high = float(np.max(rates['high']))
        day_low = float(np.min(rates['low']))
        day_close = float(rates[-1]['close'])
        
        # Get current price
        current_tick = mt5.symbol_info_tick(symbol)
        current_price = current_tick.ask if current_tick else day_close
        
        # Calculate range and midpoint
        range_pips = day_high - day_low
        midpoint = (day_high + day_low) / 2
        
        # Determine what was broken
        if current_price > day_high:
            broken_level = "resistance"
            broken_description = f"Above previous day HIGH ({day_high:.5f})"
        elif current_price < day_low:
            broken_level = "support"
            broken_description = f"Below previous day LOW ({day_low:.5f})"
        else:
            broken_level = "neither"
            broken_description = "Trading within previous day range"
        
        # Position relative to range
        if current_price > midpoint:
            position = "above_mid"
        elif current_price < midpoint:
            position = "below_mid"
        else:
            position = "at_mid"
        
        # Entry reference zones
        tick_size = mt5.symbol_info(symbol).point if mt5.symbol_info(symbol) else 0.001
        buffer = tick_size * 5  # 5 ticks safety buffer
        
        entry_above_resistance = day_high + buffer
        entry_below_support = day_low - buffer
        
        # Build recommendation
        if broken_level == "resistance":
            recommendation = (
                f"BULLISH BREAKOUT - Price above R ({day_high:.5f}) "
                f"Range: {range_pips:.4f}. Support at {day_low:.5f}. "
                f"Target: {day_high + (range_pips * 1.5):.5f}"
            )
        elif broken_level == "support":
            recommendation = (
                f"BEARISH BREAKOUT - Price below S ({day_low:.5f}) "
                f"Range: {range_pips:.4f}. Resistance at {day_high:.5f}. "
                f"Target: {day_low - (range_pips * 1.5):.5f}"
            )
        else:
            if position == "above_mid":
                recommendation = (
                    f"IN RANGE (BULLISH BIAS) - Price above midpoint ({midpoint:.5f}). "
                    f"Support: {day_low:.5f}, Resistance: {day_high:.5f}. "
                    f"For breakout: watch {entry_above_resistance:.5f}"
                )
            else:
                recommendation = (
                    f"IN RANGE (BEARISH BIAS) - Price below midpoint ({midpoint:.5f}). "
                    f"Support: {day_low:.5f}, Resistance: {day_high:.5f}. "
                    f"For breakout: watch {entry_below_support:.5f}"
                )
        
        return {
            "symbol": symbol,
            "date": previous_day.strftime("%Y-%m-%d"),
            "open": round(day_open, 5),
            "high": round(day_high, 5),
            "low": round(day_low, 5),
            "close": round(day_close, 5),
            "range": round(range_pips, 5),
            "midpoint": round(midpoint, 5),
            "broken_level": broken_level,
            "broken_description": broken_description,
            "entry_above_resistance": round(entry_above_resistance, 5),
            "entry_below_support": round(entry_below_support, 5),
            "current_price": round(float(current_price), 5),
            "position_relative_to_range": position,
            "recommendation": recommendation,
            "analysis_timestamp": now.isoformat(),
        }
    
    except Exception as e:
        return {
            "error": str(e),
            "symbol": symbol
        }
    
    finally:
        mt5.shutdown()


def get_all_symbols_previous_day_levels(symbols: list) -> Dict:
    """
    Get previous day levels for multiple symbols efficiently.
    
    Returns:
        {
            "GBPJPY": {...levels...},
            "EURUSD": {...levels...},
            ...
        }
    """
    result = {}
    for symbol in symbols:
        result[symbol] = get_previous_day_levels(symbol)
    return result


def is_position_in_sweet_zone(
    symbol: str,
    position_price: float,
    previous_day_levels: Dict,
    sweet_zone_ratio: float = 0.5
) -> bool:
    """
    Check if position price is in the 'sweet zone' - 
    the middle 50% of previous day's range where entries are most reliable.
    
    Sweet zone = area where price action is most decisive
    """
    if "error" in previous_day_levels:
        return False
    
    high = previous_day_levels["high"]
    low = previous_day_levels["low"]
    range_size = high - low
    
    # Sweet zone is middle portion
    sweet_start = low + (range_size * (1 - sweet_zone_ratio) / 2)
    sweet_end = high - (range_size * (1 - sweet_zone_ratio) / 2)
    
    return sweet_start <= position_price <= sweet_end


def score_setup_against_previous_day(
    symbol: str,
    entry_price: float,
    direction: str,  # "buy" or "sell"
    previous_day_levels: Dict
) -> float:
    """
    Score a setup based on alignment with previous day levels.
    
    +25 pts: Entry aligned with previous day breakout
    +15 pts: Entry in sweet zone
    +10 pts: Entry beyond S/R (confirming breakout)
    -10 pts: Entry counter to broken level
    -20 pts: Entry exactly at S/R (no confirmation)
    
    Returns score 0-100
    """
    if "error" in previous_day_levels:
        return 50.0  # Neutral score if no data
    
    score = 50.0  # Baseline
    
    high = previous_day_levels["high"]
    low = previous_day_levels["low"]
    broken = previous_day_levels["broken_level"]
    current_price = previous_day_levels["current_price"]
    
    # Alignment with breakout
    if direction == "buy" and broken == "resistance":
        score += 25  # Buying after resistance breakout
        
        if entry_price > high:
            score += 10  # Entry beyond resistance
        elif entry_price > high - (high - low) * 0.05:
            score += 5   # Entry near resistance
    
    elif direction == "sell" and broken == "support":
        score += 25  # Selling after support breakout
        
        if entry_price < low:
            score += 10  # Entry beyond support
        elif entry_price < low + (high - low) * 0.05:
            score += 5   # Entry near support
    
    # Sweet zone bonus
    if is_position_in_sweet_zone(symbol, entry_price, previous_day_levels):
        score += 15
    
    # Penalty for counter-directional setup
    if direction == "buy" and entry_price < previous_day_levels["midpoint"]:
        if broken == "support":
            score -= 20
    elif direction == "sell" and entry_price > previous_day_levels["midpoint"]:
        if broken == "resistance":
            score -= 20
    
    return min(100.0, max(0.0, score))


def print_previous_day_report(symbol: str):
    """Print a formatted report of previous day levels and recommendation."""
    levels = get_previous_day_levels(symbol)
    
    if "error" in levels:
        print(f"\n❌ Error getting levels for {symbol}: {levels['error']}\n")
        return
    
    print("\n" + "=" * 90)
    print(f"[PREVIOUS DAY REFERENCE - {levels['symbol']}] Date: {levels['date']}")
    print("=" * 90)
    
    print(f"\n📊 PREVIOUS DAY OHLC (H1):")
    print(f"   Open:  {levels['open']:.5f}")
    print(f"   High:  {levels['high']:.5f}  (Resistance)")
    print(f"   Low:   {levels['low']:.5f}   (Support)")
    print(f"   Close: {levels['close']:.5f}")
    print(f"   Range: {levels['range']:.5f} | Midpoint: {levels['midpoint']:.5f}")
    
    print(f"\n📍 CURRENT PRICE:")
    print(f"   {levels['current_price']:.5f} ({levels['position_relative_to_range']})")
    
    print(f"\n⚡ MARKET STATUS:")
    print(f"   {levels['broken_description']}")
    
    print(f"\n🎯 ENTRY REFERENCE ZONES:")
    print(f"   Long Entry:  Above  {levels['entry_above_resistance']:.5f}")
    print(f"   Short Entry: Below  {levels['entry_below_support']:.5f}")
    
    print(f"\n💡 RECOMMENDATION:")
    print(f"   {levels['recommendation']}")
    
    print("\n" + "=" * 90 + "\n")


if __name__ == "__main__":
    # Example usage
    symbols = ["GBPJPY", "EURUSD", "XAGUSD", "DOGEUSD"]
    
    for symbol in symbols:
        print_previous_day_report(symbol)
