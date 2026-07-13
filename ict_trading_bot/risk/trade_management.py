"""
Dynamic Trade Manager with trailing stops and aggressive position sizing.

Three levels of stop adjustment:
1. Breakeven at 0.5R — SL moved to entry + small buffer
2. Lock 0.5R profit at 1.0R — SL guarantees minimum gain
3. Continuous structural trail — SL follows key levels as price moves

Crypto profit lock: minimum 0.30 USD profit before any SL adjustment.
Scaled by position size: larger lots = higher threshold.
"""

from typing import Dict, Optional, List


def _crypto_min_profit_for_lot(lot: float) -> float:
    """
    Crypto minimum profit to lock in (USD) before SL adjustments.
    Base: 0.30 USD for 0.01 lots.
    Scaled proportionally: 0.10 lots = 3.00 USD, 1.00 lots = 30.00 USD.
    """
    base_lot = 0.01
    base_profit = 0.30
    return base_profit * (lot / base_lot)


def _nearest_structural_level(
    price: float,
    direction: str,
    swings: Optional[List[Dict]] = None,
    order_blocks: Optional[List[Dict]] = None,
    fvgs: Optional[List[Dict]] = None,
    point: float = 0.0001,
) -> Optional[float]:
    """Find the nearest structural level to trail SL behind."""
    candidates = []

    # Order Blocks (unmitigated)
    if order_blocks:
        for ob in order_blocks:
            if not isinstance(ob, dict):
                continue
            if ob.get("mitigated", False):
                continue
            ob_type = str(ob.get("type", "")).lower()
            if direction == "buy" and "bullish" not in ob_type and "buy" not in ob_type:
                continue
            if direction == "sell" and "bearish" not in ob_type and "sell" not in ob_type:
                continue
            low = ob.get("low", ob.get("price_low", 0))
            high = ob.get("high", ob.get("price_high", 0))
            try:
                low = float(low)
                high = float(high)
            except (TypeError, ValueError):
                continue
            if direction == "buy":
                if low < price:
                    candidates.append(("ob", low))
            else:
                if high > price:
                    candidates.append(("ob", high))

    # Mitigated FVGs (origin candle acts as support/resistance)
    if fvgs:
        for fvg in fvgs:
            if not isinstance(fvg, dict):
                continue
            if not fvg.get("mitigated", False):
                continue
            try:
                if direction == "buy":
                    ref = float(fvg.get("reference_low", fvg.get("low", fvg.get("high", 0))))
                    if ref < price:
                        candidates.append(("fvg", ref))
                else:
                    ref = float(fvg.get("reference_high", fvg.get("high", fvg.get("low", 0))))
                    if ref > price:
                        candidates.append(("fvg", ref))
            except (TypeError, ValueError):
                continue

    # Strong swing points
    if swings:
        swing_type = "low" if direction == "buy" else "high"
        for s in swings:
            if s.get("type") != swing_type:
                continue
            if s.get("strength") == "weak":
                continue
            try:
                p = float(s["price"])
            except (TypeError, ValueError):
                continue
            if direction == "buy" and p < price:
                candidates.append(("swing_strong", p))
            elif direction == "sell" and p > price:
                candidates.append(("swing_strong", p))

    # Weak swing points (fallback)
    if not candidates and swings:
        swing_type = "low" if direction == "buy" else "high"
        for s in swings:
            if s.get("type") != swing_type:
                continue
            try:
                p = float(s["price"])
            except (TypeError, ValueError):
                continue
            if direction == "buy" and p < price:
                candidates.append(("swing_weak", p))
            elif direction == "sell" and p > price:
                candidates.append(("swing_weak", p))

    if not candidates:
        return None

    if direction == "buy":
        best = max(candidates, key=lambda c: c[1])
        return best[1] + point * 5
    else:
        best = min(candidates, key=lambda c: c[1])
        return best[1] - point * 5


def manage_trade(
    trade: Dict,
    price: float,
    swings: Optional[List[Dict]] = None,
    order_blocks: Optional[List[Dict]] = None,
    fvgs: Optional[List[Dict]] = None,
    atr: Optional[float] = None,
    is_crypto: bool = False,
    point: float = 0.0001,
    symbol: str = "",
) -> Optional[Dict]:
    """
    Manage an open trade: trail stop, lock profits, partial close.

    Three stages:
    1. At 0.5R profit -> move SL to breakeven (entry + buffer)
    2. At 1.0R profit -> lock in 0.5R minimum profit
    3. At 1.5R+ profit -> trail behind nearest structural level

    Crypto: waits until unrealized PnL >= 0.30 USD (scaled to lot size)
    before any SL adjustment.
    """
    if not trade:
        return None

    try:
        direction = str(trade.get("direction", "")).lower()
        entry = float(trade.get("entry", 0))
        current_sl = float(trade.get("sl", 0))
        tp = float(trade.get("tp", 0))
        current_price = float(price)
        volume = float(trade.get("volume", 0))
        current_profit = float(trade.get("profit", 0))
    except (TypeError, ValueError, KeyError):
        return None

    if direction not in ("buy", "sell") or entry <= 0 or current_sl <= 0:
        return None

    risk = abs(entry - current_sl)
    if risk <= 0:
        return None

    # Dynamic buffer for breakeven
    buffer = max(atr * 0.3, point * 10) if atr else max(risk * 0.1, point * 10)

    # --- CRYPTO PROFIT LOCK CHECK ---
    if is_crypto:
        min_profit = _crypto_min_profit_for_lot(volume)
        if abs(current_profit) < min_profit:
            return None

    # --- PARTIAL CLOSE AT INITIAL TP ---
    if tp > 0:
        if direction == "buy" and current_price >= tp:
            trade["tp"] = 0.0
            return {"action": "partial_close", "percent": 0.5}
        elif direction == "sell" and current_price <= tp:
            trade["tp"] = 0.0
            return {"action": "partial_close", "percent": 0.5}

    # === STAGE 1: BREAKEVEN AT 0.5R ===
    if direction == "buy":
        if current_price >= entry + risk * 0.5:
            new_sl = entry + buffer
            if new_sl > current_sl and new_sl < current_price:
                trade["sl"] = new_sl
                return {"action": "move_sl", "sl": new_sl}
    else:
        if current_price <= entry - risk * 0.5:
            new_sl = entry - buffer
            if new_sl < current_sl and new_sl > current_price:
                trade["sl"] = new_sl
                return {"action": "move_sl", "sl": new_sl}

    # === STAGE 2: LOCK 0.5R PROFIT AT 1.0R ===
    if direction == "buy":
        if current_price >= entry + risk * 1.0:
            lock_sl = entry + risk * 0.5
            if lock_sl > current_sl and lock_sl < current_price:
                trade["sl"] = lock_sl
                return {"action": "move_sl", "sl": lock_sl}
    else:
        if current_price <= entry - risk * 1.0:
            lock_sl = entry - risk * 0.5
            if lock_sl < current_sl and lock_sl > current_price:
                trade["sl"] = lock_sl
                return {"action": "move_sl", "sl": lock_sl}

    # === STAGE 3: STRUCTURAL TRAIL (1.5R+) ===
    if direction == "buy" and current_price >= entry + risk * 1.5:
        trail_level = _nearest_structural_level(
            current_price, direction, swings, order_blocks, fvgs, point
        )
        if trail_level is not None:
            new_sl = trail_level
            if new_sl > current_sl and new_sl < current_price:
                trade["sl"] = new_sl
                return {"action": "move_sl", "sl": new_sl}
    elif direction == "sell" and current_price <= entry - risk * 1.5:
        trail_level = _nearest_structural_level(
            current_price, direction, swings, order_blocks, fvgs, point
        )
        if trail_level is not None:
            new_sl = trail_level
            if new_sl < current_sl and new_sl > current_price:
                trade["sl"] = new_sl
                return {"action": "move_sl", "sl": new_sl}

    return None