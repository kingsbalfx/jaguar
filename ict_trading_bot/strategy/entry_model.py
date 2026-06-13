"""Lower-timeframe ICT entry state machine with binary gates only."""

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

from ict_concepts.fvg import detect_displacement_fvg
from ict_concepts.order_blocks import find_true_order_block


def _timeframe(value):
    if mt5 is None:
        return None
    return {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
    }.get(str(value).upper())


def _rates(symbol, timeframe, bars):
    mapped = _timeframe(timeframe)
    if mapped is None:
        return []
    rates = mt5.copy_rates_from_pos(symbol, mapped, 0, bars + 1)
    if rates is None or len(rates) < 4:
        return []
    return [
        {
            "time": int(row["time"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "tick_volume": float(row["tick_volume"]),
        }
        for row in rates[:-1]
    ]


def _swings(candles, width=2):
    result = []
    for index in range(width, len(candles) - width):
        window = candles[index - width : index + width + 1]
        candle = candles[index]
        if candle["high"] == max(item["high"] for item in window):
            result.append({"type": "high", "price": candle["high"], "index": index, "time": candle["time"]})
        if candle["low"] == min(item["low"] for item in window):
            result.append({"type": "low", "price": candle["low"], "index": index, "time": candle["time"]})
    return result


def _trend(candles):
    swings = _swings(candles)
    highs = [item for item in swings if item["type"] == "high"]
    lows = [item for item in swings if item["type"] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return None
    if highs[-1]["price"] > highs[-2]["price"] and lows[-1]["price"] > lows[-2]["price"]:
        return "buy"
    if highs[-1]["price"] < highs[-2]["price"] and lows[-1]["price"] < lows[-2]["price"]:
        return "sell"
    return None


def _external_liquidity(h1, d1, w1):
    levels = []
    for label, candles in (("previous_day", d1), ("previous_week", w1)):
        if candles:
            candle = candles[-1]
            levels.extend(
                (
                    {"type": "high", "level": candle["high"], "source": f"{label}_high"},
                    {"type": "low", "level": candle["low"], "source": f"{label}_low"},
                )
            )
    for swing in _swings(h1)[-12:]:
        levels.append({"type": swing["type"], "level": swing["price"], "source": "H1_major_swing"})
    return levels


def _find_sweep(candles, levels, direction):
    required_type = "low" if direction == "buy" else "high"
    for index in range(max(1, len(candles) - 80), len(candles) - 2):
        candle = candles[index]
        for level in levels:
            price = float(level["level"])
            swept = (
                candle["low"] < price and candle["close"] > price
                if direction == "buy"
                else candle["high"] > price and candle["close"] < price
            )
            if level["type"] == required_type and swept:
                return {**level, "index": index, "extreme": candle["low"] if direction == "buy" else candle["high"]}
    return None


def _atr(candles, end, period=14):
    ranges = []
    previous_close = None
    for candle in candles[: end + 1]:
        ranges.append(
            candle["high"] - candle["low"]
            if previous_close is None
            else max(
                candle["high"] - candle["low"],
                abs(candle["high"] - previous_close),
                abs(candle["low"] - previous_close),
            )
        )
        previous_close = candle["close"]
    window = ranges[-period:]
    return sum(window) / len(window) if window else 0.0


def _find_displacement(candles, sweep, direction):
    for index in range(sweep["index"] + 1, min(len(candles) - 1, sweep["index"] + 8)):
        candle = candles[index]
        candle_range = max(candle["high"] - candle["low"], 1e-12)
        body = abs(candle["close"] - candle["open"])
        directional = candle["close"] > candle["open"] if direction == "buy" else candle["close"] < candle["open"]
        if directional and body / candle_range >= 0.60 and candle_range >= _atr(candles, index):
            return index
    return None


def _mss(candles, displacement_index, direction):
    prior = candles[max(0, displacement_index - 20) : displacement_index]
    swings = _swings(prior, width=1)
    opposing = [item for item in swings if item["type"] == ("high" if direction == "buy" else "low")]
    if not opposing:
        return None
    level = opposing[-1]["price"]
    for index in range(displacement_index, min(len(candles), displacement_index + 5)):
        close = candles[index]["close"]
        if (direction == "buy" and close > level) or (direction == "sell" and close < level):
            return {"index": index, "level": level}
    return None


def _dealing_range(candles, sweep_index, direction):
    window = candles[max(0, sweep_index - 40) : sweep_index + 1]
    low = min(item["low"] for item in window)
    high = max(item["high"] for item in window)
    if high <= low:
        return None
    if direction == "buy":
        return {"low": low + (high - low) * 0.21, "high": low + (high - low) * 0.38, "equilibrium": (low + high) / 2.0}
    return {"low": low + (high - low) * 0.62, "high": low + (high - low) * 0.79, "equilibrium": (low + high) / 2.0}


def _select_retracement_zone(candle, fvg, order_block):
    for kind, zone in (("FVG", fvg), ("ORDER_BLOCK", order_block)):
        if candle["low"] <= float(zone["high"]) and candle["high"] >= float(zone["low"]):
            low, high = float(zone["low"]), float(zone["high"])
            distance = high - low
            return {
                **zone,
                "kind": kind,
                "levels": {
                    "25": low + distance * 0.25,
                    "50": low + distance * 0.50,
                    "75": low + distance * 0.75,
                },
            }
    return None


def _retrace(candles, start_index, zone):
    for index in range(start_index + 1, len(candles)):
        candle = candles[index]
        if candle["low"] <= zone["high"] and candle["high"] >= zone["low"]:
            return index
    return None


def _confirmation(candles, direction, zone):
    if len(candles) < 2:
        return False
    previous, current = candles[-2], candles[-1]
    touched = current["low"] <= zone["high"] and current["high"] >= zone["low"]
    candle_range = max(current["high"] - current["low"], 1e-12)
    body = abs(current["close"] - current["open"])
    if direction == "buy":
        rejection = current["close"] > current["open"] and min(current["open"], current["close"]) - current["low"] >= body
        engulfing = previous["close"] < previous["open"] and current["open"] <= previous["close"] and current["close"] >= previous["open"]
        strong_close = current["close"] > current["open"] and (current["close"] - current["low"]) / candle_range >= 0.75
    else:
        rejection = current["close"] < current["open"] and current["high"] - max(current["open"], current["close"]) >= body
        engulfing = previous["close"] > previous["open"] and current["open"] >= previous["close"] and current["close"] <= previous["open"]
        strong_close = current["close"] < current["open"] and (current["high"] - current["close"]) / candle_range >= 0.75
    return touched and (rejection or engulfing or strong_close)


def _target(levels, entry, stop, direction):
    risk = abs(entry - stop)
    candidates = [
        float(item["level"])
        for item in levels
        if item["type"] == ("high" if direction == "buy" else "low")
        and ((direction == "buy" and float(item["level"]) > entry) or (direction == "sell" and float(item["level"]) < entry))
        and abs(float(item["level"]) - entry) >= risk * 1.5
    ]
    if not candidates:
        return None
    return min(candidates) if direction == "buy" else max(candidates)


def get_lower_timeframe_entry(symbol, direction, tf="M5"):
    """Return a market-entry plan only after every strict lower-timeframe gate passes."""
    if mt5 is None or str(tf).upper() not in ("M1", "M5"):
        return None
    direction = str(direction or "").lower()
    if direction not in ("buy", "sell"):
        return None
    d1, h4, h1 = _rates(symbol, "D1", 160), _rates(symbol, "H4", 240), _rates(symbol, "H1", 300)
    lower, m1 = _rates(symbol, tf, 500), _rates(symbol, "M1", 300)
    if min(len(d1), len(h4), len(h1), len(lower), len(m1)) < 20:
        return None
    if _trend(d1) != direction or _trend(h4) != direction:
        return None
    levels = _external_liquidity(h1, d1, _rates(symbol, "W1", 80))
    if not levels:
        return None
    sweep = _find_sweep(lower, levels, direction)
    if not sweep:
        return None
    displacement_index = _find_displacement(lower, sweep, direction)
    if displacement_index is None:
        return None
    if not _mss(lower, displacement_index, direction):
        return None
    fvg = detect_displacement_fvg(lower, displacement_index, direction, timeframe=tf)
    order_block = find_true_order_block(lower, displacement_index, direction, timeframe=tf)
    if not fvg or not order_block:
        return None
    zone = _select_retracement_zone(lower[-1], fvg, order_block)
    if not zone:
        return None
    retrace_index = _retrace(lower, displacement_index + 1, zone)
    if retrace_index is None or retrace_index != len(lower) - 1:
        return None
    if not _confirmation(m1, direction, zone):
        return None
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return None
    entry = float(tick.ask if direction == "buy" else tick.bid)
    point = float(getattr(mt5.symbol_info(symbol), "point", 0.0) or 0.0)
    stop = float(sweep["extreme"]) - point * 2 if direction == "buy" else float(sweep["extreme"]) + point * 2
    target = _target(levels, entry, stop, direction)
    if target is None:
        return None
    return {
        "entry": entry,
        "sl": stop,
        "tp": target,
        "type": zone["kind"],
        "direction": direction,
        "timeframe": str(tf).upper(),
        "fvg": fvg,
        "order_block": order_block,
        "confluence_zone": zone,
        "swept_liquidity": sweep,
    }


def hybrid_entry_model(data):
    """Compatibility adapter; accepts only a pre-confirmed strict plan."""
    if not isinstance(data, dict) or not data.get("strict_sequence_confirmed"):
        return None
    required = ("direction", "entry", "sl", "tp", "type")
    return {key: data[key] for key in required} if all(key in data for key in required) else None


def explain_entry_failure(trend, price, fib_levels, fvgs, htf_order_blocks, symbol=None, atr=None):
    del trend, price, fib_levels, fvgs, htf_order_blocks, symbol, atr
    return "strict_sequence_not_confirmed"


def check_entry(trend, price, fib_levels, fvgs, htf_order_blocks, symbol=None, atr=None):
    del trend, price, fib_levels, fvgs, htf_order_blocks, symbol, atr
    return None
