"""
Jaguar Trend Dynamics Analyzer
Full ICT rhythm metrics: alignment, continuation, displacement,
OTE zone, and Market Structure Shift (MSS) detection.
Now adapts weights using the live probability table.
"""

import json
from pathlib import Path

PROBABILITY_FILE = Path(__file__).resolve().parent.parent / "data" / "ict_probabilities.json"

def _load_regime_stats(regime):
    """Load the win rate for the current regime from the probability table."""
    try:
        with open(PROBABILITY_FILE, 'r') as f:
            table = json.load(f)
    except Exception:
        return None
    regime_table = table.get(regime)
    if not regime_table:
        return None
    total = regime_table.get("count", 0)
    if total < 5:
        return None
    # compute overall win rate for this regime from the default key (which is the aggregate)
    win_rate = regime_table.get("default", 0.5)
    return win_rate


def analyze_market_rhythm(analysis: dict, trend: str) -> dict:
    if not isinstance(analysis, dict):
        return {
            "trend_strength": 0.5,
            "market_condition": "normal",
        }

    htf = analysis.get("HTF") or {}
    mtf = analysis.get("MTF") or {}
    ltf = analysis.get("LTF") or {}
    execution = analysis.get("EXECUTION") or {}

    # --- 1. Multi‑timeframe alignment score ---
    tf_trends = [
        htf.get("trend"),
        mtf.get("trend"),
        ltf.get("trend"),
        execution.get("trend"),
    ]
    aligned = sum(1 for t in tf_trends if t == trend)
    total = sum(1 for t in tf_trends if t is not None)
    alignment_score = aligned / max(total, 1)

    # --- 2. Structural continuation (HH/HL or LL/LH) ---
    def _continuation(swings, direction):
        if not swings:
            return 0.5
        highs = [s for s in swings if s.get("type") == "high"]
        lows = [s for s in swings if s.get("type") == "low"]
        if len(highs) < 2 or len(lows) < 2:
            return 0.5
        if direction == "bullish":
            hh = float(highs[-1]["price"]) > float(highs[-2]["price"])
            hl = float(lows[-1]["price"]) > float(lows[-2]["price"])
        else:
            hh = float(highs[-1]["price"]) < float(highs[-2]["price"])
            hl = float(lows[-1]["price"]) < float(lows[-2]["price"])
        return (0.5 if hh else 0.0) + (0.5 if hl else 0.0)

    mtf_swings = mtf.get("swings", [])
    ltf_swings = ltf.get("swings", [])
    cont_mtf = _continuation(mtf_swings, trend)
    cont_ltf = _continuation(ltf_swings, trend)
    continuation_score = (cont_mtf * 0.6) + (cont_ltf * 0.4)

    # --- 3. Displacement (swing range expansion relative to ATR) ---
    def _displacement_score(swings, atr):
        if not swings or atr <= 0:
            return 0.5
        highs = [float(s["price"]) for s in swings if s.get("type") == "high"]
        lows = [float(s["price"]) for s in swings if s.get("type") == "low"]
        if not highs or not lows:
            return 0.5
        recent_high = max(highs[-5:]) if len(highs) >= 5 else max(highs)
        recent_low = min(lows[-5:]) if len(lows) >= 5 else min(lows)
        swing_range = recent_high - recent_low
        if swing_range <= 0:
            return 0.5
        ratio = swing_range / (atr * 14)
        return min(1.0, max(0.0, (ratio - 0.5) / 2.0))

    atr = float(mtf.get("atr", 0) or htf.get("atr", 0) or 0)
    if atr <= 0:
        atr = 0.0001
    displacement = _displacement_score(mtf_swings, atr)

    # --- 4. OTE Zone (position within recent range) ---
    def _ote_score(swings, price, direction):
        if not swings:
            return 0.5
        highs = [float(s["price"]) for s in swings if s.get("type") == "high"]
        lows = [float(s["price"]) for s in swings if s.get("type") == "low"]
        if not highs or not lows:
            return 0.5
        recent_high = max(highs[-5:]) if len(highs) >= 5 else max(highs)
        recent_low = min(lows[-5:]) if len(lows) >= 5 else min(lows)
        if recent_high <= recent_low:
            return 0.5
        position_pct = (price - recent_low) / (recent_high - recent_low)
        if direction == "bullish":
            return 1.0 - position_pct
        else:
            return position_pct

    price = float(analysis.get("price", 0) or 0)
    ote = _ote_score(mtf_swings, price, trend)

    # --- 5. MSS Detection (Market Structure Shift) ---
    def _detect_mss(swings, direction):
        if not swings:
            return False
        lows = [s for s in swings if s.get("type") == "low"]
        highs = [s for s in swings if s.get("type") == "high"]
        if len(lows) < 2 or len(highs) < 2:
            return False
        if direction == "bullish":
            return float(lows[-1]["price"]) < float(lows[-2]["price"])
        else:
            return float(highs[-1]["price"]) > float(highs[-2]["price"])

    mss = _detect_mss(mtf_swings, trend)

    # --- 6. Adaptive weights from probability table ---
    regime = None
    combined_base = (alignment_score * 0.4 + continuation_score * 0.3 + displacement * 0.15 + ote * 0.15)
    if combined_base >= 0.75:
        regime = "trending"
    elif combined_base >= 0.55:
        regime = "volatile"
    elif combined_base >= 0.35:
        regime = "ranging"
    else:
        regime = "compressing"

    regime_win_rate = _load_regime_stats(regime)
    adaptive_multiplier = 1.0
    if regime_win_rate is not None:
        adaptive_multiplier = 0.8 + (regime_win_rate * 0.4)

    # --- 7. Combine into final strength ---
    mss_penalty = 0.15 if mss else 0.0
    combined = (
        alignment_score * 0.4 +
        continuation_score * 0.3 +
        displacement * 0.15 +
        ote * 0.15
    ) - mss_penalty
    combined = max(0.0, min(1.0, combined * adaptive_multiplier))

    # --- 8. Market condition ---
    if combined >= 0.75:
        market_condition = "trending"
    elif combined >= 0.55:
        market_condition = "volatile"
    elif combined >= 0.35:
        market_condition = "ranging"
    else:
        market_condition = "compressing"

    return {
        "trend_strength": round(combined, 3),
        "market_condition": market_condition,
    }