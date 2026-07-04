"""Strict true order block detection."""

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

import pandas as pd


def _as_frame(candles):
    if isinstance(candles, pd.DataFrame):
        return candles.reset_index(drop=True).copy()
    return pd.DataFrame(candles or []).reset_index(drop=True)


def find_true_order_block(candles, displacement_index, direction, timeframe="M5", search_bars=8):
    """Find the final opposing candle immediately preceding an impulse."""
    frame = _as_frame(candles)
    direction = str(direction or "").lower()
    bullish = direction in ("buy", "bullish", "long")
    displacement_index = int(displacement_index)
    if displacement_index < 1 or displacement_index >= len(frame):
        return None
    impulse = frame.iloc[displacement_index]
    impulse_range = max(float(impulse["high"]) - float(impulse["low"]), 1e-12)
    impulse_body = abs(float(impulse["close"]) - float(impulse["open"]))
    impulse_directional = (
        float(impulse["close"]) > float(impulse["open"])
        if bullish
        else float(impulse["close"]) < float(impulse["open"])
    )
    if impulse_body / impulse_range < 0.60 or not impulse_directional:
        return None

    origin = None
    for index in range(displacement_index - 1, max(-1, displacement_index - search_bars - 1), -1):
        candle = frame.iloc[index]
        opposing = (
            float(candle["close"]) < float(candle["open"])
            if bullish
            else float(candle["close"]) > float(candle["open"])
        )
        if opposing:
            origin = index
            break
    if origin is None:
        return None

    candle = frame.iloc[origin]
    # ICT standard: use full candle range (wick + body) for the order block zone
    ob_low = min(float(candle["open"]), float(candle["close"]), float(candle["low"]))
    ob_high = max(float(candle["open"]), float(candle["close"]), float(candle["high"]))
    touched = False
    mitigation_index = None
    for index in range(displacement_index + 1, len(frame)):
        future = frame.iloc[index]
        if float(future["low"]) <= ob_high and float(future["high"]) >= ob_low:
            touched = True
            mitigation_index = index
            break
    return {
        "type": "bullish" if bullish else "bearish",
        "low": ob_low,
        "high": ob_high,
        "wick_low": float(candle["low"]),
        "wick_high": float(candle["high"]),
        "midpoint": (ob_low + ob_high) / 2.0,
        "origin_index": origin,
        "displacement_index": displacement_index,
        "index": displacement_index,
        "timeframe": str(timeframe).upper(),
        "final_opposing_candle": True,
        "displacement_ok": True,
        "fresh": not touched,
        "mitigated": touched,
        "mitigation_index": mitigation_index,
    }


def detect_order_blocks(df, structure_points):
    frame = _as_frame(df)
    blocks = []
    for point in structure_points or []:
        if isinstance(point, dict):
            index = point.get("index")
            direction = point.get("direction") or point.get("trend")
        else:
            _, index, direction = point
        block = find_true_order_block(frame, int(index), direction, timeframe="dynamic")
        if block:
            blocks.append(block)
    return blocks


def qualify_order_blocks(order_blocks, *, direction=None, structure_break=False, liquidity_sweep=False, fvgs=None, fib=None):
    expected = "bullish" if str(direction or "").lower() in ("buy", "bullish", "long") else "bearish"
    fvg_origins = {
        int(item.get("displacement_index", item.get("origin_index")))
        for item in fvgs or []
        if isinstance(item, dict) and item.get("displacement_index", item.get("origin_index")) is not None
    }
    qualified = []
    for source in order_blocks or []:
        if not isinstance(source, dict):
            continue
        item = dict(source)
        midpoint = float(item.get("midpoint", (float(item["low"]) + float(item["high"])) / 2.0))
        correct_zone = True
        if fib and "0.5" in fib:
            correct_zone = midpoint <= float(fib["0.5"]) if expected == "bullish" else midpoint >= float(fib["0.5"])
        displacement_index = int(item.get("displacement_index", int(item.get("index", -2)) + 1))
        same_impulse = displacement_index in fvg_origins
        item["caused_structure_break"] = bool(structure_break)
        item["liquidity_sweep_confirmed"] = bool(liquidity_sweep)
        item["created_fvg"] = same_impulse
        item["premium_discount_aligned"] = correct_zone
        item["true_order_block"] = all(
            (
                item.get("type") == expected,
                bool(item.get("final_opposing_candle")),
                bool(item.get("displacement_ok", float(item.get("displacement", 0.0) or 0.0) >= 0.60)),
                bool(structure_break),
                bool(liquidity_sweep),
                same_impulse,
                correct_zone,
                str(item.get("timeframe", "M5")).upper() in ("M1", "M5", "DYNAMIC"),
                bool(item.get("fresh", True)) and not bool(item.get("mitigated", False)),
            )
        )
        qualified.append(item)
    return qualified


def detect_htf_order_blocks(symbol, timeframe, bars=500):
    """Compatibility API. Entry logic rejects these because they are not M1/M5."""
    if mt5 is None:
        return []
    mapped = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "W1": mt5.TIMEFRAME_W1,
        "D1": mt5.TIMEFRAME_D1,
    }.get(str(timeframe).upper())
    if mapped is None:
        return []
    rates = mt5.copy_rates_from_pos(symbol, mapped, 0, bars)
    if rates is None:
        return []
    frame = pd.DataFrame(rates)
    blocks = []
    for index in range(1, len(frame)):
        for direction in ("bullish", "bearish"):
            block = find_true_order_block(frame, index, direction, timeframe=timeframe)
            if block:
                blocks.append(block)
    return blocks
