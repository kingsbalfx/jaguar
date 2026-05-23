"""
REGIME CLASSIFIER
Identifies the current market environment.
Only trending / volatile regimes are tradeable.
"""

def classify_regime(features, topdown_analysis):
    if features is None:
        return "unknown"

    trend = topdown_analysis.get("overall_trend", "neutral")
    if trend not in ("bullish", "bearish"):
        return "ranging"

    body = features["body_ratio"]
    range_pct = features["range_percentile"]
    atr = features["atr"]
    vol_spike = features["volume_spike"]
    sweep = features["sweep"]
    displacement = features["displacement"]
    bos = features["bos"]

    # If we have sweep + displacement + BOS, it's either trending or volatile
    if sweep and displacement and bos and range_pct > 1.1 and body > 0.55:
        return "volatile"

    # Strong directional persistence without expansion -> trending
    if bos and body > 0.5 and range_pct > 0.9 and atr > 0:
        return "trending"

    # Low range, no structure -> ranging
    if range_pct < 0.8 and not bos:
        return "ranging"

    # Compression
    if range_pct < 0.7 and atr < 1e-6:
        return "compressing"

    # Default to ranging if unclear
    return "ranging"


def is_tradeable_regime(regime):
    return regime in ("trending", "volatile")