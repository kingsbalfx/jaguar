"""
Liquidity and Order Block Analysis
==================================
Handles advanced ICT concepts for liquidity zones and OB strength.
"""


def _candle_volume(candle):
    return float(candle.get("volume", candle.get("tick_volume", 0.0)) or 0.0)


def validate_liquidity_zone(liquidity_zone: dict, recent_candles: list, direction: str) -> bool:
    if not isinstance(liquidity_zone, dict) or not isinstance(recent_candles, list):
        return False
    if len(recent_candles) < 3:
        return False

    prices = liquidity_zone.get("prices") or ()
    if len(prices) < 2:
        return False

    zone_low = float(min(prices))
    zone_high = float(max(prices))
    recent = recent_candles[-3:]
    avg_vol = sum(_candle_volume(c) for c in recent_candles[-10:]) / max(1, len(recent_candles[-10:]))

    confirmations = 0
    for candle in recent:
        high = float(candle.get("high", 0.0))
        low = float(candle.get("low", 0.0))
        close = float(candle.get("close", 0.0))
        volume_ok = _candle_volume(candle) >= avg_vol

        if str(direction or "").lower() == "buy":
            touched = low <= zone_high
            reaction = close >= zone_low
        else:
            touched = high >= zone_low
            reaction = close <= zone_high

        if touched and reaction and volume_ok:
            confirmations += 1

    return confirmations >= 2


def is_premium_discount_optimal(price: float, fib_levels: dict, direction: str) -> bool:
    """
    Determine if price is in the optimal zone.
    BUY/bullish -> discount (0.0 to 0.5)
    SELL/bearish -> premium (0.5 to 1.0)
    """
    if not isinstance(fib_levels, dict):
        return False

    low = fib_levels.get("0.0")
    equilibrium = fib_levels.get("0.5")
    high = fib_levels.get("1.0")
    if low is None or equilibrium is None or high is None:
        return False

    context = str(direction or "").lower()
    if context in ("buy", "bullish"):
        return float(low) <= float(price) <= float(equilibrium)
    if context in ("sell", "bearish"):
        return float(equilibrium) <= float(price) <= float(high)
    return False


def measure_order_block_strength(symbol: str, timeframe: str) -> float:
    """
    Measure order block quality using displacement plus multi-candle volume follow-through.
    """
    import MetaTrader5 as mt5
    from strategy.pre_trade_analysis import _tf_to_mt5

    tf = _tf_to_mt5(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, 8)
    if rates is None or len(rates) < 4:
        return 0.0

    candles = list(rates[-4:])
    impulse = candles[-2]
    follow_through = candles[-1]
    average_volume = sum(float(c["tick_volume"]) for c in candles[:-1]) / max(1, len(candles) - 1)

    impulse_range = max(float(impulse["high"]) - float(impulse["low"]), 1e-9)
    impulse_body = abs(float(impulse["close"]) - float(impulse["open"]))
    displacement = impulse_body / impulse_range
    volume_score = min(1.0, float(impulse["tick_volume"]) / max(average_volume, 1e-9))

    follow_range = max(float(follow_through["high"]) - float(follow_through["low"]), 1e-9)
    follow_body = abs(float(follow_through["close"]) - float(follow_through["open"]))
    follow_through_score = follow_body / follow_range

    return round(
        min(1.0, (displacement * 0.5) + (min(volume_score, 1.5) / 1.5 * 0.3) + (follow_through_score * 0.2)),
        3,
    )
