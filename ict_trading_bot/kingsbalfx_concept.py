# FILE: ict_trading_bot/kingsbalfx_concept.py
"""Kingsbalfx secondary fallback strategy.

This module is intentionally independent from the strict ICT state machine. It
does not mutate or replace the 12-gate ICT logic. It only evaluates a fallback
trade model when the primary ICT state machine has already returned SKIP.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


Direction = str
Candle = Dict[str, float]


@dataclass
class Zone:
    kind: str
    direction: Direction
    low: float
    high: float
    midpoint: float
    levels: Dict[str, float]
    timeframe: str
    source: str
    index: int
    fresh: bool = True
    fill_ratio: float = 0.0

    def contains(self, price: float, tolerance: float = 0.0) -> bool:
        return self.low - tolerance <= price <= self.high + tolerance

    def aligned_with(self, direction: Direction, price: float) -> bool:
        if direction == "buy":
            return self.high <= price or self.contains(price)
        return self.low >= price or self.contains(price)


@dataclass
class Target:
    kind: str
    direction: Direction
    price: float
    timeframe: str
    source: str
    distance: float


@dataclass
class KingsbalfxDecision:
    executable: bool
    reason: str
    direction: Optional[Direction]
    mode: Optional[str]
    entry: Optional[float]
    sl: Optional[float]
    tp: Optional[float]
    rr: float
    target: Optional[Dict[str, Any]]
    entry_zone: Optional[Dict[str, Any]]
    evidence: Dict[str, Any]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _candles(state: Dict[str, Any]) -> List[Candle]:
    out: List[Candle] = []
    for item in state.get("recent_candles") or []:
        try:
            out.append(
                {
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                    "volume": float(item.get("volume", 0.0)),
                    "time": item.get("time", 0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _range(candle: Candle) -> float:
    return max(float(candle["high"]) - float(candle["low"]), 0.0)


def _body(candle: Candle) -> float:
    return abs(float(candle["close"]) - float(candle["open"]))


def _body_ratio(candle: Candle) -> float:
    candle_range = _range(candle)
    return _body(candle) / candle_range if candle_range > 0 else 0.0


def _direction_of(candle: Candle) -> Optional[Direction]:
    if candle["close"] > candle["open"]:
        return "buy"
    if candle["close"] < candle["open"]:
        return "sell"
    return None


def _average_range(candles: Sequence[Candle], period: int = 14) -> float:
    sample = list(candles)[-max(1, period):]
    if not sample:
        return 0.0
    ranges = [_range(candle) for candle in sample]
    return sum(ranges) / max(len(ranges), 1)


def _point_from_price(price: float) -> float:
    if price >= 1000:
        return 0.1
    if price >= 100:
        return 0.01
    if price >= 10:
        return 0.001
    return 0.0001


def _normalize_direction(value: Any) -> Optional[Direction]:
    raw = str(value or "").lower()
    if raw in ("buy", "bull", "bullish", "long"):
        return "buy"
    if raw in ("sell", "bear", "bearish", "short"):
        return "sell"
    return None


def _trend_from_candles(candles: Sequence[Candle]) -> str:
    if len(candles) < 8:
        return "range"
    recent = list(candles)[-8:]
    highs = [candle["high"] for candle in recent]
    lows = [candle["low"] for candle in recent]
    closes = [candle["close"] for candle in recent]
    higher_highs = sum(1 for left, right in zip(highs, highs[1:]) if right > left)
    higher_lows = sum(1 for left, right in zip(lows, lows[1:]) if right > left)
    lower_highs = sum(1 for left, right in zip(highs, highs[1:]) if right < left)
    lower_lows = sum(1 for left, right in zip(lows, lows[1:]) if right < left)
    net_change = closes[-1] - closes[0]
    avg_range = _average_range(recent, period=len(recent))
    if higher_highs >= 4 and higher_lows >= 4 and net_change > avg_range:
        return "bullish"
    if lower_highs >= 4 and lower_lows >= 4 and net_change < -avg_range:
        return "bearish"
    last_four = list(candles)[-4:]
    four_day_range = max(c["high"] for c in last_four) - min(c["low"] for c in last_four)
    if avg_range > 0 and four_day_range <= avg_range * 2.0:
        return "range"
    if net_change > avg_range * 1.5:
        return "bullish"
    if net_change < -avg_range * 1.5:
        return "bearish"
    return "range"


def _bias_from_state(state: Dict[str, Any], candles: Sequence[Candle]) -> Optional[Direction]:
    trend = _normalize_direction(state.get("trend")) or _normalize_direction(_trend_from_candles(candles))
    return trend


def _swing_points(candles: Sequence[Candle], lookback: int = 2) -> List[Dict[str, Any]]:
    swings: List[Dict[str, Any]] = []
    if len(candles) < lookback * 2 + 1:
        return swings
    for index in range(lookback, len(candles) - lookback):
        window = candles[index - lookback:index + lookback + 1]
        candle = candles[index]
        if candle["high"] == max(item["high"] for item in window):
            swings.append({"type": "high", "price": candle["high"], "index": index, "time": candle.get("time")})
        if candle["low"] == min(item["low"] for item in window):
            swings.append({"type": "low", "price": candle["low"], "index": index, "time": candle.get("time")})
    return swings


def _liquidity_targets(candles: Sequence[Candle], direction: Direction, price: float, timeframe: str) -> List[Target]:
    targets: List[Target] = []
    swings = _swing_points(candles, lookback=2)[-30:]
    desired_type = "high" if direction == "buy" else "low"
    avg_range = _average_range(candles, period=20)
    equal_tolerance = max(avg_range * 0.12, _point_from_price(price) * 20)
    for swing in swings:
        level = float(swing["price"])
        if swing["type"] != desired_type:
            continue
        if direction == "buy" and level <= price:
            continue
        if direction == "sell" and level >= price:
            continue
        swept = any(
            (future["high"] > level if direction == "buy" else future["low"] < level)
            for future in list(candles)[int(swing["index"]) + 1:]
        )
        if swept:
            continue
        targets.append(
            Target(
                kind="liquidity",
                direction=direction,
                price=level,
                timeframe=timeframe,
                source=f"{timeframe}_unswept_swing_{desired_type}",
                distance=abs(level - price),
            )
        )
    same_side_swings = [swing for swing in swings if swing["type"] == desired_type]
    for left, right in zip(same_side_swings, same_side_swings[1:]):
        left_level = float(left["price"])
        right_level = float(right["price"])
        if abs(left_level - right_level) > equal_tolerance:
            continue
        level = (left_level + right_level) / 2.0
        if direction == "buy" and level <= price:
            continue
        if direction == "sell" and level >= price:
            continue
        future = list(candles)[int(right["index"]) + 1:]
        swept = any(
            (candle["high"] > level if direction == "buy" else candle["low"] < level)
            for candle in future
        )
        if swept:
            continue
        targets.append(
            Target(
                kind="equal_liquidity",
                direction=direction,
                price=level,
                timeframe=timeframe,
                source=f"{timeframe}_unswept_equal_{desired_type}s",
                distance=abs(level - price),
            )
        )
    recent = list(candles)[-6:-1]
    if recent:
        level = max(c["high"] for c in recent) if direction == "buy" else min(c["low"] for c in recent)
        if (direction == "buy" and level > price) or (direction == "sell" and level < price):
            targets.append(
                Target(
                    kind="liquidity",
                    direction=direction,
                    price=level,
                    timeframe=timeframe,
                    source=f"{timeframe}_recent_visible_liquidity",
                    distance=abs(level - price),
                )
            )
    return sorted(targets, key=lambda item: item.distance)


def _fvg_future_fill(low: float, high: float, direction: Direction, future_candles: Sequence[Candle]) -> float:
    width = max(high - low, 1e-12)
    if not future_candles:
        return 0.0
    if direction == "buy":
        lowest_after_creation = min(candle["low"] for candle in future_candles)
        if lowest_after_creation <= low:
            return 1.0
        if lowest_after_creation >= high:
            return 0.0
        return (high - lowest_after_creation) / width
    highest_after_creation = max(candle["high"] for candle in future_candles)
    if highest_after_creation >= high:
        return 1.0
    if highest_after_creation <= low:
        return 0.0
    return (highest_after_creation - low) / width


def _displacement_candle(candle: Candle, average_range: float, direction: Direction) -> bool:
    return bool(
        _direction_of(candle) == direction
        and _body_ratio(candle) >= 0.60
        and _range(candle) >= max(average_range * 1.10, 1e-12)
    )


def _fvg_zones(candles: Sequence[Candle], timeframe: str, price: float) -> List[Zone]:
    zones: List[Zone] = []
    for index in range(2, len(candles)):
        first = candles[index - 2]
        middle = candles[index - 1]
        third = candles[index]
        average_range = _average_range(candles[:index], period=20)
        bullish_displacement = _displacement_candle(middle, average_range, "buy") or _displacement_candle(third, average_range, "buy")
        bearish_displacement = _displacement_candle(middle, average_range, "sell") or _displacement_candle(third, average_range, "sell")
        if first["high"] < third["low"] and bullish_displacement:
            low = first["high"]
            high = third["low"]
            fill = max(
                _fvg_future_fill(low, high, "buy", list(candles)[index + 1:]),
                _zone_fill_ratio(low, high, price, "buy"),
            )
            if fill <= 0.75:
                zones.append(_make_zone("true_fvg", "buy", low, high, timeframe, "true_bullish_fvg_displacement_created_unmitigated", index, fill))
        if first["low"] > third["high"] and bearish_displacement:
            low = third["high"]
            high = first["low"]
            fill = max(
                _fvg_future_fill(low, high, "sell", list(candles)[index + 1:]),
                _zone_fill_ratio(low, high, price, "sell"),
            )
            if fill <= 0.75:
                zones.append(_make_zone("true_fvg", "sell", low, high, timeframe, "true_bearish_fvg_displacement_created_unmitigated", index, fill))
    return zones


def _zone_fill_ratio(low: float, high: float, price: float, direction: Direction) -> float:
    width = max(high - low, 1e-12)
    if direction == "buy":
        if price >= high:
            return 0.0
        if price <= low:
            return 1.0
        return (high - price) / width
    if price <= low:
        return 0.0
    if price >= high:
        return 1.0
    return (price - low) / width


def _make_zone(kind: str, direction: Direction, low: float, high: float, timeframe: str, source: str, index: int, fill_ratio: float = 0.0) -> Zone:
    low_value = min(float(low), float(high))
    high_value = max(float(low), float(high))
    return Zone(
        kind=kind,
        direction=direction,
        low=low_value,
        high=high_value,
        midpoint=(low_value + high_value) / 2.0,
        levels={
            "25": low_value + (high_value - low_value) * 0.25,
            "50": low_value + (high_value - low_value) * 0.50,
            "75": low_value + (high_value - low_value) * 0.75,
        },
        timeframe=timeframe,
        source=source,
        index=index,
        fill_ratio=fill_ratio,
    )


def _ob_zones(candles: Sequence[Candle], timeframe: str) -> List[Zone]:
    zones: List[Zone] = []
    avg_range = _average_range(candles, period=20)
    for index in range(1, len(candles)):
        previous = candles[index - 1]
        current = candles[index]
        current_direction = _direction_of(current)
        previous_direction = _direction_of(previous)
        if current_direction is None or previous_direction is None:
            continue
        prior = list(candles)[max(0, index - 8):index]
        if len(prior) < 3:
            continue
        impulse = _displacement_candle(current, avg_range, current_direction)
        bullish_bos = current_direction == "buy" and current["close"] > max(candle["high"] for candle in prior)
        bearish_bos = current_direction == "sell" and current["close"] < min(candle["low"] for candle in prior)
        if not impulse:
            continue
        if previous_direction == "sell" and bullish_bos:
            zones.append(_make_zone("true_order_block", "buy", previous["low"], previous["high"], timeframe, "true_ob_final_bearish_candle_before_bullish_displacement_bos", index - 1))
        if previous_direction == "buy" and bearish_bos:
            zones.append(_make_zone("true_order_block", "sell", previous["low"], previous["high"], timeframe, "true_ob_final_bullish_candle_before_bearish_displacement_bos", index - 1))
    return zones


def _ote_zone(candles: Sequence[Candle], direction: Direction, timeframe: str) -> Optional[Zone]:
    swings = _swing_points(candles, lookback=2)
    if len(swings) < 2:
        return None
    recent_swings = swings[-12:]
    highs = [swing for swing in recent_swings if swing["type"] == "high"]
    lows = [swing for swing in recent_swings if swing["type"] == "low"]
    if not highs or not lows:
        return None
    last_high = highs[-1]
    last_low = lows[-1]
    if direction == "buy":
        impulse_low = float(last_low["price"])
        impulse_high = max(float(swing["price"]) for swing in highs if int(swing["index"]) > int(last_low["index"]) or swing == last_high)
        if impulse_high <= impulse_low:
            return None
        low = impulse_high - (impulse_high - impulse_low) * 0.79
        high = impulse_high - (impulse_high - impulse_low) * 0.62
        return _make_zone("ote", "buy", low, high, timeframe, "optimal_trade_entry_62_79_retracement", int(last_high["index"]))
    impulse_high = float(last_high["price"])
    impulse_low = min(float(swing["price"]) for swing in lows if int(swing["index"]) > int(last_high["index"]) or swing == last_low)
    if impulse_high <= impulse_low:
        return None
    low = impulse_low + (impulse_high - impulse_low) * 0.62
    high = impulse_low + (impulse_high - impulse_low) * 0.79
    return _make_zone("ote", "sell", low, high, timeframe, "optimal_trade_entry_62_79_retracement", int(last_low["index"]))


def _target_from_zones(zones: Sequence[Zone], direction: Direction, price: float, timeframe: str) -> List[Target]:
    targets: List[Target] = []
    for zone in zones:
        if zone.direction != direction:
            continue
        target_price = zone.high if direction == "buy" else zone.low
        if direction == "buy" and target_price <= price:
            continue
        if direction == "sell" and target_price >= price:
            continue
        targets.append(
            Target(
                kind=zone.kind,
                direction=direction,
                price=target_price,
                timeframe=timeframe,
                source=zone.source,
                distance=abs(target_price - price),
            )
        )
    return sorted(targets, key=lambda item: item.distance)


def _nearest_entry_zone(zones: Sequence[Zone], direction: Direction, price: float) -> Optional[Zone]:
    candidates = [
        zone for zone in zones
        if zone.direction == direction and zone.aligned_with(direction, price)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda zone: min(abs(price - zone.low), abs(price - zone.high), abs(price - zone.midpoint)))[0]


def _previous_day_shift(candles: Sequence[Candle], direction: Direction) -> Dict[str, Any]:
    if len(candles) < 2:
        return {"confirmed": False, "type": "none"}
    previous = candles[-2]
    before = candles[-3] if len(candles) >= 3 else candles[-2]
    candle_direction = _direction_of(previous)
    continuation = candle_direction == direction and _body_ratio(previous) >= 0.45
    reversal = (
        direction == "buy" and previous["low"] < before["low"] and previous["close"] > before["close"]
    ) or (
        direction == "sell" and previous["high"] > before["high"] and previous["close"] < before["close"]
    )
    if continuation:
        return {"confirmed": True, "type": "continuation", "body_ratio": _body_ratio(previous)}
    if reversal:
        return {"confirmed": True, "type": "reversal", "body_ratio": _body_ratio(previous)}
    return {"confirmed": False, "type": "none", "body_ratio": _body_ratio(previous)}


def _h4_aligned(h4_state: Dict[str, Any], h4_candles: Sequence[Candle], direction: Direction) -> bool:
    state_bias = _bias_from_state(h4_state, h4_candles)
    if state_bias == direction:
        return True
    recent = list(h4_candles)[-8:]
    if len(recent) < 4:
        return False
    if direction == "buy":
        return recent[-1]["close"] > max(c["high"] for c in recent[:-1])
    return recent[-1]["close"] < min(c["low"] for c in recent[:-1])


def _engulfing(candles: Sequence[Candle], direction: Direction) -> bool:
    if len(candles) < 2:
        return False
    previous = candles[-2]
    current = candles[-1]
    if direction == "buy":
        return current["close"] > current["open"] and current["close"] > previous["high"] and current["open"] <= previous["close"]
    return current["close"] < current["open"] and current["close"] < previous["low"] and current["open"] >= previous["close"]


def _strong_rejection(candles: Sequence[Candle], direction: Direction) -> bool:
    if not candles:
        return False
    candle = candles[-1]
    candle_range = _range(candle)
    if candle_range <= 0:
        return False
    upper_wick = candle["high"] - max(candle["open"], candle["close"])
    lower_wick = min(candle["open"], candle["close"]) - candle["low"]
    if direction == "buy":
        return lower_wick >= candle_range * 0.45 and candle["close"] > candle["open"]
    return upper_wick >= candle_range * 0.45 and candle["close"] < candle["open"]


def _break_of_structure(candles: Sequence[Candle], direction: Direction) -> bool:
    if len(candles) < 8:
        return False
    previous = list(candles)[-8:-1]
    current = candles[-1]
    if direction == "buy":
        return current["close"] > max(c["high"] for c in previous)
    return current["close"] < min(c["low"] for c in previous)


def _two_consecutive_directional(candles: Sequence[Candle], direction: Direction, body_ratio: float = 0.70) -> bool:
    if len(candles) < 2:
        return False
    last_two = list(candles)[-2:]
    return all(_direction_of(candle) == direction and _body_ratio(candle) >= body_ratio for candle in last_two)


def _large_engulfing_or_breakout(candles: Sequence[Candle], direction: Direction) -> bool:
    if len(candles) < 6:
        return False
    current = candles[-1]
    previous = candles[-2]
    prior = list(candles)[-6:-1]
    avg_range = _average_range(prior, period=len(prior))
    if _direction_of(current) != direction:
        return False
    large = _range(current) >= avg_range * 1.35 and _body_ratio(current) >= 0.65
    if direction == "buy":
        engulf = current["close"] > previous["high"]
        breakout = current["close"] > max(c["high"] for c in prior)
    else:
        engulf = current["close"] < previous["low"]
        breakout = current["close"] < min(c["low"] for c in prior)
    return large and (engulf or breakout)


def _swept_liquidity(candles: Sequence[Candle], direction: Direction) -> bool:
    if len(candles) < 6:
        return False
    current = candles[-1]
    prior = list(candles)[-6:-1]
    if direction == "buy":
        swept = current["low"] < min(c["low"] for c in prior)
        reclaimed = current["close"] > min(c["low"] for c in prior)
        return swept and reclaimed
    swept = current["high"] > max(c["high"] for c in prior)
    reclaimed = current["close"] < max(c["high"] for c in prior)
    return swept and reclaimed


def _price_touched_zone(candles: Sequence[Candle], zone: Optional[Zone], tolerance: float = 0.0) -> bool:
    if zone is None or not candles:
        return False
    recent = list(candles)[-5:]
    return any(candle["low"] <= zone.high + tolerance and candle["high"] >= zone.low - tolerance for candle in recent)


def _continuation_signal(h1_candles: Sequence[Candle], h1_zone: Optional[Zone], direction: Direction, point: float) -> bool:
    return bool(
        h1_zone
        and _price_touched_zone(h1_candles, h1_zone, tolerance=point * 5)
        and _two_consecutive_directional(h1_candles, direction, body_ratio=0.50)
    )


def _reversal_signal(h1_candles: Sequence[Candle], direction: Direction) -> bool:
    return bool(
        _swept_liquidity(h1_candles, direction)
        and (_engulfing(h1_candles, direction) or _strong_rejection(h1_candles, direction) or _break_of_structure(h1_candles, direction))
    )


def _last_swing_stop(candles: Sequence[Candle], direction: Direction, entry: float, point: float) -> float:
    swings = _swing_points(candles, lookback=2)
    if direction == "buy":
        lows = [float(swing["price"]) for swing in swings if swing["type"] == "low" and float(swing["price"]) < entry]
        fallback = min(c["low"] for c in list(candles)[-8:]) if candles else entry - point * 100
        return (lows[-1] if lows else fallback) - point * 10
    highs = [float(swing["price"]) for swing in swings if swing["type"] == "high" and float(swing["price"]) > entry]
    fallback = max(c["high"] for c in list(candles)[-8:]) if candles else entry + point * 100
    return (highs[-1] if highs else fallback) + point * 10


def _select_target(direction: Direction, price: float, daily_targets: Sequence[Target], h4_targets: Sequence[Target]) -> Optional[Target]:
    all_targets = [target for target in list(daily_targets) + list(h4_targets) if target.direction == direction]
    valid = [
        target for target in all_targets
        if (target.price > price if direction == "buy" else target.price < price)
    ]
    if not valid:
        return None
    return sorted(valid, key=lambda item: (item.timeframe != "D1", item.distance))[0]


def _state(name: str, confirmed: bool, evidence: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": name, "confirmed": bool(confirmed), "evidence": evidence}


def _decision_dict(decision: KingsbalfxDecision) -> Dict[str, Any]:
    return asdict(decision)


def _build_analysis_context(analysis: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    daily = analysis.get("DAILY") or {}
    h4 = analysis.get("H4_CONTEXT") or {}
    h1 = analysis.get("HTF") or {}
    m15 = analysis.get("LTF") or {}
    execution = analysis.get("EXECUTION") or {}
    return daily, h4, h1, m15, execution


def evaluate(
    symbol: str,
    direction: Optional[Direction],
    mt5_connector: Any,
    *,
    analysis: Dict[str, Any],
    tick: Dict[str, Any],
    account: Dict[str, Any],
    risk_percent: float = 1.0,
    minimum_rr: float = 1.5,
) -> Dict[str, Any]:
    """Evaluate the Kingsbalfx fallback and return a trade request if valid."""
    price = (_to_float(tick.get("ask")) + _to_float(tick.get("bid"))) / 2.0
    point = _to_float(tick.get("point"), _point_from_price(price))
    daily_state, h4_state, h1_state, m15_state, execution_state = _build_analysis_context(analysis)
    d1 = _candles(daily_state)
    h4 = _candles(h4_state)
    h1 = _candles(h1_state)
    m15 = _candles(m15_state)
    m5 = _candles(execution_state) or list(analysis.get("m5_candles") or [])
    requested_direction = _normalize_direction(direction)
    daily_direction = _bias_from_state(daily_state, d1)
    trade_direction = requested_direction or daily_direction

    evidence: Dict[str, Any] = {
        "symbol": symbol,
        "strategy": "kingsbalfx",
        "states": [],
    }

    if trade_direction not in ("buy", "sell"):
        decision = KingsbalfxDecision(False, "d1_narrative_unclear", None, None, None, None, None, 0.0, None, None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    daily_trend = _trend_from_candles(d1)
    daily_clear = daily_trend in ("bullish", "bearish") and _normalize_direction(daily_trend) == trade_direction
    daily_fvgs = _fvg_zones(d1, "D1", price)
    daily_obs = _ob_zones(d1, "D1")
    daily_targets = (
        _liquidity_targets(d1, trade_direction, price, "D1")
        + _target_from_zones(daily_fvgs, trade_direction, price, "D1")
        + _target_from_zones(daily_obs, trade_direction, price, "D1")
    )
    previous_shift = _previous_day_shift(d1, trade_direction)
    primary_target = _select_target(trade_direction, price, daily_targets, [])
    d1_pass = bool(daily_clear and primary_target and previous_shift.get("confirmed"))
    evidence["states"].append(
        _state(
            "d1_context",
            d1_pass,
            {
                "daily_trend": daily_trend,
                "direction": trade_direction,
                "target": asdict(primary_target) if primary_target else None,
                "previous_day_shift": previous_shift,
                "fvg_count": len(daily_fvgs),
                "order_block_count": len(daily_obs),
            },
        )
    )
    if not d1_pass:
        decision = KingsbalfxDecision(False, "d1_context_or_target_missing", trade_direction, None, None, None, None, 0.0, asdict(primary_target) if primary_target else None, None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    h4_fvgs = _fvg_zones(h4, "H4", price)
    h4_obs = _ob_zones(h4, "H4")
    h4_ote = _ote_zone(h4, trade_direction, "H4")
    h4_entry_zones = h4_fvgs + h4_obs + ([h4_ote] if h4_ote else [])
    h4_targets = (
        _liquidity_targets(h4, trade_direction, price, "H4")
        + _target_from_zones(h4_fvgs, trade_direction, price, "H4")
        + _target_from_zones(h4_obs, trade_direction, price, "H4")
    )
    h4_entry_zone = _nearest_entry_zone(h4_entry_zones, trade_direction, price)
    h4_agrees = _h4_aligned(h4_state, h4, trade_direction)
    h4_pass = bool(h4_agrees)
    evidence["states"].append(
        _state(
            "h4_alignment",
            h4_pass,
            {
                "h4_trend": h4_state.get("trend") or _trend_from_candles(h4),
                "secondary_entry_area": asdict(h4_entry_zone) if h4_entry_zone else None,
                "h4_targets": [asdict(item) for item in h4_targets[:3]],
                "h4_zone_optional": h4_entry_zone is None,
                "true_fvg_count": len(h4_fvgs),
                "true_order_block_count": len(h4_obs),
                "ote_zone": asdict(h4_ote) if h4_ote else None,
            },
        )
    )
    if not h4_pass:
        decision = KingsbalfxDecision(False, "h4_does_not_align_with_d1_bias", trade_direction, None, None, None, None, 0.0, asdict(primary_target), None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    h1_fvgs = _fvg_zones(h1, "H1", price)
    h1_obs = _ob_zones(h1, "H1")
    h1_ote = _ote_zone(h1, trade_direction, "H1")
    h1_entry_zones = h1_fvgs + h1_obs + ([h1_ote] if h1_ote else [])
    h1_entry_zone = _nearest_entry_zone(h1_entry_zones, trade_direction, price) or h4_entry_zone
    continuation = _continuation_signal(h1, h1_entry_zone, trade_direction, point)
    reversal = _reversal_signal(h1, trade_direction)
    h1_pass = continuation or reversal
    mode = "continuation" if continuation else "reversal" if reversal else None
    evidence["states"].append(
        _state(
            "h1_setup",
            h1_pass,
            {
                "mode": mode,
                "strong_reversal": reversal,
                "continuation_retracement": continuation,
                "h1_entry_zone": asdict(h1_entry_zone) if h1_entry_zone else None,
                "true_fvg_count": len(h1_fvgs),
                "true_order_block_count": len(h1_obs),
                "ote_zone": asdict(h1_ote) if h1_ote else None,
                "engulfing": _engulfing(h1, trade_direction),
                "strong_rejection": _strong_rejection(h1, trade_direction),
                "bos": _break_of_structure(h1, trade_direction),
            },
        )
    )
    if not h1_pass:
        decision = KingsbalfxDecision(False, "h1_reversal_or_continuation_trigger_missing", trade_direction, None, None, None, None, 0.0, asdict(primary_target), asdict(h1_entry_zone) if h1_entry_zone else None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    m15_fvgs = _fvg_zones(m15, "M15", price)
    m15_obs = _ob_zones(m15, "M15")
    m15_ote = _ote_zone(m15, trade_direction, "M15")
    m15_entry_zones = m15_fvgs + m15_obs + ([m15_ote] if m15_ote else [])
    m15_zone = _nearest_entry_zone(m15_entry_zones, trade_direction, price) or h1_entry_zone
    if mode == "reversal":
        m15_condition = _swept_liquidity(m15, trade_direction) and _price_touched_zone(m15, m15_zone, tolerance=point * 5)
    else:
        m15_condition = bool(m15_zone and _price_touched_zone(m15, m15_zone, tolerance=point * 5))
    evidence["states"].append(
        _state(
            "m15_refinement",
            m15_condition,
            {
                "mode": mode,
                "m15_zone": asdict(m15_zone) if m15_zone else None,
                "true_fvg_count": len(m15_fvgs),
                "true_order_block_count": len(m15_obs),
                "ote_zone": asdict(m15_ote) if m15_ote else None,
                "liquidity_sweep": _swept_liquidity(m15, trade_direction),
                "zone_retraced": _price_touched_zone(m15, m15_zone, tolerance=point * 5),
            },
        )
    )
    if not m15_condition:
        decision = KingsbalfxDecision(False, "m15_refinement_missing", trade_direction, mode, None, None, None, 0.0, asdict(primary_target), asdict(m15_zone) if m15_zone else None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    final_trigger = _two_consecutive_directional(m5, trade_direction, body_ratio=0.70) or _large_engulfing_or_breakout(m5, trade_direction)
    evidence["states"].append(
        _state(
            "m5_final_trigger",
            final_trigger,
            {
                "two_strong_candles": _two_consecutive_directional(m5, trade_direction, body_ratio=0.70),
                "large_engulfing_or_breakout": _large_engulfing_or_breakout(m5, trade_direction),
            },
        )
    )
    if not final_trigger:
        decision = KingsbalfxDecision(False, "m5_final_trigger_missing", trade_direction, mode, None, None, None, 0.0, asdict(primary_target), asdict(m15_zone) if m15_zone else None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    entry = _to_float(tick.get("ask") if trade_direction == "buy" else tick.get("bid"))
    sl = _last_swing_stop(m15 or h1, trade_direction, entry, point)
    selected_target = _select_target(trade_direction, entry, [primary_target], h4_targets) or primary_target
    tp = selected_target.price if selected_target else 0.0
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr = reward / risk if risk > 0 else 0.0
    risk_valid = risk > 0 and reward > 0 and rr >= minimum_rr
    evidence["states"].append(
        _state(
            "risk_execution",
            risk_valid,
            {
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "rr": rr,
                "minimum_rr": minimum_rr,
                "target": asdict(selected_target) if selected_target else None,
            },
        )
    )
    if not risk_valid:
        decision = KingsbalfxDecision(False, "minimum_rr_or_structural_risk_invalid", trade_direction, mode, entry, sl, tp, rr, asdict(selected_target) if selected_target else None, asdict(m15_zone) if m15_zone else None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    balance = _to_float((account or {}).get("balance"))
    risk_amount = balance * (max(0.01, float(risk_percent)) / 100.0)
    volume = mt5_connector.calculate_volume_for_risk(symbol, entry, sl, risk_amount)
    if volume <= 0:
        decision = KingsbalfxDecision(False, "risk_manager_returned_zero_volume", trade_direction, mode, entry, sl, tp, rr, asdict(selected_target), asdict(m15_zone) if m15_zone else None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    decision = KingsbalfxDecision(True, "kingsbalfx_fallback_valid", trade_direction, mode, entry, sl, tp, rr, asdict(selected_target), asdict(m15_zone) if m15_zone else None, evidence)
    request = {
        "symbol": symbol,
        "direction": trade_direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "lot": volume,
        "order_type": "market",
        "strategy": "kingsbalfx",
        "identity_context": {
            "strategy": "kingsbalfx",
            "mode": mode,
            "entry_zone": asdict(m15_zone) if m15_zone else None,
            "target": asdict(selected_target),
        },
    }
    return {
        "valid": True,
        "request": request,
        "setup": _decision_dict(decision),
        "reason": decision.reason,
    }
