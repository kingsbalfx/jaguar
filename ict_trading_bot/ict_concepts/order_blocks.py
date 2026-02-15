import MetaTrader5 as mt5
import pandas as pd


def detect_order_blocks(df, structure_points):
    obs = []

    for s in structure_points:
        # structure_points format may vary; keep defensive
        try:
            tag, idx, price = s
        except Exception:
            continue

        if tag == "BOS":
            prev = df.iloc[idx-1]

            ob = {
                "type": "bullish" if df['close'][idx] > df['open'][idx] else "bearish",
                "high": prev['high'],
                "low": prev['low'],
                "index": idx
            }
            obs.append(ob)

    return obs


def detect_htf_order_blocks(symbol, timeframe, bars=500):
    tf = _tf_to_mt5(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None or len(rates) == 0:
        return []

    df = pd.DataFrame(rates)
    # simplified placeholder: mark prior swing highs as order blocks
    obs = []
    if not set(['high', 'low', 'close', 'open']).issubset(df.columns) or len(df) < 5:
        return obs

    for i in range(2, len(df) - 2):
        try:
            hi = float(df['high'].iloc[i])
            lo = float(df['low'].iloc[i])
            prev_hi = float(df['high'].iloc[i-1])
            prev_lo = float(df['low'].iloc[i-1])
            next_hi = float(df['high'].iloc[i+1])
            next_lo = float(df['low'].iloc[i+1])

            if hi > prev_hi and hi > next_hi:
                obs.append({
                    'type': 'bearish',
                    'high': prev_hi,
                    'low': prev_lo,
                    'index': i
                })
            if lo < prev_lo and lo < next_lo:
                obs.append({
                    'type': 'bullish',
                    'high': prev_hi,
                    'low': prev_lo,
                    'index': i
                })
        except Exception:
            continue

    return obs


def _tf_to_mt5(tf):
    mapping = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
    }
    return mapping.get(tf, tf)
