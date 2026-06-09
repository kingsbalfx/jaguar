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


def _avg_range(df, end_index, lookback=14):
    start = max(0, end_index - lookback + 1)
    window = df.iloc[start : end_index + 1]
    if window.empty:
        return 0.0
    ranges = (window["high"] - window["low"]).astype(float)
    return float(ranges.mean()) if len(ranges) else 0.0


def _fill_progress(candidate, candle):
    low = float(candidate["low"])
    high = float(candidate["high"])
    gap_size = max(float(candidate["gap_size"]), 1e-9)

    if candidate["type"] == "bullish":
        future_low = float(candle["low"])
        if future_low >= high:
            return 0.0
        penetrated = high - max(future_low, low)
        return max(0.0, min(1.0, penetrated / gap_size))

    future_high = float(candle["high"])
    if future_high <= low:
        return 0.0
    penetrated = min(future_high, high) - low
    return max(0.0, min(1.0, penetrated / gap_size))


def _mitigation_state(df, start_index, candidate):
    best_fill_ratio = 0.0
    mitigation_index = None

    for j in range(start_index + 1, len(df)):
        fill_ratio = _fill_progress(candidate, df.iloc[j])
        if fill_ratio > best_fill_ratio:
            best_fill_ratio = fill_ratio
            mitigation_index = int(j)
        if fill_ratio >= 1.0:
            break

    return {
        "fill_ratio": round(best_fill_ratio, 3),
        "mitigated": best_fill_ratio >= 1.0,
        "partially_mitigated": 0.0 < best_fill_ratio < 1.0,
        "mitigation_index": mitigation_index,
    }


def detect_fvg_from_df(df, trend=None, min_gap_ratio=0.12, min_body_ratio=0.55):
    fvgs = []

    if df is None or len(df) < 3:
        return fvgs
    if not set(["high", "low", "open", "close"]).issubset(df.columns):
        return fvgs

    for i in range(2, len(df)):
        try:
            c1 = df.iloc[i - 2]
            c2 = df.iloc[i - 1]
            c3 = df.iloc[i]

            middle_open = float(c2["open"])
            middle_close = float(c2["close"])
            middle_high = float(c2["high"])
            middle_low = float(c2["low"])
            middle_range = max(middle_high - middle_low, 1e-9)
            middle_body_ratio = abs(middle_close - middle_open) / middle_range
            displacement_ok = middle_body_ratio >= min_body_ratio

            average_range = max(_avg_range(df, i), 1e-9)

            candidates = []
            high1 = float(c1["high"])
            low1 = float(c1["low"])
            high3 = float(c3["high"])
            low3 = float(c3["low"])

            if high1 < low3:
                candidates.append(
                    {
                        "type": "bullish",
                        "low": high1,
                        "high": low3,
                        "reference_low": low1,
                        "reference_high": high3,
                    }
                )

            if low1 > high3:
                candidates.append(
                    {
                        "type": "bearish",
                        "low": high3,
                        "high": low1,
                        "reference_low": low3,
                        "reference_high": high1,
                    }
                )

            for candidate in candidates:
                gap_size = float(candidate["high"]) - float(candidate["low"])
                size_ratio = gap_size / average_range
                size_ok = size_ratio >= min_gap_ratio
                context_aligned = trend is None or trend == candidate["type"]
                mitigation = _mitigation_state(df, i, {**candidate, "gap_size": gap_size})
                quality = min(
                    1.0,
                    (size_ratio * 0.55) + (middle_body_ratio * 0.35) + (0.10 if context_aligned else 0.0),
                )

                record = {
                    **candidate,
                    "index": int(i),
                    "gap_size": round(gap_size, 6),
                    "gap_ratio": round(size_ratio, 3),
                    "middle_body_ratio": round(middle_body_ratio, 3),
                    "displacement_ok": displacement_ok,
                    "size_ok": size_ok,
                    "context_aligned": context_aligned,
                    "quality": round(quality, 3),
                    "midpoint": round((float(candidate["low"]) + float(candidate["high"])) / 2.0, 6),
                    "origin_index": int(i - 1),
                    "structure_break_confirmed": False,
                    "liquidity_sweep_confirmed": False,
                    **mitigation,
                    "active": not mitigation["mitigated"],
                }

                if size_ok and displacement_ok and context_aligned:
                    fvgs.append(record)
        except Exception:
            continue

    return fvgs


def qualify_fvgs(fvgs, *, direction=None, structure_break=False, liquidity_sweep=False, fib=None):
    """Attach narrative evidence and rank FVGs without silently discarding them."""
    qualified = []
    expected = "bullish" if str(direction or "").lower() in ("buy", "bullish", "long") else "bearish"
    for fvg in fvgs or []:
        if not isinstance(fvg, dict):
            continue
        item = dict(fvg)
        item["structure_break_confirmed"] = bool(structure_break)
        item["liquidity_sweep_confirmed"] = bool(liquidity_sweep)
        midpoint = float(item.get("midpoint", (float(item["low"]) + float(item["high"])) / 2.0))
        correct_zone = True
        if fib:
            correct_zone = midpoint <= float(fib["0.5"]) if expected == "bullish" else midpoint >= float(fib["0.5"])
        item["premium_discount_aligned"] = correct_zone
        evidence = [
            bool(item.get("displacement_ok")),
            bool(item.get("size_ok")),
            bool(item.get("context_aligned")),
            bool(structure_break),
            bool(liquidity_sweep),
            bool(correct_zone),
            bool(item.get("active")) and not bool(item.get("mitigated")),
        ]
        item["narrative_score"] = round(sum(evidence) / len(evidence), 3)
        item["true_fvg"] = item.get("type") == expected and item["narrative_score"] >= 0.70
        qualified.append(item)
    return sorted(qualified, key=lambda item: (not item.get("true_fvg", False), -float(item.get("narrative_score", 0.0)), -float(item.get("quality", 0.0))))


def detect_fvgs(symbol, timeframe, bars=200, trend=None):
    _require_mt5()
    tf = _tf_to_mt5(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None or len(rates) == 0:
        return []

    df = pd.DataFrame(rates)
    for col in ["high", "low", "open", "close"]:
        if col not in df.columns:
            return []

    fvgs = detect_fvg_from_df(df, trend=trend)
    for fvg in fvgs:
        fvg["timeframe"] = timeframe
    return fvgs


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
