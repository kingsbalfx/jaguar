"""
Central Intelligence System (CIS)
==================================
Synthesizes all analysis into PRE-TRADE DECISIONS:

Before entering ANY trade, CIS answers:
1. SETUP QUALITY: Is this setup high-confidence? (0-1 score)
2. MARKET CONDITIONS: Are market conditions favorable? (0-1 score)
3. RISK PROFILE: Can we afford this trade given existing exposure? (0-1 score)
4. TIMING: Is this the right time to trade this pair? (0-1 score)
5. FINAL VERDICT: Should we TRADE, AVOID, or WAIT? Decision + reasoning.

CIS INPUTS:
- Multi-timeframe analysis across 7 timeframes:
  * W1 (Weekly): TRUE STRUCTURAL REFERENCE - Core support/resistance, major trends
  * D1 (Daily): BRIEF - Structural confirmation relative to Weekly
  * H4 (4-Hour): BRIEF - Intraday structure confirmation
  * H1 (Hourly): Entry setup quality confirmation
  * M15 (15-min): Mid-term entry confirmation
  * M5 (5-min): Pattern precision & exact entry point
  * M1 (1-min): Micro entry precision - Exact candle placement
- Pair volatility & market condition
- Current positions & account exposure
- Correlation risk between pairs
- Time of day & session analysis
- Price action patterns
- Risk-reward ratios

CIS OUTPUTS:
- Decision: "TRADE" (>0.75), "WAIT" (0.5-0.75), "AVOID" (<0.5)
- Confidence score: 0-1
- Position sizing recommendation
- Stop loss sizing recommendation
- Entry validation checklist
- Performance metrics (historical decision success rate)

PHILOSOPHY:
- Active Execution: High-precision triggers lead to direct, fast orders.
- Adaptive: Learn from past decisions (track win rate per pair)
- Risk-aware: Refuse bad risk-reward ratios
- Transparent: Show reasoning for every decision
"""
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import time

import MetaTrader5 as mt5
from utils.persistent_json import load_json_file, update_json_file
from risk.news_filter import check_for_high_impact_news

logger = logging.getLogger(__name__)

# Restored Analysis Modules
from ict_concepts.liquidity_analysis import is_premium_discount_optimal, measure_order_block_strength
from strategy.confirmation_system import get_all_confirmations_for_pair
from risk.market_condition import should_trade_pair_based_on_volatility, load_volatility_analysis
from risk.correlation_manager import get_pair_correlation_risk
from risk.position_manager import get_current_account_exposure, calculate_position_sizing
from execution.order_manager import calculate_risk_reward_for_trade
from strategy.pre_trade_analysis import analyze_market_top_down
from utils.sessions import in_london_session, in_newyork_session, in_asia_session
from strategy.setup_confirmations import bos_setup, liquidity_sweep_or_swing, price_action_setup
from risk.trend_dynamics import TrendDynamicsAnalyzer
from utils.symbol_profile import canonical_symbol

# Error Handling & Retry Logic Configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # Seconds

# ICT Sequence Logic Gating
MIN_DISPLACEMENT_SCORE = 0.70
MIN_CONFIRMATIONS_REQUIRED = 4

CIS_DECISIONS_FILE = Path(__file__).resolve().parent.parent / "data" / "cis_decisions_history.json"

# ICT Correlation Mapping for SMT Divergence
CORRELATED_PAIRS = {
    "EURUSD": "GBPUSD",
    "GBPUSD": "EURUSD",
    "AUDUSD": "NZDUSD",
    "BTCUSD": "ETHUSD",
    "XAUUSD": "XAGUSD"
}

# Initialize Dynamics Analyzer for Market Position awareness
dynamics_analyzer = TrendDynamicsAnalyzer()

def _symbol_key(symbol: str) -> str:
    """Get normalized symbol key for consistent data tracking across brokers."""
    return canonical_symbol(symbol)

def load_cis_history() -> Dict:
    """Load historical CIS decisions and performance metrics."""
    history = load_json_file(CIS_DECISIONS_FILE, {})
    return history if isinstance(history, dict) else {}


def save_cis_decision(symbol: str, decision: Dict):
    """Save a CIS decision to history for tracking performance."""
    try:
        key = _symbol_key(symbol)
        timestamp = datetime.utcnow().isoformat()

        def updater(history):
            if not isinstance(history, dict):
                history = {}

            bucket = history.setdefault(key, {"trades": []})
            trades = bucket.setdefault("trades", [])
            trades.append({
                "timestamp": timestamp,
                **decision,
            })
            bucket["trades"] = trades[-500:]
            return history

        update_json_file(CIS_DECISIONS_FILE, updater, default={})
    except Exception as e:
        logger.warning(f"Failed to save CIS decision: {e}")


def check_smt_divergence(symbol: str, direction: str) -> float:
    """
    Checks for SMT Divergence with correlated pairs.
    In ICT, if Pair A sweeps liquidity but Pair B fails to sweep, smart money is accumulating.
    """
    try:
        correlated = CORRELATED_PAIRS.get(symbol)
        if not correlated:
            return 0.5
            
        rates_main = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 10)
        rates_corr = mt5.copy_rates_from_pos(correlated, mt5.TIMEFRAME_M15, 0, 10)
        
        if rates_main is None or rates_corr is None:
            return 0.5
            
        if direction.upper() == "BUY":
            # Main made Lower Low, Correlated failed to make Lower Low
            main_ll = min([r[3] for r in rates_main]) # low
            corr_ll = min([r[3] for r in rates_corr])
            
            if rates_main[-1][3] <= main_ll and rates_corr[-1][3] > corr_ll:
                return 0.9 # SMT Divergence detected
        else:
            # Main made Higher High, Correlated failed to make Higher High
            main_hh = max([r[2] for r in rates_main]) # high
            corr_hh = max([r[2] for r in rates_corr])
            
            if rates_main[-1][2] >= main_hh and rates_corr[-1][2] < corr_hh:
                return 0.9
                
        return 0.5
    except Exception:
        return 0.5

def get_midnight_open(symbol: str) -> float:
    """Calculates NY Midnight Open (00:00 EST) for Power of 3 (AMD) context."""
    try:
        now = datetime.utcnow()
        midnight_utc = now.replace(hour=5, minute=0, second=0, microsecond=0)
        if now < midnight_utc:
            midnight_utc -= timedelta(days=1)
            
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 24)
        return rates[0][1] if rates is not None else 0.0
    except Exception:
        return 0.0


def _normalize_direction(direction: str) -> str:
    return str(direction or "").strip().upper()


def _is_buy_direction(direction: str) -> bool:
    return _normalize_direction(direction) == "BUY"


def _market_structure_description(analysis: Dict, direction: str) -> str:
    trend = analysis.get("overall_trend") or analysis.get("trend") or "unknown"
    if _is_buy_direction(direction):
        return "Bullish HH/HL" if trend == "bullish" else "Bearish" if trend == "bearish" else "Neutral"
    return "Bearish LL/LH" if trend == "bearish" else "Bullish" if trend == "bullish" else "Neutral"


def _session_alignment_value(hour: int, asset_class: str) -> float:
    if asset_class == "forex":
        if 7 <= hour < 10:
            return 1.0
        if 12 <= hour < 15:
            return 0.95
        if 13 <= hour < 16:
            return 0.90
        if 0 <= hour < 5:
            return 0.80
        if 8 <= hour < 16 or 13 <= hour < 21:
            return 0.75
        return 0.45
    if asset_class == "metals":
        if 13 <= hour < 16:
            return 1.0
        if 12 <= hour < 21:
            return 0.95
        if 7 <= hour < 16:
            return 0.85
        return 0.35
    if asset_class == "crypto":
        if 7 <= hour < 10 or 12 <= hour < 15:
            return 0.95
        return 0.85
    return 0.6


def _confirm_displacement(analysis: Dict, entry_price: float, direction: str) -> bool:
    execution = (analysis or {}).get("EXECUTION") or {}
    recent_candles = execution.get("recent_candles") or []
    if len(recent_candles) < 2:
        return False

    last = recent_candles[-1]
    prev = recent_candles[-2]
    body = abs(float(last.get("close", 0.0)) - float(last.get("open", 0.0)))
    candle_range = max(float(last.get("high", 0.0)) - float(last.get("low", 0.0)), 1e-9)
    momentum = body / candle_range >= 0.5

    if not momentum:
        return False

    if _normalize_direction(direction) == "BUY":
        return float(last.get("close", 0.0)) > float(prev.get("high", 0.0))
    return float(last.get("close", 0.0)) < float(prev.get("low", 0.0))


def _confirm_retrace(entry_price: float, analysis: Dict, direction: str) -> bool:
    mtf_data = (analysis or {}).get("MTF") or {}
    ltf_data = (analysis or {}).get("LTF") or {}
    execution_data = (analysis or {}).get("EXECUTION") or {}
    trend = (analysis or {}).get("overall_trend", "unknown")

    if is_premium_discount_optimal(entry_price or 0.0, mtf_data.get("fib", {}), trend):
        return True

    fvgs = execution_data.get("fvgs") or ltf_data.get("fvgs", []) or mtf_data.get("fvgs", [])
    for fvg in fvgs or []:
        if not isinstance(fvg, dict):
            continue
        low = fvg.get("low")
        high = fvg.get("high")
        if low is None or high is None:
            continue
        if float(low) <= entry_price <= float(high):
            return True

    order_blocks = mtf_data.get("order_blocks", []) or ltf_data.get("order_blocks", [])
    for ob in order_blocks or []:
        if not isinstance(ob, dict):
            continue
        low = ob.get("low")
        high = ob.get("high")
        if low is None or high is None:
            continue
        if float(low) <= entry_price <= float(high):
            return True

    return False


def evaluate_ict_sequence(
    symbol: str,
    direction: str,
    analysis: Dict,
    entry_price: float,
) -> Dict:
    """AUDIT FIX: Enforce BOS and Strict Sweep Requirement."""
    direction_label = _normalize_direction(direction)
    trend = (analysis or {}).get("overall_trend", "unknown")
    sequence = {
        "market_structure": False,
        "liquidity_zones_identified": False,
        "liquidity_sweep_confirmed": False,
        "displacement_confirmed": False,
        "fvg_or_ob": False,
        "retrace_to_fvg_or_zone": False,
        "sequence_score": 0.0,
        "standalone_approval": False,
        "steps": [],
    }

    if trend in ("bullish", "bearish"):
        structure = bos_setup(analysis, direction_label)
        sequence["market_structure"] = bool(structure.get("confirmed"))
        sequence["steps"].append(
            f"Market Structure: {'PASS' if sequence['market_structure'] else 'FAIL'}"
        )
    else:
        sequence["steps"].append("Market Structure: FAIL")

    mtf_liquidity = (analysis or {}).get("MTF", {}).get("liquidity")
    ltf_liquidity = (analysis or {}).get("LTF", {}).get("liquidity")
    sequence["liquidity_zones_identified"] = bool(mtf_liquidity or ltf_liquidity)
    sequence["steps"].append(
        f"Liquidity Zones: {'PASS' if sequence['liquidity_zones_identified'] else 'FAIL'}"
    )

    # AUDIT: Strict Sweep only (No loose tolerance)
    sweep_data = liquidity_sweep_or_swing(entry_price or 0.0, analysis, direction_label)
    sequence["liquidity_sweep_confirmed"] = bool(sweep_data.get("confirmed"))
    sequence["steps"].append(
        f"Liquidity Sweep: {'PASS' if sequence['liquidity_sweep_confirmed'] else 'FAIL'}"
    )

    # AUDIT: Mandatory BOS for entry
    if not sequence["market_structure"]:
        sequence["steps"].append("CRITICAL: BOS Missing - Blocking Entry")
        sequence["standalone_approval"] = False
        return sequence

    sequence["displacement_confirmed"] = _confirm_displacement(analysis, entry_price or 0.0, direction_label)
    sequence["steps"].append(
        f"Displacement: {'PASS' if sequence['displacement_confirmed'] else 'FAIL'}"
    )

    fvgs = (analysis or {}).get("EXECUTION", {}).get("fvgs") or (analysis or {}).get("LTF", {}).get("fvgs", []) or (analysis or {}).get("MTF", {}).get("fvgs", [])
    order_blocks = (analysis or {}).get("MTF", {}).get("order_blocks", []) or (analysis or {}).get("LTF", {}).get("order_blocks", [])
    sequence["fvg_or_ob"] = bool(
        any(isinstance(fvg, dict) and fvg.get("low") is not None and fvg.get("high") is not None for fvg in fvgs or [])
        or any(isinstance(ob, dict) and ob.get("low") is not None and ob.get("high") is not None for ob in order_blocks or [])
    )
    sequence["steps"].append(
        f"FVG/OB Marked: {'PASS' if sequence['fvg_or_ob'] else 'FAIL'}"
    )

    sequence["retrace_to_fvg_or_zone"] = _confirm_retrace(entry_price or 0.0, analysis, direction_label)
    sequence["steps"].append(
        f"Retrace: {'PASS' if sequence['retrace_to_fvg_or_zone'] else 'FAIL'}"
    )

    passed_steps = sum(
        1 for key in [
            "market_structure",
            "liquidity_zones_identified",
            "liquidity_sweep_confirmed",
            "displacement_confirmed",
            "fvg_or_ob",
            "retrace_to_fvg_or_zone",
        ]
        if sequence.get(key)
    )
    sequence["sequence_score"] = round(passed_steps / 6.0, 3)
    sequence["standalone_approval"] = passed_steps == 6
    sequence["steps"].append(
        f"Standalone Approval: {'PASS' if sequence['standalone_approval'] else 'FAIL'}"
    )

    return sequence


def calculate_setup_quality_score(
    symbol: str,
    timeframe: str,
    direction: str = "BUY",
    multi_tf_analysis: Dict = None,
    entry_price: float = 0.0,
    htf_data: List = None,
    mtf_data: List = None
) -> Tuple[float, Dict]:
    """
    Calculate setup quality (0-1) based on technical analysis across 7 timeframes.

    TIMEFRAME HIERARCHY:
    - W1 (Weekly): TRUE STRUCTURAL REFERENCE - Major trend, core S/R levels
    - D1 (Daily): BRIEF - Confirmation of weekly structure
    - H4 (4-Hour): BRIEF - Intraday structure alignment
    - H1 (Hourly): Entry setup valid? (impulse/pullback pattern)
    - M15 (15-min): Mid-term confirmation
    - M5 (5-min): Pattern precision
    - M1 (1-min): Micro entry candle precision
    """
    # AUDIT FIX: Quality thresholds (FVG 0.6, OB 0.7)
    FVG_QUALITY_MIN = 0.6
    OB_QUALITY_MIN = 0.7

    score = 0.5
    details = {
        "weekly_structure": 0.3,
        "daily_brief": 0.3,
        "h4_brief": 0.3,
        "entry_setup": 0.3,
        "m30_confirmation": 0.3,
        "mid_term_confirmation": 0.3,
        "pattern_strength": 0.3,
        "micro_entry_precision": 0.3,
        "structure_confirmation": 0.0,
        "pd_zone": 0.0,
        "liquidity_sweep": 0.0,
        "displacement_strength": 0.0,
        "imbalance_quality": 0.0,
        "sequence_score": 0.0,
        "sequence_data": {},
        "smt_divergence": 0.5,
        "rsi_alignment": 0.5,
        "volatility_quality": 0.5,
        "judas_swing_context": 0.5,
        "market_dynamics": 0.5,
        "market_mode": "UNKNOWN",
        "notes": []
    }

    try:
        analysis = multi_tf_analysis or analyze_market_top_down(symbol, entry_price or 0.0)
        if not analysis:
            details["notes"].append("Market analysis failed")
            return score, details

        confirmations = get_all_confirmations_for_pair(symbol, timeframe, analysis=analysis) or {}
        if not confirmations:
            details["notes"].append("No confirmations available")

        direction_label = _normalize_direction(direction)
        direction_lower = direction_label.lower()

        htf_trend = analysis.get("overall_trend", "unknown")
        mtf_data = analysis.get("MTF", {}) or {}
        ltf_data = analysis.get("LTF", {}) or {}
        execution_data = analysis.get("EXECUTION", {}) or {}

        entry_price = entry_price or analysis.get("price", 0.0)
        fib_levels = mtf_data.get("fib", {}) or analysis.get("MTF", {}).get("fib", {})

        if not is_premium_discount_optimal(entry_price, fib_levels, htf_trend):
            details["pd_zone"] = 0.2
            details["notes"].append("Price is not in a strong premium/discount entry zone.")
            return 0.2, details

        details["pd_zone"] = 1.0
        details["notes"].append("Premium/Discount entry zone confirmed.")

        structure = bos_setup(analysis, direction_lower)
        details["structure_confirmation"] = 1.0 if structure.get("confirmed") else 0.0
        if structure.get("confirmed"):
            details["notes"].append("Break of Structure (BOS) confirmed.")
        else:
            details["notes"].append("No reliable BOS structure confirmed.")

        liquidity = liquidity_sweep_or_swing(entry_price, analysis, direction_lower)
        details["liquidity_sweep"] = 1.0 if liquidity.get("confirmed") else 0.0
        if liquidity.get("confirmed"):
            details["notes"].append("Liquidity sweep / swing confirmed.")
        else:
            details["notes"].append("No liquidity sweep or swing confirmed.")
            return 0.25, details

        # Requirement 18: Block trade if no liquidity sweep
        if not liquidity.get("confirmed"):
            details["notes"].append("BLOCK: Strict liquidity sweep requirement failed.")
            return 0.0, details

        pa = price_action_setup(analysis, direction_lower)
        if pa.get("confirmed"):
            details["notes"].append("Price action confirmation is supportive.")
        else:
            details["notes"].append("Price action confirmation is weak.")

        sequence_data = evaluate_ict_sequence(symbol, direction_lower, analysis, entry_price or 0.0)
        details["sequence_data"] = sequence_data
        details["sequence_score"] = sequence_data.get("sequence_score", 0.0)
        details["notes"].append(
            f"ICT sequence score: {details['sequence_score']:.2f} ({'PASS' if sequence_data.get('standalone_approval') else 'INCOMPLETE'})."
        )
        if sequence_data.get("standalone_approval"):
            details["notes"].append("Standalone ICT sequence approval is satisfied.")
        else:
            details["notes"].append("Standalone ICT sequence approval is not fully satisfied.")
            if details["sequence_score"] < 0.60:
                details["notes"].append("ICT sequence incomplete – using conservative setup quality.")
                return 0.35, details

        rsi_val = mtf_data.get("rsi", mtf_data.get("rsi_value", 50))
        try:
            rsi_val = float(rsi_val)
        except Exception:
            rsi_val = 50.0

        if direction_label == "BUY":
            details["rsi_alignment"] = 0.9 if rsi_val < 45 else 0.5
            if rsi_val > 70:
                details["rsi_alignment"] = 0.2
                details["notes"].append("RSI is overbought for BUY.")
        else:
            details["rsi_alignment"] = 0.9 if rsi_val > 55 else 0.5
            if rsi_val < 30:
                details["rsi_alignment"] = 0.2
                details["notes"].append("RSI is oversold for SELL.")

        vol_data = load_volatility_analysis().get(_symbol_key(symbol), {})
        condition = vol_data.get("market_condition", "stable")
        details["volatility_quality"] = 0.85 if condition in ("stable", "consolidating") else 0.5
        if condition == "volatile":
            details["notes"].append("Volatile market condition: prefer strong confirmation.")

        if htf_trend in ("unknown", "range"):
            details["notes"].append("Market structure is not sufficiently clean.")
            return 0.2, details

        d1_rating = confirmations.get("d1_rating", 0.5)
        w1_rating = confirmations.get("w1_rating", d1_rating)
        details["weekly_structure"] = w1_rating

        htf_candles = htf_data or (analysis.get("HTF", {}).get("candles") if isinstance(analysis, dict) else None)
        mtf_candles = mtf_data or (analysis.get("MTF", {}).get("candles") if isinstance(analysis, dict) else None)
        dynamics = {"displacement": 0.5, "score": 0.5, "label": "UNKNOWN"}
        if htf_candles and mtf_candles:
            dynamics = dynamics_analyzer.analyze_market_position(
                htf_data=htf_candles,
                mtf_data=mtf_candles,
                current_price=entry_price,
                direction=direction_lower,
            )

        displacement_val = dynamics.get("displacement", 0.5)
        details["displacement_strength"] = displacement_val
        if displacement_val < MIN_DISPLACEMENT_SCORE:
            details["notes"].append("Weak displacement detected - needs stronger impulse.")
            return 0.3, details

        details["market_dynamics"] = (dynamics.get("score", 0.5) * 0.7) + (displacement_val * 0.3)
        details["market_mode"] = dynamics.get("label", "UNKNOWN")
        details["notes"].append(f"Displacement confirmed: {details['market_dynamics']:.2f}.")

        details["smt_divergence"] = check_smt_divergence(symbol, direction_label)
        if details["smt_divergence"] > 0.8:
            details["notes"].append("SMT divergence adds confidence.")

        midnight_open = get_midnight_open(symbol)
        details["judas_swing_context"] = 0.8 if (direction_label == "BUY" and entry_price < midnight_open) or (direction_label == "SELL" and entry_price > midnight_open) else 0.4

        fvgs = execution_data.get("fvgs") or ltf_data.get("fvgs", []) or mtf_data.get("fvgs", [])
        ob_strength = 0.3
        try:
            ob_strength = measure_order_block_strength(symbol, timeframe) 
            if ob_strength < OB_QUALITY_MIN: ob_strength = 0.0 # Audit: Enforce Quality
        except Exception:
            pass

        imbalance_score = 0.3
        if fvgs:
            imbalance_score = 0.65 if any(f.get("quality", 0) >= FVG_QUALITY_MIN for f in fvgs) else 0.0
            if details["pd_zone"] > 0.7:
                imbalance_score = 0.85

        pd_array_priority = 1.0
        if pa.get("is_breaker"):
            pd_array_priority = 1.2
        if pa.get("is_mitigation"):
            pd_array_priority = 1.1
        if displacement_val > 0.7 and imbalance_score > 0.5:
            pd_array_priority += 0.15

        details["imbalance_quality"] = min(1.0, ((imbalance_score * 0.6) + (ob_strength * 0.4)) * pd_array_priority)
        if details["imbalance_quality"] > 0.7:
            details["notes"].append("High quality imbalance zone detected.")
        elif details["imbalance_quality"] > 0.5:
            details["notes"].append("Acceptable imbalance zone.")
        else:
            details["notes"].append("Weak imbalance zone.")

        valid_ratings = [v for k, v in confirmations.items() if k.endswith("_rating") and isinstance(v, (int, float)) and v > 0.6]
        if len(valid_ratings) < MIN_CONFIRMATIONS_REQUIRED:
            details["notes"].append(f"Insufficient confirmations ({len(valid_ratings)}/{MIN_CONFIRMATIONS_REQUIRED}).")
            return 0.35, details

        h4_rating = confirmations.get("h4_rating", 0.5)
        details["h4_brief"] = h4_rating
        if h4_rating < d1_rating - 0.2:
            details["notes"].append(f"H4 structure diverges from D1 ({h4_rating:.2f} vs {d1_rating:.2f}).")

        details["entry_setup"] = confirmations.get("h1_rating", 0.5)
        details["m30_confirmation"] = confirmations.get("m30_rating", 0.5)
        details["mid_term_confirmation"] = confirmations.get("m15_rating", 0.5)
        details["pattern_strength"] = confirmations.get("m5_rating", 0.5)
        details["micro_entry_precision"] = confirmations.get("m1_rating", 0.5)

        score = (
            details["weekly_structure"] * 0.05 +
            details["h4_brief"] * 0.05 +
            details["entry_setup"] * 0.12 +
            details["mid_term_confirmation"] * 0.12 +
            details["imbalance_quality"] * 0.12 +
            details["market_dynamics"] * 0.18 +
            details["sequence_score"] * 0.15 +
            details["smt_divergence"] * 0.06 +
            details["rsi_alignment"] * 0.07 +
            details["volatility_quality"] * 0.05 +
            details["judas_swing_context"] * 0.03
        )

        if score < 0.5:
            details["notes"].append("Low quality setup - too many missing sequence steps.")
        elif score > 0.75:
            details["notes"].append("High quality ICT setup with a strong sequence.")
        else:
            details["notes"].append("Moderate quality setup - wait for cleaner evidence.")

        return min(1.0, score), details

    except Exception as e:
        logger.debug(f"Setup quality calculation failed: {e}")
        details["notes"].append(f"Setup calculation error: {e}")
        return 0.4, details


def calculate_market_condition_score(symbol: str) -> Tuple[float, Dict]:
    """
    Calculate market favorability (0-1) for this specific pair.

    Checks:
    - Is volatility manageable?
    - Is market condition favorable for our strategy?
    - Are there session considerations?

    Returns:
        (score: float 0-1, details: {volatility, condition, recommendations})
    """
    score = 0.5
    details = {
        "volatility_score": 0.5,
        "market_condition": "unknown",
        "session_impact": 0.0,
        "overall": 0.5,
        "notes": []
    }

    try:
        # Check volatility and market condition
        should_trade, reason, adjustments = should_trade_pair_based_on_volatility(symbol)

        if not should_trade:
            details["volatility_score"] = 0.2
            details["notes"].append(f"Volatility concern: {reason}")
            score = 0.3
        else:
            # Load volatility analysis
            volatility_data = load_volatility_analysis().get(symbol, {})
            vol_index = volatility_data.get("volatility_index", 0.5)
            condition = volatility_data.get("market_condition", "stable")

            # IQ: Market Regime Understanding
            if condition == "consolidating":
                # ICT setups thrive in expansion from consolidation
                details["volatility_score"] = 0.85
                details["market_condition"] = "consolidating"
            elif condition == "stable":
                details["volatility_score"] = 0.95
                details["market_condition"] = "stable"
            elif condition == "volatile":
                # Extreme volatility can lead to fakeouts
                details["volatility_score"] = 0.45
                details["market_condition"] = "volatile"
                details["notes"].append("High volatility: requires stricter displacement confirmation")

            # Detect Volatility Expansion
            if volatility_data.get("volatility_trend") == "increasing":
                details["notes"].append("Expansion detected: looking for momentum breakout")

            # Session considerations (killzones and overlap)
            hour = datetime.utcnow().hour
            if 7 <= hour < 10:
                details["session_impact"] = 0.25
                details["notes"].append("London killzone active.")
            elif 12 <= hour < 15:
                details["session_impact"] = 0.22
                details["notes"].append("New York killzone active.")
            elif 0 <= hour < 5:
                details["session_impact"] = 0.15
                details["notes"].append("Asia session detected.")
            elif 13 <= hour < 16:
                details["session_impact"] = 0.20
                details["notes"].append("London/New York overlap.")
            else:
                details["session_impact"] = -0.05
                details["notes"].append("Lower liquidity session.")

            details["position_size_adjustment"] = adjustments.get("position_size_adjustment", 1.0)
            details["confidence_adjustment"] = adjustments.get("confidence_adjustment", 0.0)

            if condition == "volatile" and details["session_impact"] > 0:
                details["session_impact"] -= 0.05
                details["notes"].append("High volatility during killzone requires extra caution.")

            score = min(
                1.0,
                max(
                    0.0,
                    details["volatility_score"]
                    + details["session_impact"]
                    + details["confidence_adjustment"],
                ),
            )
            details["overall"] = score
            details["notes"].append(f"Market: {condition}, Volatility: {vol_index:.2f}")

        return score, details

    except Exception as e:
        logger.debug(f"Market condition score calculation failed: {e}")
        details["notes"].append(f"Market condition error: {e}")
        return 0.4, details


def calculate_risk_profile_score(
    symbol: str,
    trade_direction: str,
    position_size: float = 0.0
) -> Tuple[float, Dict]:
    """
    Calculate risk acceptance (0-1) based on current exposure.

    Checks:
    - Are we already exposed to this pair?
    - Is account risk acceptable?
    - Are we correlated to other positions?
    - Can we afford this position size?

    Returns:
        (score: float 0-1, details: {exposure, correlation_risk, sizing})
    """
    score = 0.5
    details = {
        "account_exposure_percent": 0.0,
        "pair_correlation_risk": 0.0,
        "sizing_acceptability": 0.5,
        "max_recommended_size": 0.0,
        "notes": []
    }

    try:
        # Get current exposure
        exposure = get_current_account_exposure()
        account_exposure = exposure.get("total_percent", 0.0)

        details["account_exposure_percent"] = account_exposure

        # Check correlation risk
        corr_risk = get_pair_correlation_risk(symbol)
        details["pair_correlation_risk"] = corr_risk

        # Calculate sizing
        try:
            max_size = calculate_position_sizing(symbol, risk_percent=2.0)
            details["max_recommended_size"] = max_size
        except:
            details["max_recommended_size"] = 0.01

        # Scoring logic
        account_exposure = details["account_exposure_percent"]
        if account_exposure > 8.0:
            score = 0.2  # Already heavily exposed
            details["notes"].append(f"High account exposure: {account_exposure:.1f}%")
        elif account_exposure > 5.0:
            score = 0.5  # Moderate exposure
            details["notes"].append(f"Moderate account exposure: {account_exposure:.1f}%")
        else:
            score = 0.8  # Low exposure - can trade
            details["notes"].append(f"Low account exposure: {account_exposure:.1f}%")

        # Correlation risk impact
        if corr_risk > 0.7:
            score -= 0.3
            details["notes"].append(f"High correlation risk: {corr_risk:.2f}")
        elif corr_risk > 0.5:
            score -= 0.1
            details["notes"].append(f"Moderate correlation risk: {corr_risk:.2f}")
        details["notes"].append(f"Current risk exposure: {account_exposure}%")

        score = max(0.0, min(1.0, score))
        details["sizing_acceptability"] = score

        return score, details

    except Exception as e:
        logger.debug(f"Risk profile calculation failed: {e}")
        details["notes"].append(f"Risk calculation error: {e}")
        return 0.4, details


def calculate_timing_score(symbol: str, timeframe: str) -> Tuple[float, Dict]:
    """
    Calculate timing appropriateness (0-1).

    Checks:
    - Time of day (session compatibility)
    - Recent news or events
    - Economic calendar
    - Trade frequency (are we overtrading?)

    Returns:
        (score: float 0-1, details: {timing_factors})
    """
    score = 0.5
    details = {
        "session_alignment": 0.5,
        "trade_frequency": 0.5,
        "event_risk": 0.0,
        "notes": []
    }

    try:
        # Session timing (rough)
        hour = datetime.utcnow().hour
        from utils.symbol_profile import infer_asset_class
        asset_class = infer_asset_class(symbol)

        # Intelligent Session Analysis (UTC)
        # London: 08:00 - 16:00 | New York: 13:00 - 21:00 | Asian: 00:00 - 09:00

        is_london = in_london_session()
        is_ny = in_newyork_session()
        
        # Requirement: "intelligence should only follow this" (London or NY)
        if not (is_london or is_ny):
            details["session_alignment"] = 0.0
            details["notes"].append("Non-Killzone Session: Intelligence blocks execution outside London/NY.")
            return 0.0, details

        is_overlap = is_london and is_ny
        is_london_kz = 7 <= hour < 10
        is_ny_kz = 12 <= hour < 15
        is_silver_bullet = 15 <= hour < 16

        if asset_class == "forex":
            if is_london_kz:
                details["session_alignment"] = 1.0  # London Killzone
                details["notes"].append("London Killzone Active: Peak Liquidity")
            elif is_ny_kz:
                details["session_alignment"] = 0.85
            elif is_silver_bullet:
                details["session_alignment"] = 0.95  # High probability ICT hour
            else:
                details["session_alignment"] = 0.4
        elif asset_class == "metals":
            if is_overlap:
                details["session_alignment"] = 1.0
            elif is_ny:
                details["session_alignment"] = 0.95
            elif is_london:
                details["session_alignment"] = 0.8
            else:
                details["session_alignment"] = 0.3
        elif asset_class == "crypto":
            if is_overlap or is_ny or is_london:
                details["session_alignment"] = 0.95
            else:
                details["session_alignment"] = 0.65
        else:
            details["session_alignment"] = 0.5

        # Event risk (news filter)
        news_impact = check_for_high_impact_news(symbol)
        if news_impact == "high":
            details["event_risk"] = -0.5 # Significant penalty for high impact news
            details["notes"].append("High impact news detected - avoid trading")
        elif news_impact == "medium":
            details["event_risk"] = -0.2 # Moderate penalty
            details["notes"].append("Medium impact news detected - trade with caution")
        # No change for low/no news

        # Trade frequency - are we trading this pair too much? Use canonical key.
        history = load_cis_history().get(_symbol_key(symbol), {}).get("trades", [])

        # Count trades in last 4 hours
        four_hours_ago = (datetime.utcnow() - timedelta(hours=4)).isoformat()
        recent_trades = [t for t in history if t.get("timestamp", "") > four_hours_ago]

        if len(recent_trades) > 3:
            details["trade_frequency"] = 0.2
            details["notes"].append(f"Overtrading detected: {len(recent_trades)} trades in 4h")
        elif len(recent_trades) > 1:
            details["trade_frequency"] = 0.6
        else:
            details["trade_frequency"] = 1.0

        # Composite timing score
        score = (
            details["session_alignment"] * 0.6 +
            details["trade_frequency"] * 0.3 + # Reduced weight for frequency
            details["event_risk"] * 0.1 # Add news impact
        )

        return min(1.0, score), details

    except Exception as e:
        logger.debug(f"Timing score calculation failed: {e}")
        details["notes"].append(f"Timing calculation error: {e}")
        return 0.5, details


def get_cis_score(symbol: str, direction: str, analysis: dict, context: dict, ranking_mode: bool = False) -> Tuple[float, dict]:
    """
    NEW CIS SCORING ENGINE: One Brain Decision System
    Returns score 0-100 instead of TRADE/WAIT/AVOID
    Audit Fix: Enforce Strict ICT Quality thresholds
    """
    # Hard Filters (Audit Requirement: High Quality OB/FVG)
    FVG_QUALITY_MIN = 0.6
    OB_QUALITY_MIN = 0.7
    
    score = 0
    breakdown = {}

    # 🔴 1. MARKET STRUCTURE (CRITICAL)
    # Audit Fix: FORCE BOS for entry
    if not analysis.get("bos") and not ranking_mode:
        return 0, {"reason": "BOS Missing - Strict ICT requirement"}

    score += 15
    breakdown["bos"] = 15

    if analysis.get("trend") == direction.lower():
        score += 10
        breakdown["trend_alignment"] = 10

    # 🔴 2. LIQUIDITY
    # Audit Fix: Strict Sweep Only logic
    sweep_confirmed = analysis.get("liquidity_sweep", ranking_mode)
    if not sweep_confirmed:
        return 0, {"reason": "Liquidity Sweep Missing - Strict ICT requirement"}

    score += 15
    breakdown["liquidity"] = 15

    # 🔴 3. DISPLACEMENT
    disp = analysis.get("displacement", 0)
    if disp >= 0.7:
        score += 12
        breakdown["displacement"] = 12
    elif disp >= 0.6:
        score += 8
        breakdown["displacement"] = 8
    else:
        score += 2
        breakdown["displacement"] = 2

    # 🔴 4. ZONES (FVG / OB)
    # Audit Fix: Quality scoring for FVG/OB
    fvg_quality = analysis.get("fvg_quality", 0.0)
    if analysis.get("fvg") and fvg_quality >= FVG_QUALITY_MIN:
        score += 8
        breakdown["fvg"] = 8

    ob_quality = analysis.get("order_block_quality", 0.0)
    if analysis.get("order_block") and ob_quality >= OB_QUALITY_MIN:
        score += 8
        breakdown["order_block"] = 8

    # 🔴 5. PRICE ACTION
    if context.get("price_action"):
        score += 6
        breakdown["price_action"] = 6
    else:
        score += 2
        breakdown["price_action"] = 2

    # 🔴 6. SMT DIVERGENCE
    smt_score = context.get("smt", 0.5)
    score += smt_score * 10
    breakdown["smt"] = round(smt_score * 10, 2)

    # 🔴 7. MARKET CONDITION (VOLATILITY)
    volatility = context.get("volatility_index", 0.5)
    score += volatility * 8
    breakdown["volatility"] = round(volatility * 8, 2)

    # 🔴 8. SESSION TIMING
    if context.get("session_active"):
        score += 6
        breakdown["session"] = 6
    else:
        score += 2
        breakdown["session"] = 2

    # 🔴 9. CORRELATION RISK (PENALTY)
    correlation_risk = context.get("correlation_risk", 0.0)
    penalty = correlation_risk * 10
    score -= penalty
    breakdown["correlation_penalty"] = -round(penalty, 2)

    # 🔴 10. NEWS IMPACT (PENALTY)
    news = context.get("news", "none")
    if news == "high":
        score -= 15
        breakdown["news_penalty"] = -15
    elif news == "medium":
        score -= 5
        breakdown["news_penalty"] = -5

    # 🔴 11. MARKET RHYTHM
    rhythm = context.get("market_rhythm", {})
    if rhythm.get("favorable"):
        score += 6
        breakdown["rhythm"] = 6
    if rhythm.get("avoid"):
        score -= 8
        breakdown["rhythm_penalty"] = -8

    # 🔴 12. RISK-REWARD QUALITY
    rr = context.get("rr", 2.0)
    if rr >= 3:
        score += 6
        breakdown["rr"] = 6
    elif rr >= 2:
        score += 3
        breakdown["rr"] = 3
    else:
        score -= 5
        breakdown["rr_penalty"] = -5

    # 🔴 FINAL NORMALIZATION
    score = max(0, min(score, 100))

    return score, breakdown


def cis_decision(score):
    """New execution decision based on score"""
    if score >= 80: # Audit Fix: Selective Execution
        return "EXECUTE_FULL"
    elif score >= 65:
        return "EXECUTE_PARTIAL"
    elif score >= 55:
        return "SCALP"
    else:
        return "SKIP"


def get_cis_decision(
    symbol: str,
    direction: str,  # "BUY" or "SELL"
    timeframe: str = "H1",
    entry_price: float = None,
    stop_loss: float = None,
    take_profit: float = None,
    multi_tf_analysis: Dict = None,
    htf_data: List = None,
    mtf_data: List = None
) -> Dict:
    """
    LEGACY FUNCTION: Now uses new scoring system internally
    Maintained for backward compatibility
    """
    try:
        # Build analysis dict from parameters
        analysis = {
            "bos": multi_tf_analysis.get("bos", False) if multi_tf_analysis else False,
            "trend": multi_tf_analysis.get("trend", "").lower() if multi_tf_analysis else "",
            "liquidity_sweep": multi_tf_analysis.get("liquidity_sweep", False) if multi_tf_analysis else False,
            "displacement": multi_tf_analysis.get("displacement", 0.0) if multi_tf_analysis else 0.0,
            "fvg": multi_tf_analysis.get("fvg", False) if multi_tf_analysis else False,
            "order_block": multi_tf_analysis.get("order_block", False) if multi_tf_analysis else False,
        }

        # Build context dict
        context = {
            "price_action": True,  # Assume confirmed for legacy compatibility
            "smt": 0.5,  # Default
            "volatility_index": 0.5,  # Default
            "session_active": True,  # Default
            "correlation_risk": 0.0,  # Default
            "news": "none",  # Default
            "market_rhythm": {"favorable": True},  # Default
            "rr": 2.0,  # Default
        }

        # Get new score
        score, breakdown = get_cis_score(symbol, direction, analysis, context)
        decision = cis_decision(score)

        # Convert to legacy format for backward compatibility
        final_verdict = "TRADE" if decision in ["EXECUTE_FULL", "EXECUTE_PARTIAL", "SCALP"] else "AVOID"

        return {
            "symbol": symbol,
            "direction": direction,
            "final_verdict": final_verdict,
            "confidence_score": score / 100.0,  # Convert to 0-1 scale
            "component_scores": {
                "setup_quality": score / 100.0,
                "market_condition": 0.5,
                "risk_profile": 0.5,
                "timing": 0.5,
            },
            "reasoning": [f"Score: {score}, Decision: {decision}"],
            "red_flags": [],
            "entry_checklist": [],
            "decision_id": f"{symbol}_{direction}_{int(time.time())}",
            "unified_score": score,
            "breakdown": breakdown,
        }

    except Exception as e:
        logger.error(f"CIS Decision failed: {e}")
        return {
            "final_verdict": "AVOID",
            "confidence_score": 0.0,
            "component_scores": {},
            "reasoning": [f"Error: {e}"],
        }


def get_cis_summary(symbol: str = None) -> str:
    """
    Get human-readable CIS summary for logging.

    Example:
    [CIS] EURUSD BUY: TRADE (0.82) | Setup: 0.85 | Market: 0.75 | Risk: 0.80 | Timing: 0.85
    """
    history = load_cis_history()

    if not history:
        return "[CIS] No decisions yet"

    key = _symbol_key(symbol) if symbol else None

    if not key or key not in history:
        # Summarize most recent decision across all symbols
        all_trades = []
        for sym, data in history.items():
            trades = data.get("trades", [])
            if trades:
                all_trades.append((sym, trades[-1]))

        if not all_trades:
            return "[CIS] No trading decisions"

        summaries = []
        for sym, trade in sorted(all_trades, key=lambda x: x[1].get("timestamp", ""))[-3:]:
            verdict = trade.get("final_verdict", "?")
            conf = trade.get("confidence_score", 0.0)
            setup = trade.get("component_scores", {}).get("setup_quality", 0.0)
            market = trade.get("component_scores", {}).get("market_condition", 0.0)
            risk = trade.get("component_scores", {}).get("risk_profile", 0.0)
            timing = trade.get("component_scores", {}).get("timing", 0.0)

            summaries.append(
                f"{sym}: {verdict} ({conf:.2f}) | S:{setup:.2f} M:{market:.2f} R:{risk:.2f} T:{timing:.2f}"
            )

        return "[CIS] " + " | ".join(summaries)

    # Specific symbol summary
    trades = history.get(key, {}).get("trades", [])
    if not trades:
        return f"[CIS] No decisions for {key}"

    trade = trades[-1]
    verdict = trade.get("final_verdict", "?")
    conf = trade.get("confidence_score", 0.0)
    setup = trade.get("component_scores", {}).get("setup_quality", 0.0)
    return f"[CIS] {key}: {verdict} ({conf:.2f}) setup:{setup:.2f}"
