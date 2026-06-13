"""Strict three-candle fair value gap detection."""

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

import pandas as pd


def _tf_to_mt5(timeframe):
    if mt5 is None:
        return None
    return {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }.get(str(timeframe).upper())


def _as_frame(candles):
    if isinstance(candles, pd.DataFrame):
        return candles.reset_index(drop=True).copy()
    return pd.DataFrame(candles or []).reset_index(drop=True)


def _true_ranges(frame):
    ranges = []
    previous_close = None
    for _, candle in frame.iterrows():
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        ranges.append(
            high - low
            if previous_close is None
            else max(high - low, abs(high - previous_close), abs(low - previous_close))
        )
        previous_close = close
    return ranges


def _atr_at(frame, index, period=14):
    ranges = _true_ranges(frame.iloc[: index + 1])
    window = ranges[-max(1, min(period, len(ranges))):]
    return sum(window) / len(window) if window else 0.0


def _mitigation(frame, creation_index, low, high):
    touched = False
    fully_filled = False
    mitigation_index = None
    for index in range(creation_index + 1, len(frame)):
        candle = frame.iloc[index]
        if float(candle["low"]) <= high and float(candle["high"]) >= low:
            touched = True
            mitigation_index = index
        if float(candle["low"]) <= low and float(candle["high"]) >= high:
            fully_filled = True
            break
    return touched, fully_filled, mitigation_index


def detect_displacement_fvg(candles, displacement_index, direction, timeframe="M5", atr_period=14):
    """Return only the FVG whose middle candle is the named displacement candle."""
    frame = _as_frame(candles)
    direction = str(direction or "").lower()
    expected = "bullish" if direction in ("buy", "bullish", "long") else "bearish"
    middle = int(displacement_index)
    if len(frame) < 3 or middle < 1 or middle + 1 >= len(frame):
        return None
    if not {"open", "high", "low", "close"}.issubset(frame.columns):
        return None

    first = frame.iloc[middle - 1]
    impulse = frame.iloc[middle]
    third = frame.iloc[middle + 1]
    candle_range = max(float(impulse["high"]) - float(impulse["low"]), 1e-12)
    body = abs(float(impulse["close"]) - float(impulse["open"]))
    atr = max(_atr_at(frame, middle, atr_period), 1e-12)
    directional = (
        float(impulse["close"]) > float(impulse["open"])
        if expected == "bullish"
        else float(impulse["close"]) < float(impulse["open"])
    )
    if body / candle_range < 0.60 or candle_range < atr or not directional:
        return None

    if expected == "bullish":
        low, high = float(first["high"]), float(third["low"])
    else:
        low, high = float(third["high"]), float(first["low"])
    if high <= low:
        return None

    creation_index = middle + 1
    touched, filled, mitigation_index = _mitigation(frame, creation_index, low, high)
    return {
        "type": expected,
        "low": low,
        "high": high,
        "midpoint": (low + high) / 2.0,
        "gap_size": high - low,
        "index": creation_index,
        "origin_index": middle,
        "displacement_index": middle,
        "timeframe": str(timeframe).upper(),
        "displacement_ok": True,
        "atr_normalized": True,
        "fresh": not touched,
        "active": not filled,
        "mitigated": filled,
        "mitigation_index": mitigation_index,
    }


def detect_fvg_from_df(df, trend=None, min_gap_ratio=0.0, min_body_ratio=0.60):
    del min_gap_ratio, min_body_ratio
    frame = _as_frame(df)
    direction = trend or "bullish"
    results = []
    for middle in range(1, len(frame) - 1):
        for candidate_direction in ([direction] if trend else ["bullish", "bearish"]):
            fvg = detect_displacement_fvg(frame, middle, candidate_direction, timeframe="dynamic")
            if fvg:
                results.append(fvg)
    return results


def qualify_fvgs(fvgs, *, direction=None, structure_break=False, liquidity_sweep=False, fib=None):
    expected = "bullish" if str(direction or "").lower() in ("buy", "bullish", "long") else "bearish"
    qualified = []
    for source in fvgs or []:
        if not isinstance(source, dict):
            continue
        item = dict(source)
        midpoint = float(item.get("midpoint", (float(item["low"]) + float(item["high"])) / 2.0))
        correct_zone = True
        if fib and "0.5" in fib:
            correct_zone = midpoint <= float(fib["0.5"]) if expected == "bullish" else midpoint >= float(fib["0.5"])
        item["structure_break_confirmed"] = bool(structure_break)
        item["liquidity_sweep_confirmed"] = bool(liquidity_sweep)
        item["premium_discount_aligned"] = correct_zone
        item["true_fvg"] = all(
            (
                item.get("type") == expected,
                bool(item.get("displacement_ok")),
                bool(item.get("atr_normalized", True)),
                bool(structure_break),
                bool(liquidity_sweep),
                bool(correct_zone),
                str(item.get("timeframe", "M5")).upper() in ("M1", "M5", "DYNAMIC"),
                bool(item.get("active", True)),
            )
        )
        qualified.append(item)
    return qualified


def detect_fvgs(symbol, timeframe, bars=200, trend=None):
    if mt5 is None:
        return []
    mapped = _tf_to_mt5(timeframe)
    if mapped is None:
        return []
    rates = mt5.copy_rates_from_pos(symbol, mapped, 0, bars)
    if rates is None or len(rates) == 0:
        return []
    results = detect_fvg_from_df(pd.DataFrame(rates), trend=trend)
    for item in results:
        item["timeframe"] = str(timeframe).upper()
    return results
