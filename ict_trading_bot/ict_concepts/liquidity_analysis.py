"""
Liquidity and Order Block Analysis
==================================
Handles advanced ICT concepts for liquidity zones and OB strength.
"""

def is_premium_discount_optimal(price: float, fib_levels: dict, direction: str) -> bool:
    """
    Determine if price is in the optimal zone (Discount for Buys, Premium for Sells).
    """
    equilibrium = fib_levels.get("0.5")
    if equilibrium is None:
        return False

    if direction.upper() == "BUY":
        return price < equilibrium  # Buy in Discount
    else:
        return price > equilibrium  # Sell in Premium

def measure_order_block_strength(symbol: str, timeframe: str) -> float:
    """
    Measures the 'quality' of an Order Block (0.0 to 1.0).
    High strength comes from high displacement (big candle bodies)
    and above-average volume.
    """
    import MetaTrader5 as mt5
    from strategy.pre_trade_analysis import _tf_to_mt5

    tf = _tf_to_mt5(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, 5)
    if rates is None or len(rates) < 2:
        return 0.5

    last_candle = rates[-1]
    body_size = abs(last_candle['close'] - last_candle['open'])
    total_range = max(last_candle['high'] - last_candle['low'], 1e-9)

    displacement = body_size / total_range
    return min(1.0, displacement * 1.5) # Displacement is a key ICT strength signal