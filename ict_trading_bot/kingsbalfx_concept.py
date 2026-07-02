# FILE: ict_trading_bot/kingsbalfx_concept.py
"""Kingsbalfx secondary fallback strategy.

This module is intentionally independent from the strict ICT state machine. It
does not mutate or replace the 12-gate ICT logic. It only evaluates a fallback
trade model when the primary ICT state machine has already returned SKIP.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from market_structure.structure import structure_confirms_direction

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


def _window_size(state: Dict[str, Any], name: str, default: int) -> int:
    lengths = state.get("candle_window_lengths") or {}
    try:
        return max(1, int(lengths.get(name) or default))
    except (TypeError, ValueError):
        return default


def _raw_candles(items: Iterable[Any]) -> List[Candle]:
    out: List[Candle] = []
    for item in items or []:
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


def _candles(state: Dict[str, Any], window_name: str = None, default_window: int = None) -> List[Candle]:
    if window_name:
        window = (state.get("concept_windows") or {}).get(window_name)
        if window:
            return _raw_candles(window)
    candles = _raw_candles(state.get("recent_candles") or [])
    if window_name or default_window:
        size = _window_size(state, window_name or "", default_window or len(candles))
        return candles[-max(1, min(size, len(candles))):]
    return candles


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
        distance = impulse_high - impulse_low
        low = impulse_low + distance * 0.25
        high = impulse_low + distance * 0.50
        return _make_zone("ote", "buy", low, high, timeframe, "quarter_fib_discount_retracement", int(last_high["index"]))
    impulse_high = float(last_high["price"])
    impulse_low = min(float(swing["price"]) for swing in lows if int(swing["index"]) > int(last_high["index"]) or swing == last_low)
    if impulse_high <= impulse_low:
        return None
    distance = impulse_high - impulse_low
    low = impulse_low + distance * 0.50
    high = impulse_low + distance * 0.75
    return _make_zone("ote", "sell", low, high, timeframe, "quarter_fib_premium_retracement", int(last_low["index"]))


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


def _select_target(direction: Direction, price: float, primary_targets: Sequence[Target], secondary_targets: Sequence[Target]) -> Optional[Target]:
    all_targets = [target for target in list(primary_targets) + list(secondary_targets) if target.direction == direction]
    valid = [
        target for target in all_targets
        if (target.price > price if direction == "buy" else target.price < price)
    ]
    if not valid:
        return None
    return sorted(valid, key=lambda item: (item.timeframe != "H1", item.timeframe != "M15", item.distance))[0]


def _state(name: str, confirmed: bool, evidence: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": name, "confirmed": bool(confirmed), "evidence": evidence}


def _decision_dict(decision: KingsbalfxDecision) -> Dict[str, Any]:
    return asdict(decision)


def _build_analysis_context(analysis: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    daily = analysis.get("DAILY_CONTEXT") or analysis.get("DAILY") or {}
    h1 = analysis.get("HTF") or {}
    m15 = analysis.get("MTF") or {}
    m5_context = analysis.get("LTF") or {}
    execution = analysis.get("EXECUTION") or {}
    return daily, h1, m15, m5_context, execution


def _h1_m15_alignment(analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    alignment = analysis.get("h1_m15_alignment") or (analysis.get("topdown") or {}).get("h1_m15_alignment")
    return alignment if isinstance(alignment, dict) else None


def _live_visual_concepts(analysis: Dict[str, Any]) -> Dict[str, Any]:
    concepts = analysis.get("visual_concepts") or (analysis.get("topdown") or {}).get("visual_concepts") or {}
    return concepts if isinstance(concepts, dict) else {}


def _live_concept_matches_direction(concept: Dict[str, Any], direction: Direction) -> bool:
    return bool(concept and _normalize_direction(concept.get("direction")) == direction)


def _structure_confirms(structure: Dict[str, Any], direction: Direction, require_event: bool = False) -> bool:
    return structure_confirms_direction(structure if isinstance(structure, dict) else {}, direction, require_event=require_event)


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
    daily_state, h1_state, m15_state, m5_context_state, execution_state = _build_analysis_context(analysis)
    d1 = _candles(daily_state, "htf_context", 120)
    d1_fvg_ob = _candles(daily_state, "true_fvg_ob_context", 100)
    h1 = _candles(h1_state, "htf_context", 120)
    h1_liquidity = _candles(h1_state, "external_liquidity", 200)
    h1_fvg_ob = _candles(h1_state, "true_fvg_ob_context", 100)
    m15 = _candles(m15_state, "structure", 80)
    m15_external_liquidity = _candles(m15_state, "external_liquidity", 200)
    m15_sweep = _candles(m15_state, "sweep", 20)
    m15_fvg_ob = _candles(m15_state, "true_fvg_ob_context", 100)
    m5_context_liquidity = _candles(m5_context_state, "external_liquidity", 200)
    m5 = _candles(execution_state, "execution_confirmation", 50) or _candles(m5_context_state, "execution_confirmation", 50) or list(analysis.get("m5_candles") or [])[-50:]
    h1_m15_alignment = _h1_m15_alignment(analysis)
    requested_direction = _normalize_direction(direction)
    h1_direction = (
        h1_m15_alignment.get("direction")
        if h1_m15_alignment and h1_m15_alignment.get("confirmed")
        else _bias_from_state(h1_state, h1)
    )
    if h1_direction not in ("buy", "sell"):
        h1_direction = _bias_from_state(h1_state, h1)
    trade_direction = requested_direction or h1_direction

    evidence: Dict[str, Any] = {
        "symbol": symbol,
        "strategy": "kingsbalfx",
        "states": [],
        "candle_windows": analysis.get("candle_window_usage") or analysis.get("candle_windows") or {},
        "previous_day_context": analysis.get("previous_day_context") or {},
        "opening_gaps": analysis.get("opening_gaps") or (analysis.get("topdown") or {}).get("opening_gaps") or {},
        "visual_concepts": _live_visual_concepts(analysis),
        "session_analysis": analysis.get("session_analysis") or {},
    }

    if trade_direction not in ("buy", "sell"):
        decision = KingsbalfxDecision(False, "h1_narrative_unclear", None, None, None, None, None, 0.0, None, None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    background_context = analysis.get("previous_day_context") or {}
    background_timeframe = str(
        background_context.get("source_timeframe")
        or daily_state.get("timeframe")
        or "D1"
    ).upper()
    daily_fvgs = _fvg_zones(d1_fvg_ob, background_timeframe, price)
    daily_obs = _ob_zones(d1_fvg_ob, background_timeframe)
    previous_shift = _previous_day_shift(d1, trade_direction)
    evidence["states"].append(
        _state(
            "previous_day_context",
            True,
            {
                "role": "background_only",
                "previous_day_context": background_context,
                "previous_day_shift": previous_shift,
                "background_timeframe": background_timeframe,
                "background_fallback_used": bool(background_context.get("fallback_used")),
                "background_fvg_count": len(daily_fvgs),
                "background_order_block_count": len(daily_obs),
                "d1_fvg_count": len(daily_fvgs),
                "d1_order_block_count": len(daily_obs),
                "context_candles": len(d1),
            },
        )
    )

    h1_trend = _trend_from_candles(h1)
    h1_structure = h1_state.get("market_structure") or {}
    h1_structure_confirms = _structure_confirms(h1_structure, trade_direction, require_event=False)
    h1_clear = (
        bool(h1_m15_alignment.get("confirmed") and h1_m15_alignment.get("direction") == trade_direction)
        if h1_m15_alignment
        else h1_trend in ("bullish", "bearish") and _normalize_direction(h1_trend) == trade_direction
    )
    h1_clear = bool(h1_clear or (_bias_from_state(h1_state, h1) == trade_direction and h1_structure_confirms))
    h1_fvgs_for_targets = _fvg_zones(h1_fvg_ob, "H1", price)
    h1_obs_for_targets = _ob_zones(h1_fvg_ob, "H1")
    primary_targets = (
        _liquidity_targets(h1_liquidity, trade_direction, price, "H1")
        + _liquidity_targets(m15_external_liquidity, trade_direction, price, "M15")
        + _liquidity_targets(m5_context_liquidity, trade_direction, price, "M5")
        + _target_from_zones(h1_fvgs_for_targets, trade_direction, price, "H1")
        + _target_from_zones(h1_obs_for_targets, trade_direction, price, "H1")
    )
    primary_target = _select_target(trade_direction, price, primary_targets, [])
    h1_context_pass = bool(h1_clear and primary_target)
    evidence["states"].append(
        _state(
            "h1_context",
            h1_context_pass,
            {
                "h1_trend": h1_trend,
                "direction": trade_direction,
                "h1_m15_alignment": h1_m15_alignment,
                "h1_market_structure": h1_structure,
                "h1_structure_confirms_direction": h1_structure_confirms,
                "target": asdict(primary_target) if primary_target else None,
                "fvg_count": len(h1_fvgs_for_targets),
                "order_block_count": len(h1_obs_for_targets),
                "context_candles": len(h1),
                "external_liquidity_timeframes": "H1,M15,M5",
                "liquidity_candles": {
                    "H1": len(h1_liquidity),
                    "M15": len(m15_external_liquidity),
                    "M5": len(m5_context_liquidity),
                },
                "true_fvg_ob_candles": len(h1_fvg_ob),
            },
        )
    )
    if not h1_context_pass:
        decision = KingsbalfxDecision(False, "h1_context_or_target_missing", trade_direction, None, None, None, None, 0.0, asdict(primary_target) if primary_target else None, None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    live_visual = _live_visual_concepts(analysis)
    sweet_zone = live_visual.get("sweet_zone") or {}
    judas_swing = live_visual.get("judas_swing") or {}
    sweet_zone_live = bool(
        sweet_zone.get("in_sweet_zone")
        and sweet_zone.get("enter_now")
        and _live_concept_matches_direction(sweet_zone, trade_direction)
    )
    judas_swing_live = bool(
        judas_swing.get("is_judas_swing")
        and judas_swing.get("purge_confirmed")
        and judas_swing.get("enter_now")
        and _live_concept_matches_direction(judas_swing, trade_direction)
    )

    m15_agrees = (
        bool(h1_m15_alignment.get("confirmed") and h1_m15_alignment.get("direction") == trade_direction)
        if h1_m15_alignment
        else _bias_from_state(m15_state, m15) == trade_direction
    )
    evidence["states"].append(
        _state(
            "m15_alignment",
            m15_agrees,
            {
                "m15_trend": m15_state.get("trend") or _trend_from_candles(m15),
                "h1_m15_alignment": h1_m15_alignment,
                "context_candles": len(m15),
                "liquidity_candles": len(m15_external_liquidity),
            },
        )
    )
    if not m15_agrees:
        decision = KingsbalfxDecision(False, "m15_does_not_align_with_h1_bias", trade_direction, None, None, None, None, 0.0, asdict(primary_target), None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    h1_ote = _ote_zone(h1, trade_direction, "H1")
    h1_entry_zones = h1_fvgs_for_targets + h1_obs_for_targets + ([h1_ote] if h1_ote else [])
    h1_entry_zone = _nearest_entry_zone(h1_entry_zones, trade_direction, price)
    m15_structure = m15_state.get("market_structure") or {}
    m15_structure_confirms = _structure_confirms(m15_structure, trade_direction, require_event=True)
    m15_fvgs = _fvg_zones(m15_fvg_ob, "M15", price)
    m15_obs = _ob_zones(m15_fvg_ob, "M15")
    m15_ote = _ote_zone(m15, trade_direction, "M15")
    m15_entry_zones = m15_fvgs + m15_obs + ([m15_ote] if m15_ote else [])
    m15_zone = _nearest_entry_zone(m15_entry_zones, trade_direction, price) or h1_entry_zone
    continuation = _continuation_signal(m15, m15_zone, trade_direction, point)
    reversal = _reversal_signal(m15, trade_direction) or (_swept_liquidity(m15_sweep, trade_direction) and m15_structure_confirms)
    m15_setup_pass = continuation or reversal or sweet_zone_live or judas_swing_live
    mode = (
        "continuation" if continuation
        else "reversal" if reversal
        else "sweet_zone" if sweet_zone_live
        else "judas_swing" if judas_swing_live
        else None
    )
    evidence["states"].append(
        _state(
            "m15_setup",
            m15_setup_pass,
            {
                "mode": mode,
                "strong_reversal": reversal,
                "continuation_retracement": continuation,
                "m15_market_structure": m15_structure,
                "m15_structure_confirms_direction": m15_structure_confirms,
                "sweet_zone_continuation": sweet_zone_live,
                "judas_swing_reversal": judas_swing_live,
                "sweet_zone": sweet_zone,
                "judas_swing": judas_swing,
                "h1_entry_zone": asdict(h1_entry_zone) if h1_entry_zone else None,
                "m15_entry_zone": asdict(m15_zone) if m15_zone else None,
                "true_fvg_count": len(m15_fvgs),
                "true_order_block_count": len(m15_obs),
                "h1_ote_zone": asdict(h1_ote) if h1_ote else None,
                "m15_ote_zone": asdict(m15_ote) if m15_ote else None,
                "engulfing": _engulfing(m15, trade_direction),
                "strong_rejection": _strong_rejection(m15, trade_direction),
                "bos": _break_of_structure(m15, trade_direction),
                "structure_candles": len(m15),
                "true_fvg_ob_candles": len(m15_fvg_ob),
            },
        )
    )
    if not m15_setup_pass:
        decision = KingsbalfxDecision(False, "m15_reversal_or_continuation_trigger_missing", trade_direction, None, None, None, None, 0.0, asdict(primary_target), asdict(m15_zone) if m15_zone else None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    m5_sweep = _candles(m5_context_state, "sweep", 20) or m5[-20:]
    if mode == "reversal":
        m5_condition = _swept_liquidity(m5_sweep, trade_direction) and _price_touched_zone(m5, m15_zone, tolerance=point * 5)
    elif mode == "judas_swing":
        m5_condition = bool(judas_swing_live and (_two_consecutive_directional(m5, trade_direction, body_ratio=0.55) or _large_engulfing_or_breakout(m5, trade_direction)))
    elif mode == "sweet_zone":
        m5_condition = bool(sweet_zone_live and (_two_consecutive_directional(m5, trade_direction, body_ratio=0.55) or _large_engulfing_or_breakout(m5, trade_direction)))
    else:
        m5_condition = bool(m15_zone and _price_touched_zone(m5, m15_zone, tolerance=point * 5))
    evidence["states"].append(
        _state(
            "m5_refinement",
            m5_condition,
            {
                "mode": mode,
                "m15_zone": asdict(m15_zone) if m15_zone else None,
                "liquidity_sweep": _swept_liquidity(m5_sweep, trade_direction),
                "zone_retraced": _price_touched_zone(m5, m15_zone, tolerance=point * 5),
                "sweet_zone_live": sweet_zone_live,
                "judas_swing_live": judas_swing_live,
                "sweep_candles": len(m5_sweep),
                "execution_confirmation_candles": len(m5),
            },
        )
    )
    if not m5_condition:
        decision = KingsbalfxDecision(False, "m5_refinement_missing", trade_direction, mode, None, None, None, 0.0, asdict(primary_target), asdict(m15_zone) if m15_zone else None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    final_trigger = _two_consecutive_directional(m5, trade_direction, body_ratio=0.70) or _large_engulfing_or_breakout(m5, trade_direction)
    evidence["states"].append(
        _state(
            "m5_final_trigger",
            final_trigger,
            {
                "two_strong_candles": _two_consecutive_directional(m5, trade_direction, body_ratio=0.70),
                "large_engulfing_or_breakout": _large_engulfing_or_breakout(m5, trade_direction),
                "execution_confirmation_candles": len(m5),
            },
        )
    )
    if not final_trigger:
        decision = KingsbalfxDecision(False, "m5_final_trigger_missing", trade_direction, mode, None, None, None, 0.0, asdict(primary_target), asdict(m15_zone) if m15_zone else None, evidence)
        return {"valid": False, "request": None, "setup": _decision_dict(decision), "reason": decision.reason}

    entry = _to_float(tick.get("ask") if trade_direction == "buy" else tick.get("bid"))
    sl = _last_swing_stop(m15 or h1, trade_direction, entry, point)
    m15_targets = (
        _liquidity_targets(m15_external_liquidity, trade_direction, entry, "M15")
        + _target_from_zones(m15_fvgs, trade_direction, entry, "M15")
        + _target_from_zones(m15_obs, trade_direction, entry, "M15")
    )
    selected_target = _select_target(trade_direction, entry, [primary_target], m15_targets) or primary_target
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
