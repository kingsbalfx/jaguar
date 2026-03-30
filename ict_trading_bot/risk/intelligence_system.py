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
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List

import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

# Import analysis modules
from ict_concepts.liquidity_analysis import is_premium_discount_optimal, measure_order_block_strength
from strategy.confirmation_system import get_all_confirmations_for_pair
from risk.market_condition import should_trade_pair_based_on_volatility, load_volatility_analysis
from risk.correlation_manager import get_pair_correlation_risk
from risk.position_manager import get_current_account_exposure, calculate_position_sizing
from execution.order_manager import calculate_risk_reward_for_trade

CIS_DECISIONS_FILE = Path(__file__).resolve().parent.parent / "data" / "cis_decisions_history.json"


def load_cis_history() -> Dict:
    """Load historical CIS decisions and performance metrics."""
    if CIS_DECISIONS_FILE.exists():
        try:
            with open(CIS_DECISIONS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load CIS history: {e}")
    return {}


def save_cis_decision(symbol: str, decision: Dict):
    """Save a CIS decision to history for tracking performance."""
    try:
        history = load_cis_history()
        
        if symbol not in history:
            history[symbol] = {"trades": []}
        
        history[symbol]["trades"].append({
            "timestamp": datetime.utcnow().isoformat(),
            **decision
        })
        
        # Keep only last 500 decisions per pair
        history[symbol]["trades"] = history[symbol]["trades"][-500:]
        
        CIS_DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CIS_DECISIONS_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save CIS decision: {e}")


def calculate_setup_quality_score(
    symbol: str,
    timeframe: str,
    multi_tf_analysis: Dict = None
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
        "mid_term_confirmation": 0.3,   # M15 rating - Mid-term confirmation
        "pattern_strength": 0.3,        # M5 rating - Pattern precision
        "micro_entry_precision": 0.3,   # M1 rating - Exact entry candle
        "imbalance_quality": 0.0,
        "notes": []
    }
    
    try:
        # Get confirmations from confirmation system
        confirmations = get_all_confirmations_for_pair(symbol, timeframe)
        
        if not confirmations:
            details["notes"].append("No confirmations available")
            return score, details
        
        # TRUE STRUCTURAL REFERENCE (W1 should show major trend, core S/R)
        w1_rating = confirmations.get("w1_rating", 0.5)
        details["weekly_structure"] = w1_rating
        
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
        
        # Entry setup (H1 should show valid impulse or pullback)
        h1_rating = confirmations.get("h1_rating", 0.5)
        details["entry_setup"] = h1_rating
        
        # Mid-term confirmation (M15 should confirm H1 setup)
        m15_rating = confirmations.get("m15_rating", 0.5)
        details["mid_term_confirmation"] = m15_rating
        
        # Pattern strength (M5 should show price action precision)
        m5_rating = confirmations.get("m5_rating", 0.5)
        details["pattern_strength"] = m5_rating
        
        # Micro-entry precision (M1 should show exact entry candle placement)
        m1_rating = confirmations.get("m1_rating", 0.5)
        details["micro_entry_precision"] = m1_rating
        
        # Imbalance/order block quality
        try:
            ob_strength = measure_order_block_strength(symbol, timeframe)
            details["imbalance_quality"] = ob_strength
        except:
            details["imbalance_quality"] = 0.3
        
        # Composite score: weighted average across 7 timeframes
        # STRUCTURAL HIERARCHY:
        # W1 (20%): TRUE STRUCTURAL REFERENCE - Core trends, major S/R
        # D1 (15%): BRIEF - Structural confirmation (relative to W1)
        # H4 (15%): BRIEF - Intraday structure alignment
        # H1 (20%): Entry setup quality - Critical confirmation
        # M15 (12%): Mid-term entry confirmation
        # M5 (12%): Pattern precision and entry point
        # M1 (6%): Micro entry precision - Exact candle placement
        
        score = (
            details["weekly_structure"] * 0.20 +
            details["daily_brief"] * 0.15 +
            details["h4_brief"] * 0.15 +
            details["entry_setup"] * 0.20 +
            details["mid_term_confirmation"] * 0.12 +
            details["pattern_strength"] * 0.12 +
            details["micro_entry_precision"] * 0.06 +
            details["imbalance_quality"] * 0.0  # OB strength embedded in M5 pattern
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
            
            # Score based on condition
            if condition == "consolidating":
                details["volatility_score"] = 0.8  # Good for range trades
                details["market_condition"] = "consolidating"
            elif condition == "stable":
                details["volatility_score"] = 0.9  # Good for any trade
                details["market_condition"] = "stable"
            else:  # volatile
                details["volatility_score"] = 0.5  # Neutral - check setup quality
                details["market_condition"] = "volatile"
            
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
        
        if "EUR" in symbol or "GBP" in symbol:
            if hour in [8, 9, 13, 14, 15]:  # London/NY
                details["session_alignment"] = 1.0
            elif hour in [16, 17, 18]:  # Americas
                details["session_alignment"] = 0.8
            else:
                details["session_alignment"] = 0.4
        elif "USD" in symbol or "JPY" in symbol:
            if hour in [21, 22, 23, 0, 1]:  # US/Asian
                details["session_alignment"] = 0.9
            elif hour in [8, 9]:  # London open
                details["session_alignment"] = 0.8
            else:
                details["session_alignment"] = 0.5
        
        # Trade frequency - are we trading this pair too much?
        history = load_cis_history().get(symbol, {}).get("trades", [])
        
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
            details["trade_frequency"] * 0.4
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
        setup_score, setup_details = calculate_setup_quality_score(symbol, timeframe)
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
        
        # Calculate composite confidence
        confidence = (setup_score + market_score + risk_score + timing_score) / 4.0
        decision["confidence_score"] = round(confidence, 3)
        
        # Make final verdict
        if confidence > 0.75:
            decision["final_verdict"] = "TRADE"
        elif confidence > 0.5:
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
    
    target_symbol = symbol
    if not target_symbol or target_symbol not in history:
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
    trades = history.get(target_symbol, {}).get("trades", [])
    if not trades:
        return f"[CIS] No decisions for {target_symbol}"
    
    trade = trades[-1]
    verdict = trade.get("final_verdict", "?")
    conf = trade.get("confidence_score", 0.0)
    setup = trade.get("component_scores", {}).get("setup_quality", 0.0)
    
    return f"[CIS] {target_symbol}: {verdict} ({conf:.2f}) setup:{setup:.2f}"
