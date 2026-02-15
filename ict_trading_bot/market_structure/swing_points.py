import pandas as pd

def find_swings(df, lookback=3):
    swings = []

    for i in range(lookback, len(df) - lookback):
        high = df['high'][i]
        low = df['low'][i]

        if high == max(df['high'][i-lookback:i+lookback]):
            swings.append(("high", i, high))

        if low == min(df['low'][i-lookback:i+lookback]):
            swings.append(("low", i, low))

    return swings
