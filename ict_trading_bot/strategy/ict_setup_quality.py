"""
ICT SETUP QUALITY ESTIMATOR
Extended with Silver Bullet, AMD, Turtle Soup,
Opening Candle Bias, Weekly Opening Gap, and Daily Opening Gap.
"""

import os, json
from pathlib import Path

PROBABILITY_FILE = Path(__file__).resolve().parent.parent / "data" / "ict_probabilities.json"

def load_probability_table():
    if PROBABILITY_FILE.exists():
        try:
            with open(PROBABILITY_FILE, "r") as f:
                return json.load(f)
        except: pass
    return _default_table()

def _default_table():
    return {
        "trending": {
            "sweep_yes_displacement_yes_ob_yes": 0.62,
            "sweep_yes_displacement_yes_ob_no": 0.55,
            "sweep_yes_displacement_no_ob_yes": 0.50,
            "default": 0.48
        },
        "volatile": {
            "sweep_yes_displacement_yes_ob_yes": 0.58,
            "sweep_yes_displacement_yes_ob_no": 0.52,
            "default": 0.50
        },
        "ranging": {"default": 0.45},
        "compressing": {"default": 0.40},
        "unknown": {"default": 0.45}
    }

def calculate_success_probability(features, regime, killzone_active=False):
    if features is None:
        return 0.0, "missing_features"

    table = load_probability_table()
    regime_table = table.get(regime, {"default": 0.45})

    sweep = features["sweep"]
    displacement = features["displacement"]
    ob = features["ob_exists"]
    if sweep and displacement and ob:
        key = "sweep_yes_displacement_yes_ob_yes"
    elif sweep and displacement and not ob:
        key = "sweep_yes_displacement_yes_ob_no"
    elif sweep and not displacement and ob:
        key = "sweep_yes_displacement_no_ob_yes"
    else:
        key = "default"

    base_prob = regime_table.get(key, regime_table.get("default", 0.45))

    # Time window bonuses
    if killzone_active:
        base_prob *= 1.15
    else:
        base_prob *= 0.90

    if features.get("silver_bullet_window"):
        base_prob *= 1.20

    # ICT pattern bonuses
    if features.get("amd_setup"):
        base_prob *= 1.25
    if features.get("turtle_soup"):
        base_prob *= 1.15

    # Displacement quality
    if features["body_ratio"] > 0.70:
        base_prob *= 1.05
    if features["range_percentile"] > 1.3:
        base_prob *= 1.05

    # Volume confirmation
    if features["volume_spike"]:
        base_prob *= 1.08

    # Opening candle bias bonus (cautious)
    if features.get("opening_bias_aligned", True):
        base_prob *= 1.03

    # Weekly opening gap bonus
    gap = features.get("weekly_gap", {})
    if gap.get("direction") != "none" and not gap.get("filled", True):
        trend = features.get("trend", "neutral")
        if (trend == "bullish" and gap["direction"] == "bearish") or \
           (trend == "bearish" and gap["direction"] == "bullish"):
            base_prob *= 1.04

    # Daily opening gap bonus
    daily_gap = features.get("daily_gap", {})
    if daily_gap.get("direction") != "none" and not daily_gap.get("filled", True):
        trend = features.get("trend", "neutral")
        if (trend == "bullish" and daily_gap["direction"] == "bearish") or \
           (trend == "bearish" and daily_gap["direction"] == "bullish"):
            base_prob *= 1.04

    base_prob = min(0.88, max(0.30, base_prob))
    quality = base_prob * 100
    return round(base_prob, 4), round(quality, 1)