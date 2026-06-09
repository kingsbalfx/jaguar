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


def _build_order_block(df, idx, timeframe, symbol=None, lookahead_bars=200):
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
    # RELAXED: Changed from AND to OR - more permissive
    institutional_footprint = displacement >= 0.55 and (volume_boost or liquidity_sweep)

    # RELAXED: Don't reject blocks, just mark quality lower
    if not institutional_footprint:
        # Still create block but with reduced quality
        pass  # Continue to quality calculation

    quality = min(
        1.0,
        (displacement * 0.55)
        + (0.20 if volume_boost else 0.0)
        + (0.25 if liquidity_sweep else 0.0),
    )

    block_high = float(previous["high"])
    block_low = float(previous["low"])
    future = df.iloc[idx + 1 : min(len(df), idx + 1 + max(10, int(lookahead_bars)))]
    mitigated = False
    if not future.empty and {"high", "low"}.issubset(future.columns):
        try:
            touched = (future["low"].astype(float) <= block_high) & (future["high"].astype(float) >= block_low)
            mitigated = bool(touched.any())
        except Exception:
            mitigated = False

    block = {
        "type": order_type,
        "high": block_high,
        "low": block_low,
        "index": int(idx),
        "timeframe": timeframe,
        "displacement": round(displacement, 3),
        "liquidity_sweep_confirmed": liquidity_sweep,
        "volume_boost": volume_boost,
        "institutional_footprint": institutional_footprint,
        "quality": round(quality, 3),
        "midpoint": round((block_high + block_low) / 2.0, 6),
        "origin_index": int(idx - 1),
        "caused_structure_break": False,
        "created_fvg": False,
        "mitigated": mitigated,
        "fresh": not mitigated,
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


def qualify_order_blocks(order_blocks, *, direction=None, structure_break=False, liquidity_sweep=False, fvgs=None, fib=None):
    """Rank order blocks by narrative evidence instead of treating every candle equally."""
    expected = "bullish" if str(direction or "").lower() in ("buy", "bullish", "long") else "bearish"
    fvg_origins = {int(fvg.get("origin_index")) for fvg in (fvgs or []) if isinstance(fvg, dict) and fvg.get("origin_index") is not None}
    qualified = []
    for ob in order_blocks or []:
        if not isinstance(ob, dict):
            continue
        item = dict(ob)
        item["caused_structure_break"] = bool(structure_break)
        item["created_fvg"] = int(item.get("index", -999)) in fvg_origins or int(item.get("index", -999)) + 1 in fvg_origins
        item["liquidity_sweep_confirmed"] = bool(item.get("liquidity_sweep_confirmed") or liquidity_sweep)
        midpoint = float(item.get("midpoint", (float(item["low"]) + float(item["high"])) / 2.0))
        correct_zone = True
        if fib:
            correct_zone = midpoint <= float(fib["0.5"]) if expected == "bullish" else midpoint >= float(fib["0.5"])
        item["premium_discount_aligned"] = correct_zone
        evidence = [
            bool(item.get("institutional_footprint")),
            bool(item.get("displacement", 0.0) >= 0.55),
            bool(item.get("caused_structure_break")),
            bool(item.get("created_fvg")),
            bool(item.get("liquidity_sweep_confirmed")),
            bool(correct_zone),
            bool(item.get("fresh")) and not bool(item.get("mitigated")),
        ]
        item["narrative_score"] = round(sum(evidence) / len(evidence), 3)
        item["true_order_block"] = item.get("type") == expected and item["narrative_score"] >= 0.70
        qualified.append(item)
    return sorted(qualified, key=lambda item: (not item.get("true_order_block", False), -float(item.get("narrative_score", 0.0)), -float(item.get("quality", 0.0))))


def detect_htf_order_blocks(symbol, timeframe, bars=500):
    if mt5 is None:
        return []
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
    if mt5 is None:
        return None
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
