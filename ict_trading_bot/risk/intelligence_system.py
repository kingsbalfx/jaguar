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
- Conservative: Require multiple confirmations
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
from execution.order_manager import calculate_risk_reward_for_trade
from strategy.pre_trade_analysis import analyze_market_top_down
from strategy.setup_confirmations import bos_setup, liquidity_sweep_or_swing, price_action_setup
from utils.symbol_profile import canonical_symbol

CIS_DECISIONS_FILE = Path(__file__).resolve().parent.parent / "data" / "cis_decisions_history.json"

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


def calculate_setup_quality_score(
    symbol: str,
    timeframe: str,
    multi_tf_analysis: Dict = None,
    entry_price: float = 0.0
) -> Tuple[float, Dict]:
    """
    Calculate setup quality (0-1) based on technical analysis across 7 timeframes.

    TIMEFRAME HIERARCHY:
    - W1 (Weekly): TRUE STRUCTURAL REFERENCE - Major trend, core S/R levels
    - D1 (Daily): BRIEF - Confirmation of weekly structure
    - H4 (4-Hour): BRIEF - Intraday structure alignment
    - H1 (Hourly): Entry setup valid? (impulse/pullback pattern)
    - M15 (15-min): Setup confirmation? (mid-term confirmation)
    - M5 (5-min): Exact entry point? (precise timing)
    - M1 (1-min): Micro-entry precision? (exact candle placement)

    Returns:
        (score: float 0-1, details: {breakdown of all 7 timeframe components})
    """
    score = 0.5
    details = {
        "weekly_structure": 0.3,       # W1 rating - TRUE STRUCTURAL REFERENCE
        "daily_brief": 0.3,             # D1 rating - BRIEF, structural confirmation
        "h4_brief": 0.3,                # H4 rating - BRIEF, intraday structure
        "entry_setup": 0.3,             # H1 rating - Entry setup quality
        "m30_confirmation": 0.3,         # M30 rating - Analysis confirmation
        "mid_term_confirmation": 0.3,   # M15 rating - Mid-term confirmation
        "pattern_strength": 0.3,        # M5 rating - Pattern precision
        "micro_entry_precision": 0.3,   # M1 rating - Exact entry candle
        "imbalance_quality": 0.0,
        "notes": []
    }

    try:
        # Use pre_trade_analysis to get technical context
        analysis = multi_tf_analysis or analyze_market_top_down(symbol, entry_price or 0.0)
        if not analysis:
            details["notes"].append("Market analysis failed")
            return score, details

        # Get confirmations from confirmation system using the same timeframe snapshot.
        confirmations = get_all_confirmations_for_pair(symbol, timeframe, analysis=analysis)
        if not confirmations:
            details["notes"].append("No confirmations available")

        # Extract trends for structural confirmation
        htf_trend = analysis.get("overall_trend", "unknown")
        mtf_data = analysis.get("MTF", {})
        ltf_data = analysis.get("LTF", {})
        execution_data = analysis.get("EXECUTION", {})

        # LOGICAL GATE: Market must follow topdown analysis and major trend
        if htf_trend == "unknown" or htf_trend == "range":
            details["notes"].append("Logic Error: Setup lacks macro directional established trend.")
            return 0.1, details

        # Map available data to structural hierarchy (Weekly/Daily/H4)
        details["weekly_structure"] = 0.8 if htf_trend in ("bullish", "bearish") else 0.5
        details["daily_brief"] = 0.7 if mtf_data.get("trend") == htf_trend else 0.4
        details["h4_brief"] = 0.7 if ltf_data.get("trend") == htf_trend else 0.4

        # TRUE STRUCTURAL REFERENCE (daily brief is the macro proxy here)
        w1_rating = confirmations.get("w1_rating", confirmations.get("d1_rating", 0.5))
        details["weekly_structure"] = w1_rating
        # Use setup confirmations for logic-based scoring
        bos = bos_setup(analysis, htf_trend)
        liq = liquidity_sweep_or_swing(analysis.get("price", 0), analysis, "buy" if htf_trend == "bullish" else "sell")
        pa = price_action_setup(analysis, htf_trend)

        if bos["confirmed"]: details["notes"].append("BOS alignment detected")
        if liq["confirmed"]: details["notes"].append("Liquidity sweep confirmed")
        if pa["confirmed"]: details["notes"].append("Bullish/Bearish price action found")

        # Confirmation Logic Check: Require 2+ confirmations beyond macro structure
        # Ratings above 0.6 are considered "passed"
        valid_ratings = [v for k, v in confirmations.items() if k.endswith("_rating") and isinstance(v, (int, float)) and v > 0.6]
        if len(valid_ratings) < 2:
            details["notes"].append(f"Logic Rejected: Insufficient confirmations (Found {len(valid_ratings)}/2 required)")
            return 0.2, details

        # Check for imbalance (FVG) quality and optimal entry zone
        fvgs = execution_data.get("fvgs") or ltf_data.get("fvgs", [])
        fib_levels = analysis.get("MTF", {}).get("fib", {}) # Assuming MTF fib is relevant for optimal zone

        imbalance_score_base = 0.3 # Base score if no FVG
        if fvgs:
            imbalance_score_base = 0.6 # FVG present
            # Check if price is in optimal premium/discount zone
            if is_premium_discount_optimal(entry_price, fib_levels, htf_trend):
                imbalance_score_base = 0.8 # FVG present AND optimal zone

        # Measure Order Block strength
        ob_strength = 0.3
        try:
            ob_strength = measure_order_block_strength(symbol, timeframe)
        except Exception:
            pass

        # Combine FVG presence, optimal zone, and OB strength
        details["imbalance_quality"] = (imbalance_score_base * 0.6) + (ob_strength * 0.4)
        if details["imbalance_quality"] > 0.7:
            details["notes"].append("Optimal entry zone (FVG + Premium/Discount) confirmed")
        elif details["imbalance_quality"] > 0.5:
            details["notes"].append("FVG present, but not perfectly optimal zone")
        else:
            details["notes"].append("No clear FVG or optimal entry zone")

        # BRIEF: Daily structural confirmation relative to Weekly
        d1_rating = confirmations.get("d1_rating", 0.5)
        details["daily_brief"] = d1_rating
        if d1_rating < w1_rating - 0.2:
            details["notes"].append(f"D1 brief: Diverges from W1 structure ({d1_rating:.2f} vs {w1_rating:.2f})")

        # BRIEF: 4-hour intraday structure alignment
        h4_rating = confirmations.get("h4_rating", 0.5)
        details["h4_brief"] = h4_rating
        if h4_rating < d1_rating - 0.2:
            details["notes"].append(f"H4 brief: Diverges from D1 structure ({h4_rating:.2f} vs {d1_rating:.2f})")

        # Update entry setup and confirmation details based on confirmations
        details["entry_setup"] = confirmations.get("h1_rating", 0.5) # H1 entry setup quality
        details["m30_confirmation"] = confirmations.get("m30_rating", 0.5) # M30 analysis confirmation
        details["mid_term_confirmation"] = confirmations.get("m15_rating", 0.5) # M15 confirmation
        details["pattern_strength"] = confirmations.get("m5_rating", 0.5) # M5 pattern precision
        details["micro_entry_precision"] = confirmations.get("m1_rating", 0.5) # M1 micro entry


        # Composite score: Weighted alignment between structural hierarchy and analytical confirmation.
        # This ensures the confirmation score is properly weighted for alternative execution paths.
        # Daily/H4 are brief context. H1/M30/M15 carry analysis. M5 is execution confirmation.

        score = (
            details["daily_brief"] * 0.10 +
            details["h4_brief"] * 0.10 +
            details["entry_setup"] * 0.20 +            # H1 analysis
            details["m30_confirmation"] * 0.20 +       # M30 analysis
            details["mid_term_confirmation"] * 0.25 +  # M15 analysis
            details["pattern_strength"] * 0.10 +       # M5 execution confirmation
            details["imbalance_quality"] * 0.05
        )

        if score < 0.5:
            details["notes"].append("Low quality setup - multiple confirmations missing")
        elif score > 0.75:
            details["notes"].append("High quality setup - strong multi-timeframe alignment")
        else:
            details["notes"].append("Moderate setup quality - proceed with caution")

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

            # Session considerations (rough)
            hour = datetime.utcnow().hour
            if hour in [8, 9, 13, 14, 15]:  # London/NY overlap
                details["session_impact"] = 0.2  # Positive
            elif hour in [0, 1, 2]:  # Asian session
                details["session_impact"] = 0.0  # Neutral
            else:
                details["session_impact"] = -0.1  # Slow hours

            score = min(1.0, details["volatility_score"] + details["session_impact"])
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

        is_london = 8 <= hour < 16
        is_ny = 13 <= hour < 21
        is_asian = (0 <= hour < 9) or (hour >= 23)
        is_overlap = 13 <= hour < 16

        if asset_class == "forex":
            if is_overlap:
                details["session_alignment"] = 1.0  # Gold standard for liquidity
            elif is_london:
                details["session_alignment"] = 0.9
            elif is_ny:
                details["session_alignment"] = 0.85
            elif is_asian:
                # Trade majors in Asia? Lower IQ timing
                details["session_alignment"] = 0.65
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
                details["session_alignment"] = 0.3  # Metals dead in Asia
        elif asset_class == "crypto":
            # Crypto is 24/7, but NY/London volume is higher for quality
            if is_overlap or is_ny or is_london:
                details["session_alignment"] = 0.95
            else:
                details["session_alignment"] = 0.85 # Stronger weight for Asia than FX
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
    }

    try:
        # 1. Setup Quality
        setup_score, setup_details = calculate_setup_quality_score(
            symbol,
            timeframe,
            multi_tf_analysis=multi_tf_analysis,
            entry_price=entry_price,
        )
        decision["component_scores"]["setup_quality"] = round(setup_score, 3)
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

        # Make final verdict
        if confidence > 0.75:
            decision["final_verdict"] = "TRADE"
        elif confidence > 0.62: # Raised "Wait" threshold to be more selective
            decision["final_verdict"] = "WAIT"
        else:
            decision["final_verdict"] = "AVOID"

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
        if decision["final_verdict"] == "TRADE":
            try:
                decision["position_size"] = calculate_position_sizing(symbol, risk_percent=2.0)
            except:
                decision["position_size"] = 0.01

            decision["position_size"] = 0.01 # Fallback position size
            # Stop loss sizing
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
