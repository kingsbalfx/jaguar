import pandas as pd


def _volume_value(row):
    return float(row.get("volume", row.get("tick_volume", 0.0)) or 0.0)


def find_swings(df, lookback=3):
    swings = []
    if df is None or len(df) < (lookback * 2) + 1:
        return swings

    average_range = float((df["high"] - df["low"]).mean()) if "high" in df and "low" in df else 0.0
    average_volume = (
        float(df.get("volume", df.get("tick_volume", pd.Series([0.0] * len(df)))).mean())
        if len(df)
        else 0.0
    )

    for i in range(lookback, len(df) - lookback):
        row = df.iloc[i]
        high = float(row["high"])
        low = float(row["low"])
        local_highs = df["high"].iloc[i - lookback : i + lookback + 1]
        local_lows = df["low"].iloc[i - lookback : i + lookback + 1]
        candle_range = float(row["high"] - row["low"])
        range_score = candle_range / max(average_range, 1e-9)
        volume_score = _volume_value(row) / max(average_volume, 1e-9) if average_volume > 0 else 1.0
        weight = round(min(3.0, (range_score * 0.6) + (volume_score * 0.4)), 3)
        strength = "strong" if weight >= 1.2 else "weak"

        if high >= float(local_highs.max()):
            swings.append(
                {
                    "type": "high",
                    "index": int(i),
                    "price": high,
                    "weight": weight,
                    "strength": strength,
                }
            )

        if low <= float(local_lows.min()):
            swings.append(
                {
                    "type": "low",
                    "index": int(i),
                    "price": low,
                    "weight": weight,
                    "strength": strength,
                }
            )

    return swings
