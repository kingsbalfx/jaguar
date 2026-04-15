try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None
import pandas as pd


def _require_mt5():
    if mt5 is None:
        raise RuntimeError(
            "MetaTrader5 package not available on this platform. "
            "Run the bot on Windows with MT5 installed."
        )


def _volume_value(row):
    return float(row.get("tick_volume", row.get("volume", 0.0)) or 0.0)


def _liquidity_sweep_present(df, idx, order_type):
    if idx < 2:
        return False

    current = df.iloc[idx]
    previous_window = df.iloc[max(0, idx - 4) : idx]
    if previous_window.empty:
        return False

    if order_type == "bullish":
        prior_low = float(previous_window["low"].min())
        return float(current["low"]) < prior_low and float(current["close"]) > float(current["open"])
    prior_high = float(previous_window["high"].max())
    return float(current["high"]) > prior_high and float(current["close"]) < float(current["open"])


def _build_order_block(df, idx, timeframe, symbol=None):
    if idx < 1:
        return None

    current = df.iloc[idx]
    previous = df.iloc[idx - 1]
    current_close = float(current["close"])
    current_open = float(current["open"])
    current_high = float(current["high"])
    current_low = float(current["low"])
    body = abs(current_close - current_open)
    candle_range = max(current_high - current_low, 1e-9)
    displacement = body / candle_range
    order_type = "bullish" if current_close > current_open else "bearish"

    average_volume = float(df.iloc[max(0, idx - 10) : idx]["tick_volume"].mean()) if "tick_volume" in df.columns else 0.0
    volume_boost = _volume_value(current) >= max(average_volume * 1.15, 1.0)
    liquidity_sweep = _liquidity_sweep_present(df, idx, order_type)
    institutional_footprint = displacement >= 0.70 and volume_boost and liquidity_sweep

    if not institutional_footprint:
        return None

    quality = min(
        1.0,
        (displacement * 0.55)
        + (0.20 if volume_boost else 0.0)
        + (0.25 if liquidity_sweep else 0.0),
    )

    block = {
        "type": order_type,
        "high": float(previous["high"]),
        "low": float(previous["low"]),
        "index": int(idx),
        "timeframe": timeframe,
        "displacement": round(displacement, 3),
        "liquidity_sweep_confirmed": liquidity_sweep,
        "volume_boost": volume_boost,
        "institutional_footprint": institutional_footprint,
        "quality": round(quality, 3),
    }
    if symbol:
        block["id"] = f"{symbol}|{timeframe}|{order_type}|{idx}"
    return block


def detect_order_blocks(df, structure_points):
    obs = []
    if df is None or len(df) == 0:
        return obs

    for point in structure_points or []:
        try:
            if isinstance(point, dict):
                tag = point.get("event", point.get("tag"))
                idx = int(point.get("index"))
            else:
                tag, idx, _ = point
        except Exception:
            continue

        if tag != "BOS":
            continue
        block = _build_order_block(df, idx, timeframe="dynamic")
        if block:
            obs.append(block)

    return obs


def detect_htf_order_blocks(symbol, timeframe, bars=500):
    _require_mt5()
    tf = _tf_to_mt5(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None or len(rates) == 0:
        return []

    df = pd.DataFrame(rates)
    if not set(["high", "low", "close", "open"]).issubset(df.columns) or len(df) < 5:
        return []

    obs = []
    for i in range(2, len(df) - 2):
        block = _build_order_block(df, i, timeframe=timeframe, symbol=symbol)
        if block:
            obs.append(block)

    return obs


def _tf_to_mt5(tf):
    _require_mt5()
    mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    return mapping.get(tf, tf)
