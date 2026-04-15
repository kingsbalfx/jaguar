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
from risk.intelligent_execution import get_learned_threshold_adjustment
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

    sequence["liquidity_sweep_confirmed"] = bool(
        liquidity_sweep_or_swing(entry_price or 0.0, analysis, direction_label).get("confirmed")
    )
    sequence["steps"].append(
        f"Liquidity Sweep: {'PASS' if sequence['liquidity_sweep_confirmed'] else 'FAIL'}"
    )

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
        except Exception:
            pass

        imbalance_score = 0.3
        if fvgs:
            imbalance_score = 0.65
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
    MAIN CIS FUNCTION: Make pre-trade decision.

    Returns comprehensive decision package:
    {
        "symbol": "EURUSD",
        "direction": "BUY",
        "final_verdict": "TRADE",  # or "WAIT" or "AVOID"
        "confidence_score": 0.82,
        "position_size": 0.01,
        "stop_loss_size": 50,  # pips

        "component_scores": {
            "setup_quality": 0.85,
            "market_condition": 0.75,
            "risk_profile": 0.80,
            "timing": 0.85,
        },

        "reasoning": [
            "Strong multi-timeframe alignment (0.85)",
            "Stable market conditions, good for this strategy",
            "Account exposure acceptable (2.3%)",
            "Perfect trading session for EURUSD",
        ],

        "red_flags": [],
        "entry_checklist": [check1, check2, ...],
        "decision_id": "20260329_143000_EURUSD_BUY",
    }
    """
    decision = {
        "symbol": symbol,
        "direction": direction,
        "timeframe": timeframe,
        "timestamp": datetime.utcnow().isoformat(),
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,

        "final_verdict": "ANALYZE",
        "confidence_score": 0.0,
        "position_size": 0.0,
        "stop_loss_size": 0,

        "component_scores": {},
        "reasoning": [],
        "red_flags": [],
        "entry_checklist": [],
        "history_count": 0
    }

    try:
        # 1. Setup Quality
        setup_score, setup_details = calculate_setup_quality_score(
            symbol,
            timeframe,
            direction=direction,
            multi_tf_analysis=multi_tf_analysis,
            entry_price=entry_price,
            htf_data=htf_data,
            mtf_data=mtf_data
        )
        
        # Strict Liquidity Block
        if not setup_details.get("liquidity_sweep"):
            decision["final_verdict"] = "AVOID"
            decision["reasoning"].append("CRITICAL BLOCK: Setup requires a confirmed liquidity sweep.")
            return decision

        sequence_data = setup_details.get("sequence_data", {})
        if not sequence_data.get("standalone_approval"):
            decision["final_verdict"] = "AVOID"
            decision["ict_sequence"] = sequence_data
            decision["reasoning"].append("CRITICAL BLOCK: Full ICT sequence is incomplete.")
            return decision

        decision["component_scores"]["setup_quality"] = round(setup_score, 3)
        decision["market_mode"] = setup_details.get("market_mode", "UNKNOWN")
        decision["ict_sequence"] = sequence_data
        if decision["ict_sequence"].get("standalone_approval"):
            decision["reasoning"].append("ICT sequence fully satisfied for the proposed setup.")
        decision["reasoning"].extend([f"Setup: {note}" for note in setup_details.get("notes", [])])

        # 2. Market Condition
        market_score, market_details = calculate_market_condition_score(symbol)
        decision["component_scores"]["market_condition"] = round(market_score, 3)
        decision["reasoning"].extend([f"Market: {note}" for note in market_details.get("notes", [])])

        # 3. Risk Profile
        risk_score, risk_details = calculate_risk_profile_score(symbol, direction)
        decision["component_scores"]["risk_profile"] = round(risk_score, 3)
        decision["reasoning"].extend([f"Risk: {note}" for note in risk_details.get("notes", [])])

        # 4. Timing
        timing_score, timing_details = calculate_timing_score(symbol, timeframe)
        decision["component_scores"]["timing"] = round(timing_score, 3)
        decision["reasoning"].extend([f"Timing: {note}" for note in timing_details.get("notes", [])])

        # LOGICAL PRECISION: Setup and Risk anchored logic
        # Weights: Setup (45%), Risk (25%), Market (15%), Timing (15%)
        confidence = (setup_score * 0.45) + (risk_score * 0.25) + (market_score * 0.15) + (timing_score * 0.15)
        decision["confidence_score"] = round(confidence, 3)

        # Load trade history count for 100+ trade requirement
        history = load_cis_history().get(_symbol_key(symbol), {}).get("trades", [])
        decision["history_count"] = len(history)

        # Apply learned threshold adjustments so the system improves over time
        threshold_adjustment = get_learned_threshold_adjustment(symbol)
        decision["learning_adjustment"] = round(threshold_adjustment, 3)
        if threshold_adjustment != 0:
            decision["reasoning"].append(f"Learning adaptation adjusts trade threshold by {threshold_adjustment:+.0%}")

        trade_threshold = min(0.99, max(0.65, 0.75 + threshold_adjustment))
        wait_threshold = min(0.99, max(0.55, 0.62 + threshold_adjustment))

        # Strong symbols should still benefit from high edge; weak symbols get stricter gating
        if confidence > trade_threshold:
            decision["final_verdict"] = "TRADE"
        elif confidence > wait_threshold:
            decision["final_verdict"] = "WAIT"
        else:
            decision["final_verdict"] = "AVOID"

        # Intelligence should prefer London/NewYork hours unless override is enabled.
        if not (in_london_session() or in_newyork_session()):
            if decision["final_verdict"] == "TRADE":
                decision["final_verdict"] = "AVOID"
                decision["reasoning"].append("BLOCK: Intelligence system only executes during London/NewYork sessions.")
                decision["confidence_score"] = 0.0

        # Red flags
        if setup_score < 0.5:
            decision["red_flags"].append("Low setup quality - multiple confirmations weak")
        if market_score < 0.4:
            decision["red_flags"].append("Unfavorable market conditions")
        if risk_score < 0.4:
            decision["red_flags"].append("Account risk too high")
        if timing_score < 0.4:
            decision["red_flags"].append("Poor trade timing")

        # Positioning
        if decision["final_verdict"] in ("TRADE", "WAIT"):
            try:
                position_size = calculate_position_sizing(symbol, risk_percent=2.0)
                if not position_size or position_size <= 0:
                    position_size = 0.01
                if decision["final_verdict"] == "WAIT":
                    position_size = max(0.01, position_size * 0.70)
                decision["position_size"] = round(position_size, 2)
            except Exception:
                decision["position_size"] = 0.01

            if entry_price and stop_loss:
                decision["stop_loss_size"] = abs(entry_price - stop_loss) * 10000  # in pips

        # Entry checklist
        decision["entry_checklist"] = [
            f"Setup Quality: {'PASS' if setup_score > 0.6 else 'FAIL'} ({setup_score:.2f})",
            f"Market Condition: {'PASS' if market_score > 0.5 else 'WAIT'} ({market_score:.2f})",
            f"Risk Profile: {'PASS' if risk_score > 0.5 else 'FAIL'} ({risk_score:.2f})",
            f"Timing: {'PASS' if timing_score > 0.5 else 'SUBOPTIMAL'} ({timing_score:.2f})",
            f"Overall: {decision['final_verdict']} ({confidence:.2f})",
        ]

        # Save decision
        save_cis_decision(symbol, decision)

        return decision

    except Exception as e:
        logger.error(f"CIS decision failed for {symbol}: {e}")
        decision["final_verdict"] = "ERROR"
        decision["reasoning"].append(f"Decision system error: {e}")
        return decision


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
