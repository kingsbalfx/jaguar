"""
DAILY + 4HR BRIEF CONTEXT ANALYSIS
===================================
Analyzes Daily (24HR) and 4HR charts for:
- Support/Resistance levels (S/R)
- Fair Value Gaps (FVGs) - zones that need filling
- Order Blocks (OBs) - from recent sweeps
- Volume Balance - if volume is balanced or imbalanced
- Price Action - rejection candles, reversals

This is the BRIEF CONTEXT CHECK before trading on H1→M15→M5→M1.

Key Features:
- Gets Daily (24HR) OHLC + structure
- Gets 4HR OHLC + recent swings
- Identifies FVGs (gaps in price action)
- Detects Order Blocks (from major moves)
- Analyzes volume imbalance
- Provides liquidity map for the day
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


def detect_fvgs(symbol: str, timeframe: int = mt5.TIMEFRAME_D1, lookback: int = 50) -> Dict:
    """
    Detect Fair Value Gaps (FVGs) - zones where price has created gaps that need filling.
    
    FVG = Gap between candles where price may eventually return
    
    Returns:
        {
            "symbol": "GBPJPY",
            "timeframe": "D1",
            "fvgs": [
                {
                    "type": "bullish",  # or "bearish"
                    "top": 145.800,     # Resistance of FVG (upper boundary)
                    "bottom": 145.650,  # Support of FVG (lower boundary)
                    "formed_after_candle": 10,  # Candle index
                    "power": "high",    # based on gap size
                }
            ]
        }
    """
    if not mt5.initialize():
        return {"error": "MT5 not initialized", "symbol": symbol}
    
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        
        if rates is None or len(rates) < 3:
            return {"error": "Not enough candles", "symbol": symbol}
        
        fvgs = []
        
        for i in range(1, len(rates) - 1):
            prev_high = float(rates[i-1]['high'])
            prev_low = float(rates[i-1]['low'])
            curr_high = float(rates[i]['high'])
            curr_low = float(rates[i]['low'])
            next_high = float(rates[i+1]['high'])
            next_low = float(rates[i+1]['low'])
            
            # BULLISH FVG: current candle low > previous candle high (gap up)
            if curr_low > prev_high:
                gap_size = curr_low - prev_high
                if gap_size > 0:
                    fvgs.append({
                        "type": "bullish",
                        "top": round(curr_low, 5),
                        "bottom": round(prev_high, 5),
                        "gap_size": round(gap_size, 5),
                        "formed_at_candle": i,
                        "power": "high" if gap_size > (max(rates['high']) - min(rates['low'])) * 0.01 else "normal"
                    })
            
            # BEARISH FVG: current candle high < previous candle low (gap down)
            elif curr_high < prev_low:
                gap_size = prev_low - curr_high
                if gap_size > 0:
                    fvgs.append({
                        "type": "bearish",
                        "top": round(prev_low, 5),
                        "bottom": round(curr_high, 5),
                        "gap_size": round(gap_size, 5),
                        "formed_at_candle": i,
                        "power": "high" if gap_size > (max(rates['high']) - min(rates['low'])) * 0.01 else "normal"
                    })
        
        return {
            "symbol": symbol,
            "timeframe": "D1" if timeframe == mt5.TIMEFRAME_D1 else "4H",
            "fvgs": fvgs[:5],  # Return latest 5 FVGs
            "total_fvgs": len(fvgs),
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {"error": str(e), "symbol": symbol}
    
    finally:
        mt5.shutdown()


def detect_order_blocks(symbol: str, timeframe: int = mt5.TIMEFRAME_D1, lookback: int = 50) -> Dict:
    """
    Detect Order Blocks (OBs) - zones from recent strong moves that often act as support/resistance.
    
    OB = Price zone where a strong move originated from (often has trapped liquidity)
    
    Returns:
        {
            "symbol": "GBPJPY",
            "timeframe": "D1",
            "order_blocks": [
                {
                    "type": "bullish",  # or "bearish"
                    "high": 145.850,    # Top of order block
                    "low": 145.550,     # Bottom of order block
                    "formed_after_candle": 15,
                    "strength": "strong"  # based on candle size
                }
            ]
        }
    """
    if not mt5.initialize():
        return {"error": "MT5 not initialized", "symbol": symbol}
    
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        
        if rates is None or len(rates) < 3:
            return {"error": "Not enough candles", "symbol": symbol}
        
        order_blocks = []
        
        for i in range(1, len(rates) - 1):
            curr_close = float(rates[i]['close'])
            curr_open = float(rates[i]['open'])
            curr_high = float(rates[i]['high'])
            curr_low = float(rates[i]['low'])
            prev_close = float(rates[i-1]['close'])
            
            # BULLISH OB: Big candle moving up (body is substantial part of range)
            if curr_close > curr_open and (curr_close - curr_open) > (curr_high - curr_low) * 0.6:
                obstructed_zone = (curr_low, curr_high)
                candle_size = curr_close - curr_open
                
                if candle_size > 0:
                    order_blocks.append({
                        "type": "bullish",
                        "high": round(curr_high, 5),
                        "low": round(curr_low, 5),
                        "zone_size": round(candle_size, 5),
                        "formed_at_candle": i,
                        "strength": "strong" if candle_size > (max(rates['high']) - min(rates['low'])) * 0.01 else "normal"
                    })
            
            # BEARISH OB: Big candle moving down (body is substantial part of range)
            elif curr_open > curr_close and (curr_open - curr_close) > (curr_high - curr_low) * 0.6:
                obstructed_zone = (curr_high, curr_low)
                candle_size = curr_open - curr_close
                
                if candle_size > 0:
                    order_blocks.append({
                        "type": "bearish",
                        "high": round(curr_high, 5),
                        "low": round(curr_low, 5),
                        "zone_size": round(candle_size, 5),
                        "formed_at_candle": i,
                        "strength": "strong" if candle_size > (max(rates['high']) - min(rates['low'])) * 0.01 else "normal"
                    })
        
        return {
            "symbol": symbol,
            "timeframe": "D1" if timeframe == mt5.TIMEFRAME_D1 else "4H",
            "order_blocks": order_blocks[:5],  # Return latest 5 OBs
            "total_order_blocks": len(order_blocks),
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {"error": str(e), "symbol": symbol}
    
    finally:
        mt5.shutdown()


def analyze_volume_balance(symbol: str, timeframe: int = mt5.TIMEFRAME_D1, lookback: int = 50) -> Dict:
    """
    Analyze volume balance - is volume pushing price in a direction strongly?
    
    Returns:
        {
            "symbol": "GBPJPY",
            "balance": "bullish",  # or "bearish" or "balanced"
            "avg_volume": 1000000,
            "recent_volume": 1200000,
            "volume_imbalance_ratio": 1.2,
            "description": "Strong bullish volume - buyers in control"
        }
    """
    if not mt5.initialize():
        return {"error": "MT5 not initialized", "symbol": symbol}
    
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        
        if rates is None or len(rates) < 10:
            return {"error": "Not enough candles", "symbol": symbol}
        
        # Get average volume
        avg_volume = np.mean(rates['tick_volume'])
        
        # Get recent volume (last 3 candles average)
        recent_volume = np.mean(rates['tick_volume'][-3:])
        
        # Get buy/sell volumes (simplified: based on close > open or close < open)
        up_volume = 0
        down_volume = 0
        
        for i in range(len(rates)):
            if rates[i]['close'] > rates[i]['open']:
                up_volume += rates[i]['tick_volume']
            else:
                down_volume += rates[i]['tick_volume']
        
        volume_ratio = up_volume / (down_volume + 1)  # Avoid division by zero
        
        # Determine balance
        if volume_ratio > 1.3:
            balance = "bullish"
            description = f"Strong bullish volume - buyers in control (ratio: {volume_ratio:.2f})"
        elif volume_ratio < 0.7:
            balance = "bearish"
            description = f"Strong bearish volume - sellers in control (ratio: {volume_ratio:.2f})"
        else:
            balance = "balanced"
            description = f"Balanced volume - no clear direction (ratio: {volume_ratio:.2f})"
        
        return {
            "symbol": symbol,
            "timeframe": "D1" if timeframe == mt5.TIMEFRAME_D1 else "4H",
            "balance": balance,
            "avg_volume": round(avg_volume, 0),
            "recent_volume": round(recent_volume, 0),
            "volume_imbalance_ratio": round(volume_ratio, 2),
            "description": description,
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {"error": str(e), "symbol": symbol}
    
    finally:
        mt5.shutdown()


def analyze_price_action(symbol: str, timeframe: int = mt5.TIMEFRAME_D1, lookback: int = 20) -> Dict:
    """
    Analyze price action - rejection candles, reversals, momentum patterns
    
    Returns:
        {
            "symbol": "GBPJPY",
            "recent_structure": "bullish",  # or "bearish" or "consolidating"
            "rejection_candles_count": 2,
            "strongest_candle": {"size": 0.850, "type": "bullish", "position": "recent"},
            "price_action_quality": "strong"  # or "weak" or "consolidating"
        }
    """
    if not mt5.initialize():
        return {"error": "MT5 not initialized", "symbol": symbol}
    
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        
        if rates is None or len(rates) < 5:
            return {"error": "Not enough candles", "symbol": symbol}
        
        rejection_candles = 0
        bullish_candles = 0
        bearish_candles = 0
        candle_sizes = []
        
        for i in range(len(rates)):
            high = float(rates[i]['high'])
            low = float(rates[i]['low'])
            close = float(rates[i]['close'])
            open_p = float(rates[i]['open'])
            
            candle_size = high - low
            candle_sizes.append(candle_size)
            
            # Rejection candle: long wick, small body
            wick_size_top = high - max(close, open_p)
            wick_size_bottom = min(close, open_p) - low
            body_size = abs(close - open_p)
            
            if (wick_size_top > body_size * 2 or wick_size_bottom > body_size * 2) and body_size > 0:
                rejection_candles += 1
            
            if close > open_p:
                bullish_candles += 1
            elif close < open_p:
                bearish_candles += 1
        
        # Recent structure
        if bullish_candles > bearish_candles * 1.5:
            structure = "bullish"
        elif bearish_candles > bullish_candles * 1.5:
            structure = "bearish"
        else:
            structure = "consolidating"
        
        # Price action quality (based on largest candle)
        largest_candle = max(candle_sizes)
        avg_candle = np.mean(candle_sizes)
        
        if largest_candle > avg_candle * 2:
            quality = "strong"
        else:
            quality = "weak"
        
        return {
            "symbol": symbol,
            "timeframe": "D1" if timeframe == mt5.TIMEFRAME_D1 else "4H",
            "recent_structure": structure,
            "bullish_candles": bullish_candles,
            "bearish_candles": bearish_candles,
            "rejection_candles_count": rejection_candles,
            "largest_candle_size": round(largest_candle, 5),
            "avg_candle_size": round(avg_candle, 5),
            "price_action_quality": quality,
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {"error": str(e), "symbol": symbol}
    
    finally:
        mt5.shutdown()


def print_daily_4hr_brief_report(symbol: str):
    """
    Print a comprehensive BRIEF CONTEXT report for Daily + 4HR.
    This is what you check FIRST before diving into H1→M15→M5→M1.
    """
    print("\n" + "=" * 100)
    print(f"[DAILY + 4HR BRIEF CONTEXT CHECK] {symbol}")
    print("=" * 100)
    
    # Daily levels
    daily_levels = get_previous_day_levels(symbol)
    if "error" not in daily_levels:
        print(f"\n📊 DAILY (24HR) STRUCTURE:")
        print(f"   High: {daily_levels['high']:.5f} | Low: {daily_levels['low']:.5f} | Range: {daily_levels['range']:.5f}")
        print(f"   Bias: {daily_levels['broken_description']}")
    
    # Daily FVGs
    daily_fvgs = detect_fvgs(symbol, mt5.TIMEFRAME_D1, lookback=30)
    if "fvgs" in daily_fvgs and daily_fvgs["fvgs"]:
        print(f"\n📍 DAILY FVGs (Fair Value Gaps):")
        for fvg in daily_fvgs["fvgs"][:3]:
            print(f"   {fvg['type'].upper()}: {fvg['bottom']:.5f} - {fvg['top']:.5f} (Gap: {fvg['gap_size']:.5f})")
    
    # Daily Order Blocks
    daily_obs = detect_order_blocks(symbol, mt5.TIMEFRAME_D1, lookback=30)
    if "order_blocks" in daily_obs and daily_obs["order_blocks"]:
        print(f"\n🔒 DAILY ORDER BLOCKS:")
        for ob in daily_obs["order_blocks"][:3]:
            print(f"   {ob['type'].upper()}: {ob['low']:.5f} - {ob['high']:.5f} (Size: {ob['zone_size']:.5f})")
    
    # Daily Volume Balance
    daily_vol = analyze_volume_balance(symbol, mt5.TIMEFRAME_D1, lookback=30)
    if "balance" in daily_vol:
        print(f"\n📈 DAILY VOLUME BALANCE:")
        print(f"   {daily_vol['description']}")
    
    # Daily Price Action
    daily_pa = analyze_price_action(symbol, mt5.TIMEFRAME_D1, lookback=20)
    if "recent_structure" in daily_pa:
        print(f"\n⚡ DAILY PRICE ACTION:")
        print(f"   Structure: {daily_pa['recent_structure'].upper()}")
        print(f"   Quality: {daily_pa['price_action_quality'].upper()}")
        print(f"   Rejection Candles: {daily_pa['rejection_candles_count']}")
    
    print("\n" + "-" * 100)
    print(f"[CONTEXT DECISION]: Check if Daily shows clear bias & good structure")
    print(f"   ✅ CONTINUE to 4HR if: Bias is clear + Volume is directional + Price Action is strong")
    print(f"   ❌ SKIP if: No clear bias OR mixed signals OR consolidating")
    print("\n" + "=" * 100 + "\n")



    # Example usage - DAILY + 4HR BRIEF CHECK
    symbols = ["GBPJPY", "EURUSD", "XAGUSD", "DOGEUSD"]
    
    for symbol in symbols:
        print_daily_4hr_brief_report(symbol)
