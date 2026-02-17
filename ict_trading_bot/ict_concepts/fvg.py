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


def detect_fvg_from_df(df):
    fvgs = []

    # Defensive: require enough rows and necessary columns
    if df is None or len(df) < 3:
        return fvgs
    if not set(["high", "low"]).issubset(df.columns):
        return fvgs

    for i in range(2, len(df)):
        try:
            c1 = df.iloc[i-2]
            c2 = df.iloc[i-1]
            c3 = df.iloc[i]

            # Bullish FVG
            if c1['high'] < c3['low']:
                fvgs.append({
                    "type": "bullish",
                    "low": float(c1['high']),
                    "high": float(c3['low']),
                    "index": int(i)
                })

            # Bearish FVG
            if c1['low'] > c3['high']:
                fvgs.append({
                    "type": "bearish",
                    "high": float(c1['low']),
                    "low": float(c3['high']),
                    "index": int(i)
                })
        except Exception:
            # skip malformed rows
            continue

    return fvgs


def detect_fvgs(symbol, timeframe, bars=200):
    _require_mt5()
    tf = _tf_to_mt5(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None or len(rates) == 0:
        return []

    df = pd.DataFrame(rates)
    # make sure numeric columns exist
    for col in ['high', 'low']:
        if col not in df.columns:
            return []

    return detect_fvg_from_df(df)


def _tf_to_mt5(tf):
    _require_mt5()
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
