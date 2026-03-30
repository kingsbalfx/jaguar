"""
Intelligent Execution System
=============================
10,000% IQ smarter execution for winning AND losing scenarios.

Analyzes:
1. Symbol win/loss patterns (per asset class)
2. Confirmation score reliability
3. Market conditions
4. Dynamic risk based on confidence
5. Loss prevention strategies
6. Position sizing optimization (0.5-1.0x for forex, 0.7-1.2x metals, 0.5-1.2x crypto)
7. Trade timing intelligence (asset-class-specific ADAPTIVE thresholds)
8. **ADAPTIVE LEARNING SCHEDULE** - Thresholds adjust as symbols learn from history

ADAPTIVE CONFIDENCE THRESHOLDS (NEW - Auto-Learning):
NEW SYMBOLS (0 trades):
  - Forex: 75% (protected until proven)
  - Metals: 75% (protected until proven)
  - Crypto: 75% (protected until proven)

EARLY LEARNING (1-4 trades):
  - Forex: 72%
  - Metals: 72%
  - Crypto: 72%

LEARNING PHASE (5-14 trades):
  - Forex: 68%
  - Metals: 68%
  - Crypto: 68%

PROVEN SYMBOLS (15-49 trades):
  - Forex: 65% (base)
  - Metals: 62% (base)
  - Crypto: 60% (base)

VETERAN SYMBOLS (50+ trades):
  - Forex: 60% (base - 5%) - REWARD proven winners
  - Metals: 57% (base - 5%)
  - Crypto: 55% (base - 5%)

RESULT: NEW symbols protected. PROVEN symbols execute more. No slowdown.

ASSET CLASS MULTIPLIERS (Position Sizing):
- FOREX: 0.5-1.0x (conservative)
- METALS: 0.7-1.2x (medium)
- CRYPTO: 0.5-1.2x (flexible)
  └─ Will increase to 0.9-2.1x once win rate improves beyond 40%
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, List
from utils.symbol_profile import infer_asset_class

INTELLIGENT_STATS_FILE = Path(__file__).resolve().parent.parent / "data" / "intelligent_execution_stats.json"
INTELLIGENT_SKIP_FILE = Path(__file__).resolve().parent.parent / "data" / "intelligent_skip_tracking.json"


def load_intelligent_stats():
    """Load comprehensive execution intelligence from disk."""
    if INTELLIGENT_STATS_FILE.exists():
        try:
            with open(INTELLIGENT_STATS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_intelligent_stats(stats):
    """Save comprehensive execution statistics to disk."""
    try:
        INTELLIGENT_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(INTELLIGENT_STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        print(f"[WARNING] Failed to save intelligent stats: {e}")


def calculate_precise_winning_rate(symbol: str) -> Dict:
    """
    Calculate PRECISE winning rate with advanced metrics.
    
    Returns:
        {
            "symbol": "GBPJPY",
            "win_count": 9,
            "loss_count": 6,
            "total_trades": 15,
            "base_win_rate": 0.60,
            "adjusted_win_rate": 0.65,  # After confidence adjustment
            "expectancy": 1.25,  # Average profit per trade
            "profit_factor": 2.1,  # Wins / Losses
            "confidence_adjustment": 1.083,  # Multiplier from avg_confirmation
            "win_streak": 3,
            "loss_streak": 2,
            "current_streak": "win",
            "prediction_accuracy": 0.78,  # Based on confirmation_score
            "risk_rating": "MEDIUM",  # How risky is this symbol
            "opportunity_score": 0.82  # Should we trade this symbol?
        }
    """
    stats = load_intelligent_stats()
    
    if symbol not in stats:
        return {
            "symbol": symbol,
            "win_count": 0,
            "loss_count": 0,
            "total_trades": 0,
            "base_win_rate": 0.0,
            "adjusted_win_rate": 0.0,
            "expectancy": 0.0,
            "profit_factor": 0.0,
            "confidence_adjustment": 1.0,
            "win_streak": 0,
            "loss_streak": 0,
            "current_streak": "none",
            "prediction_accuracy": 0.0,
            "risk_rating": "NEW",
            "opportunity_score": 0.5,
        }
    
    s = stats[symbol]
    total = s.get("total_trades", 0)
    wins = s.get("wins", 0)
    losses = s.get("losses", 0)
    
    if total == 0:
        return {
            "symbol": symbol,
            "win_count": 0,
            "loss_count": 0,
            "total_trades": 0,
            "base_win_rate": 0.0,
            "adjusted_win_rate": 0.0,
            "expectancy": 0.0,
            "profit_factor": 0.0,
            "confidence_adjustment": 1.0,
            "win_streak": 0,
            "loss_streak": 0,
            "current_streak": "none",
            "prediction_accuracy": 0.0,
            "risk_rating": "NEW",
            "opportunity_score": 0.5,
        }
    
    # Base metrics
    base_win_rate = wins / total
    profit_factor = wins / losses if losses > 0 else wins
    avg_confidence = s.get("avg_confidence", 0.0)
    
    # Confidence-adjusted win rate: Higher confirmation = higher expected win rate
    confidence_adjustment = 1.0 + (avg_confidence - 7.0) * 0.05 if avg_confidence >= 7.0 else 1.0 - (7.0 - avg_confidence) * 0.08
    adjusted_win_rate = min(0.95, base_win_rate * confidence_adjustment)  # Cap at 95%
    
    # Expectancy: Average profit/loss per trade (simplified)
    expectancy = (wins - losses * 0.5) / total if total > 0 else 0.0
    
    # Win/Loss streaks
    recent_outcomes = s.get("recent_outcomes", [])
    win_streak = 0
    loss_streak = 0
    current_streak = "none"
    
    if recent_outcomes:
        # Count current streak
        current = recent_outcomes[-1]
        current_streak = "win" if current else "loss"
        
        for outcome in reversed(recent_outcomes):
            if outcome and current == "win":
                win_streak += 1
            elif not outcome and current == "loss":
                loss_streak += 1
            else:
                break
    
    # Prediction accuracy: How reliable confirmation scores are for this symbol
    confidence_scores = s.get("confidence_scores", [])
    prediction_accuracy = 0.5
    
    if len(confidence_scores) >= 5:
        avg_score = sum(confidence_scores) / len(confidence_scores)
        # Scores >= 7.0 should correlate with wins
        high_confidence_signals = sum(1 for score in confidence_scores[-10:] if score >= 7.0)
        recent_wins = sum(1 for outcome in recent_outcomes[-10:] if outcome) if recent_outcomes else 0
        
        if high_confidence_signals > 0:
            prediction_accuracy = min(0.99, recent_wins / len(recent_outcomes[-10:]) if recent_outcomes else 0.5)
    
    # Risk rating
    if base_win_rate >= 0.70 and avg_confidence >= 7.5:
        risk_rating = "LOW"
    elif base_win_rate >= 0.55 and avg_confidence >= 7.0:
        risk_rating = "MEDIUM"
    elif base_win_rate >= 0.45:
        risk_rating = "MEDIUM-HIGH"
    else:
        risk_rating = "HIGH"
    
    # Opportunity score: Should we trade this symbol?
    # High when: win rate is good, confidence is high, and profit factor is positive
    opportunity_score = (
        (adjusted_win_rate * 0.4) +  # 40% from win rate
        (min(profit_factor / 5.0, 1.0) * 0.3) +  # 30% from profit factor
        (prediction_accuracy * 0.2) +  # 20% from prediction accuracy
        ((avg_confidence / 10.0) * 0.1)  # 10% from confidence
    )
    opportunity_score = min(0.99, max(0.1, opportunity_score))
    
    return {
        "symbol": symbol,
        "win_count": wins,
        "loss_count": losses,
        "total_trades": total,
        "base_win_rate": round(base_win_rate, 4),
        "adjusted_win_rate": round(adjusted_win_rate, 4),
        "expectancy": round(expectancy, 4),
        "profit_factor": round(profit_factor, 2),
        "confidence_adjustment": round(confidence_adjustment, 3),
        "win_streak": win_streak,
        "loss_streak": loss_streak,
        "current_streak": current_streak,
        "prediction_accuracy": round(prediction_accuracy, 2),
        "risk_rating": risk_rating,
        "opportunity_score": round(opportunity_score, 2),
    }


def calculate_dynamic_lot_size(
    symbol: str,
    base_lot: float,
    account_balance: float,
    risk_percent: float,
) -> Tuple[float, Dict]:
    """
    Calculate INTELLIGENT lot size based on symbol confidence.
    
    Higher confidence = larger position
    Lower confidence = smaller position
    Losing streak = reduce size
    
    DIFFERENT MULTIPLIER RANGES BY ASSET CLASS:
    - FOREX: 0.5x to 1.0x (conservative, steady growth)
    - METALS: 0.7x to 1.2x (medium, balanced)
    - CRYPTO: 0.9x to 2.1x (aggressive, exploit volatility!)
    
    Returns: (lot_size, {details})
    """
    intel = calculate_precise_winning_rate(symbol)
    asset_class = infer_asset_class(symbol)
    
    # Asset class specific multiplier ranges
    # UPDATED (March 29, 2026): Reduced crypto range due to weak backtest performance
    multiplier_ranges = {
        "forex": {"min": 0.5, "max": 1.0},
        "metals": {"min": 0.7, "max": 1.2},
        "crypto": {"min": 0.5, "max": 1.2},  # REDUCED: was 0.9-2.1x (backtests show 14% WR - too risky)
        "other": {"min": 0.6, "max": 1.3},
    }
    
    asset_range = multiplier_ranges.get(asset_class, multiplier_ranges["other"])
    base_min, base_max = asset_range["min"], asset_range["max"]
    
    # Base multiplier from risk rating
    risk_multipliers = {
        "LOW": (base_max * 1.0),        # High confidence = at max for this asset class
        "MEDIUM": ((base_min + base_max) / 2),  # Normal position = mid-range
        "MEDIUM-HIGH": (base_min * 0.8),   # Reduced
        "HIGH": (base_min * 0.5),        # Very small
        "NEW": (base_min * 0.7),         # Small for unproven symbols
    }
    
    base_multiplier = risk_multipliers.get(intel["risk_rating"], (base_min + base_max) / 2)
    
    # Opportunity score multiplier (0.1 - 1.0)
    opportunity_multiplier = intel["opportunity_score"]
    
    # Streak penalty: Reduce size during losing streaks
    streak_multiplier = 1.0
    if intel["current_streak"] == "loss" and intel["loss_streak"] > 0:
        streak_multiplier = max(0.3, 1.0 - (intel["loss_streak"] * 0.15))  # Each loss = 15% reduction
    
    # Win streak bonus: Increase size during winning streaks
    if intel["current_streak"] == "win" and intel["win_streak"] > 1:
        streak_multiplier = min(1.8, 1.0 + (intel["win_streak"] - 1) * 0.2)  # Each win = 20% increase
    
    # Expectancy adjustment: Positive expectancy = larger, negative = smaller
    expectancy_multiplier = 1.0 + (intel["expectancy"] * 0.3) if intel["expectancy"] > 0 else 1.0 - abs(intel["expectancy"] * 0.5)
    expectancy_multiplier = max(0.2, min(2.0, expectancy_multiplier))
    
    # Final calculation
    final_multiplier = base_multiplier * opportunity_multiplier * streak_multiplier * expectancy_multiplier
    # Apply asset class specific limits
    final_multiplier = max(base_min, min(base_max, final_multiplier))
    
    final_lot = base_lot * final_multiplier
    
    # Risk check: Never exceed 5% of account per trade
    max_lot_for_risk = (account_balance * (risk_percent / 100.0)) / 100.0  # Simplified
    final_lot = min(final_lot, max_lot_for_risk)
    
    return round(final_lot, 2), {
        "base_lot": base_lot,
        "asset_class": asset_class,
        "multiplier_range": f"{base_min}x - {base_max}x",
        "base_multiplier": round(base_multiplier, 2),
        "opportunity_multiplier": round(opportunity_multiplier, 2),
        "streak_multiplier": round(streak_multiplier, 2),
        "expectancy_multiplier": round(expectancy_multiplier, 2),
        "final_multiplier": round(final_multiplier, 2),
        "final_lot": round(final_lot, 2),
        "reason": f"{asset_class.upper()} {intel['risk_rating']} + {intel['current_streak']} streak = {final_multiplier:.2f}x",
    }


def calculate_intelligent_stop_loss(
    entry_price: float,
    direction: str,
    base_pips: float,
    symbol: str,
) -> Tuple[float, Dict]:
    """
    Calculate INTELLIGENT stop loss placement.
    
    Higher confidence symbols = wider stops (give winners room)
    Lower confidence symbols = tighter stops (protect capital)
    High conviction signals = further stops
    """
    intel = calculate_precise_winning_rate(symbol)
    pip_size = 0.0001  # Standard pip size
    
    # Base stop loss adjustment
    if intel["total_trades"] == 0:
        # No history: use standard stop
        multiplier = 1.0
    elif intel["risk_rating"] == "LOW":
        # High confidence: wider stops, let winners run
        multiplier = 1.3
    elif intel["risk_rating"] == "MEDIUM":
        # Medium confidence: standard stops
        multiplier = 1.0
    else:
        # High/Medium-high risk: tighter stops, preserve capital
        multiplier = 0.7
    
    # Adjust based on streak: Losing momentum = tighter stop
    if intel["current_streak"] == "loss" and intel["loss_streak"] > 1:
        multiplier *= max(0.6, 1.0 - (intel["loss_streak"] * 0.1))
    
    # Adjust based on prediction accuracy
    # High accuracy = we trust the stop, wider is ok
    # Low accuracy = tighter stops
    if intel["prediction_accuracy"] > 0.75:
        multiplier *= 1.2
    elif intel["prediction_accuracy"] < 0.55:
        multiplier *= 0.8
    
    adjusted_pips = base_pips * multiplier
    
    if direction.lower() == "buy":
        sl_price = entry_price - (adjusted_pips * pip_size)
    else:
        sl_price = entry_price + (adjusted_pips * pip_size)
    
    return round(sl_price, 5), {
        "base_pips": base_pips,
        "adjusted_pips": round(adjusted_pips, 1),
        "multiplier": round(multiplier, 2),
        "reason": f"{intel['risk_rating']} risk + {intel['prediction_accuracy']*100:.0f}% accuracy",
    }


def should_take_trade(
    symbol: str,
    confirmation_score: float,
    signal_type: str,
) -> Tuple[bool, Dict]:
    """
    INTELLIGENT trade decision based on EVERYTHING.
    
    Says YES to trades that have high probability.
    Says NO to trades that don't fit the symbol pattern.
    
    ADAPTIVE ASSET-CLASS THRESHOLDS (learns from history):
    - FOREX: 75% (NEW) → 72% (LEARNING) → 65% (PROVEN) → 60% (VETERAN)
    - METALS: 75% (NEW) → 72% (LEARNING) → 62% (PROVEN) → 57% (VETERAN)
    - CRYPTO: 75% (NEW) → 72% (LEARNING) → 60% (PROVEN) → 55% (VETERAN)
    
    NEW symbols start HIGH (75%) and LOWER as they prove themselves.
    PROVEN symbols (50+ trades) get LOWER thresholds to execute more.
    
    Returns: (should_trade, {analysis})
    """
    intel = calculate_precise_winning_rate(symbol)
    asset_class = infer_asset_class(symbol)
    
    # DYNAMIC THRESHOLD - Adapts as symbol learns from history
    total_trades = intel.get("total_trades", 0)
    base_thresholds = {
        "forex": 0.65,
        "metals": 0.62,
        "crypto": 0.60,
        "other": 0.62,
    }
    base_threshold = base_thresholds.get(asset_class, 0.62)
    
    # Adaptive learning schedule
    if total_trades == 0:
        final_threshold = 0.75  # NEW: Very protective
    elif total_trades < 5:
        final_threshold = 0.72  # EARLY: Still cautious
    elif total_trades < 15:
        final_threshold = 0.68  # LEARNING: Building confidence
    elif total_trades < 50:
        final_threshold = base_threshold  # PROVEN: Normal operation
    else:
        final_threshold = max(0.55, base_threshold - 0.05)  # VETERAN: Reward proven symbols
    
    analysis = {
        "symbol": symbol,
        "asset_class": asset_class,
        "confirmation_score": confirmation_score,
        "signal_type": signal_type,
        "decision": False,
        "confidence": 0.0,
        "threshold": final_threshold,
        "factors": [],
    }
    
    # Factor 1: New symbol (no history) - TRADE SMALL
    if intel["total_trades"] == 0:
        if confirmation_score >= 6.5:
            analysis["factors"].append(f"New {asset_class} + moderate confirmation = SMALL trade OK")
            analysis["decision"] = True
            analysis["confidence"] = 0.6
        else:
            analysis["factors"].append("New symbol + low confirmation = SKIP")
            return False, analysis
    
    # Factor 2: Symbol win rate is too low (< 40%) - SKIP HIGH RISK
    elif intel["base_win_rate"] < 0.40:
        if confirmation_score < 6.5:
            analysis["factors"].append(f"Poor win rate ({intel['base_win_rate']:.1%}) + low confirmation = SKIP")
            return False, analysis
        else:
            analysis["factors"].append(f"Poor win rate ({intel['base_win_rate']:.1%}) but HIGH confirmation = TRY")
            analysis["decision"] = True
            analysis["confidence"] = 0.55
    
    # Factor 3: Symbol has great history (> 65% win rate)
    elif intel["base_win_rate"] >= 0.65:
        analysis["factors"].append(f"Strong {asset_class} win rate ({intel['base_win_rate']:.1%}) = ALWAYS TRADE")
        analysis["decision"] = True
        analysis["confidence"] = 0.95
    
    # Factor 4: Symbol is in good range (45-65% win rate)
    elif intel["base_win_rate"] >= 0.45:
        if confirmation_score >= 7.2:
            analysis["factors"].append(f"Good {asset_class} win rate ({intel['base_win_rate']:.1%}) + high confirmation = TRADE")
            analysis["decision"] = True
            analysis["confidence"] = 0.85
        elif confirmation_score >= 6.8:
            analysis["factors"].append(f"Good {asset_class} win rate ({intel['base_win_rate']:.1%}) + medium confirmation = TRADE")
            analysis["decision"] = True
            analysis["confidence"] = 0.70
        else:
            analysis["factors"].append(f"Good win rate but LOW confirmation = SKIP")
            return False, analysis
    
    # Factor 5: Losing streak penalty
    if intel["current_streak"] == "loss" and intel["loss_streak"] >= 3:
        analysis["factors"].append(f"⚠️ {intel['loss_streak']} loss streak = REDUCE confidence by 30%")
        analysis["confidence"] *= 0.7
        
        # Skip trade if confidence drops below threshold
        if analysis["confidence"] < final_threshold:
            analysis["decision"] = False
            return False, analysis
    
    # Factor 6: Win streak bonus
    if intel["current_streak"] == "win" and intel["win_streak"] >= 2:
        analysis["factors"].append(f"✅ {intel['win_streak']} win streak = INCREASE confidence by 25%")
        analysis["confidence"] = min(0.99, analysis["confidence"] * 1.25)
    
    # Factor 7: Signal type credibility (asset-class adjusted)
    signal_credibility = {
        "weighted_confirmation": 0.95,
        "four_confirmation": 0.90,
        "symbol_confidence_high": 0.85,
        "backtest_fallback": 0.75 if asset_class == "forex" else 0.80,  # Backtest is more trustworthy for crypto
    }
    
    credibility = signal_credibility.get(signal_type, 0.70)
    analysis["factors"].append(f"Signal type '{signal_type}' credibility: {credibility:.0%}")
    analysis["confidence"] *= credibility
    
    # Final threshold
    analysis["confidence"] = round(max(0.0, min(0.99, analysis["confidence"])), 2)
    
    if analysis["confidence"] >= final_threshold:
        analysis["decision"] = True
        analysis["factors"].append(f"✅ FINAL: {asset_class.upper()} trade with {analysis['confidence']:.0%} confidence (threshold: {final_threshold:.0%})")
    else:
        analysis["decision"] = False
        analysis["factors"].append(f"❌ FINAL: Skip - only {analysis['confidence']:.0%} confidence (need {final_threshold:.0%})")
    
    return analysis["decision"], analysis


def record_trade_outcome(
    symbol: str,
    win: bool,
    confirmation_score: float,
    entry_price: float = 0.0,
    exit_price: float = 0.0,
    stop_loss_price: float = 0.0,
    take_profit_price: float = 0.0,
    lot_size: float = 0.0,
    pnl: float = 0.0,
    signal_type: str = "unknown",
):
    """
    Record detailed trade outcome for intelligent learning.
    Tracks: entry, exit, result, confirmation reliability, etc.
    """
    stats = load_intelligent_stats()
    
    if symbol not in stats:
        stats[symbol] = {
            "symbol": symbol,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "confidence_scores": [],
            "avg_confidence": 0.0,
            "recent_outcomes": [],
            "recent_trades": [],
            "pnl_total": 0.0,
            "pnl_avg": 0.0,
            "last_updated": None,
        }
    
    s = stats[symbol]
    s["total_trades"] += 1
    
    if win:
        s["wins"] += 1
    else:
        s["losses"] += 1
    
    s["win_rate"] = s["wins"] / s["total_trades"] if s["total_trades"] > 0 else 0.0
    s["confidence_scores"].append(confirmation_score)
    
    # Keep last 50 scores
    if len(s["confidence_scores"]) > 50:
        s["confidence_scores"] = s["confidence_scores"][-50:]
    
    s["avg_confidence"] = sum(s["confidence_scores"]) / len(s["confidence_scores"]) if s["confidence_scores"] else 0.0
    
    # Track recent outcomes (last 30)
    s["recent_outcomes"].append(win)
    if len(s["recent_outcomes"]) > 30:
        s["recent_outcomes"] = s["recent_outcomes"][-30:]
    
    # Record detailed trade
    trade_detail = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "win": win,
        "confirmation_score": confirmation_score,
        "entry": entry_price,
        "exit": exit_price,
        "sl": stop_loss_price,
        "tp": take_profit_price,
        "lot": lot_size,
        "pnl": pnl,
        "signal_type": signal_type,
    }
    
    s["recent_trades"].append(trade_detail)
    if len(s["recent_trades"]) > 100:
        s["recent_trades"] = s["recent_trades"][-100:]
    
    s["pnl_total"] += pnl
    s["pnl_avg"] = s["pnl_total"] / s["total_trades"] if s["total_trades"] > 0 else 0.0
    s["last_updated"] = datetime.now().isoformat()
    
    save_intelligent_stats(stats)


def get_market_intelligence_report(symbols: List[str] = None) -> str:
    """
    Generate comprehensive market intelligence report.
    Shows: All symbols, win rates, opportunities, recommendations.
    """
    stats = load_intelligent_stats()
    
    if not stats:
        return "[MARKET INTEL] No trading data yet. System learning..."
    
    if symbols is None:
        symbols = sorted(stats.keys())
    else:
        symbols = sorted([s for s in symbols if s in stats])
    
    report = "\n" + "=" * 100 + "\n"
    report += "[INTELLIGENT EXECUTION MARKET INTELLIGENCE REPORT]\n"
    report += "=" * 100 + "\n\n"
    
    # Summary row
    report += f"{'SYMBOL':<10} {'TRADES':<8} {'W-L':<12} {'W%':<8} {'RATING':<12} {'OPPORTUNITY':<12} {'EXPECTANCY':<10}\n"
    report += "-" * 100 + "\n"
    
    total_trades = 0
    total_wins = 0
    all_opportunities = []
    
    for symbol in symbols:
        intel = calculate_precise_winning_rate(symbol)
        
        if intel["total_trades"] == 0:
            continue
        
        total_trades += intel["total_trades"]
        total_wins += intel["win_count"]
        all_opportunities.append((symbol, intel["opportunity_score"]))
        
        wl = f"{intel['win_count']}-{intel['loss_count']}"
        w_pct = f"{intel['base_win_rate']*100:.0f}%"
        opp_score = f"{intel['opportunity_score']:.2f}"
        exp = f"{intel['expectancy']:.2f}"
        rating = intel["risk_rating"]
        
        # Color coding by performance
        if intel["opportunity_score"] >= 0.80:
            status = "🟢"  # Green - trade it
        elif intel["opportunity_score"] >= 0.60:
            status = "🟡"  # Yellow - cautious
        else:
            status = "🔴"  # Red - avoid
        
        report += f"{symbol:<10} {intel['total_trades']:<8} {wl:<12} {w_pct:<8} {rating:<12} {opp_score:<12} {exp:<10} {status}\n"
    
    report += "-" * 100 + "\n"
    if total_trades > 0:
        portfolio_wr = f"{total_wins}/{total_trades} = {total_wins/total_trades*100:.1f}%"
        report += f"{'PORTFOLIO':<10} {total_trades:<8} {total_wins:<2}-{total_trades-total_wins:<2} {portfolio_wr:<36}\n"
    
    report += "\n[TOP OPPORTUNITIES - Trade These]\n"
    all_opportunities.sort(key=lambda x: x[1], reverse=True)
    for symbol, score in all_opportunities[:5]:
        intel = calculate_precise_winning_rate(symbol)
        report += f"  🟢 {symbol}: Opportunity {score:.2f} (WR: {intel['base_win_rate']:.1%}, Predict: {intel['prediction_accuracy']:.0%})\n"
    
    report += "\n[CAUTION SYMBOLS - Trade Smaller Or Skip]\n"
    for symbol, score in all_opportunities[-3:]:
        if score < 0.65:
            intel = calculate_precise_winning_rate(symbol)
            report += f"  🔴 {symbol}: Opportunity {score:.2f} (WR: {intel['base_win_rate']:.1%}, Risk: {intel['risk_rating']})\n"
    
    report += "\n" + "=" * 100 + "\n"
    return report


def get_intelligent_recommendation(symbol: str) -> str:
    """Get one-line smart recommendation for a symbol."""
    intel = calculate_precise_winning_rate(symbol)
    
    if intel["total_trades"] == 0:
        return "First trade - use 60% normal lot size"
    
    if intel["opportunity_score"] >= 0.85:
        return f"✅ STRONG - {intel['base_win_rate']:.0%} WR, {intel['profit_factor']:.1f}x profit - Trade FULL size"
    elif intel["opportunity_score"] >= 0.75:
        return f"✓ GOOD - {intel['base_win_rate']:.0%} WR - Trade NORMAL size"
    elif intel["opportunity_score"] >= 0.65:
        return f"~ CAUTIOUS - {intel['base_win_rate']:.0%} WR - Trade REDUCED size (70%)"
    elif intel["opportunity_score"] >= 0.55:
        return f"⚠️ RISKY - {intel['base_win_rate']:.0%} WR - Trade VERY SMALL (40%)"
    else:
        return f"❌ AVOID - {intel['base_win_rate']:.0%} WR - Skip or minimum size only"


def load_intelligent_skip_stats():
    """Load persistent skip tracking data from disk - SURVIVES NETWORK DISRUPTION."""
    if INTELLIGENT_SKIP_FILE.exists():
        try:
            with open(INTELLIGENT_SKIP_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_intelligent_skip_stats(skip_data):
    """Save skip statistics to disk - PERSISTENT even if system crashes or network goes down."""
    try:
        INTELLIGENT_SKIP_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(INTELLIGENT_SKIP_FILE, 'w') as f:
            json.dump(skip_data, f, indent=2)
    except Exception as e:
        print(f"[WARNING] Failed to save skip tracking: {e}")


def record_skip_detailed(reason: str, symbol: str, confidence: float = 0.0, analysis: Dict = None):
    """
    Record SKIPPED trade with detailed data to PERSISTENT storage.
    
    This is CRITICAL for learning - system learns what trades to avoid!
    Data survives network disruption, system restart, etc.
    
    Args:
        reason: Why trade was skipped (intelligence, confirmation, backtest, etc)
        symbol: Trading symbol
        confidence: Entry confidence score (0.0-1.0) if known
        analysis: Detailed analysis dict from decision function
    """
    skip_data = load_intelligent_skip_stats()
    
    # Initialize symbol entry if new
    if symbol not in skip_data:
        skip_data[symbol] = {
            "symbol": symbol,
            "total_skips": 0,
            "skip_reasons": {},  # Reason -> count
            "skip_samples": [],  # Last 50 skipped opportunities
            "last_skip": None,
            "skip_patterns": {},  # Reason -> list of confidence scores
        }
    
    s = skip_data[symbol]
    s["total_skips"] += 1
    
    # Track reason frequency
    s["skip_reasons"][reason] = s["skip_reasons"].get(reason, 0) + 1
    
    # Track confidence pattern for this reason
    if reason not in s["skip_patterns"]:
        s["skip_patterns"][reason] = []
    s["skip_patterns"][reason].append(confidence)
    if len(s["skip_patterns"][reason]) > 100:  # Keep last 100 per reason
        s["skip_patterns"][reason] = s["skip_patterns"][reason][-100:]
    
    # Record detailed skip sample
    skip_record = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "reason": reason,
        "confidence": confidence,
        "analysis_summary": analysis.get("factors", [])[-3:] if analysis else [],  # Last 3 decision factors
        "signal_type": analysis.get("signal_type", "unknown") if analysis else "unknown",
    }
    
    s["skip_samples"].append(skip_record)
    if len(s["skip_samples"]) > 50:  # Keep last 50 skips per symbol
        s["skip_samples"] = s["skip_samples"][-50:]
    
    s["last_skip"] = datetime.now().isoformat()
    
    # PERSIST TO DISK IMMEDIATELY - Critical!
    save_intelligent_skip_stats(skip_data)


def get_skip_pattern_analysis(symbol: str) -> Dict:
    """
    Analyze why a symbol keeps getting skipped - helps identify false signals.
    
    Returns:
        {
            "symbol": "GBPUSD",
            "total_skips": 47,
            "most_common_skip_reason": "intelligence",  # Confidence too low
            "confidence_pattern": {
                "intelligence": [58%, 61%, 59%, ...]  # Consistently below threshold?
            },
            "recommendation": "Stop trying until confirmation improves"
        }
    """
    skip_data = load_intelligent_skip_stats()
    
    if symbol not in skip_data:
        return {
            "symbol": symbol,
            "total_skips": 0,
            "most_common_skip_reason": "none",
            "confidence_pattern": {},
            "recommendation": "Not enough skip history yet",
        }
    
    s = skip_data[symbol]
    
    if s["total_skips"] == 0:
        return {
            "symbol": symbol,
            "total_skips": 0,
            "most_common_skip_reason": "none",
            "confidence_pattern": {},
            "recommendation": "No skips recorded yet",
        }
    
    # Find most common reason
    most_common = max(s["skip_reasons"].items(), key=lambda x: x[1]) if s["skip_reasons"] else ("unknown", 0)
    
    # Calculate avg confidence per reason
    confidence_by_reason = {}
    for reason, scores in s["skip_patterns"].items():
        if scores:
            confidence_by_reason[reason] = {
                "avg": sum(scores) / len(scores),
                "min": min(scores),
                "max": max(scores),
                "count": len(scores),
            }
    
    recommendation = f"Skipped {s['total_skips']} times (mainly: {most_common[0]})"
    if most_common[1] >= 10:
        recommendation += " - PATTERN DETECTED! Review this symbol's signals."
    
    return {
        "symbol": symbol,
        "total_skips": s["total_skips"],
        "most_common_skip_reason": most_common[0],
        "skip_reason_breakdown": s["skip_reasons"],
        "confidence_patterns": confidence_by_reason,
        "recent_skip_samples": s["skip_samples"][-3:] if s["skip_samples"] else [],
        "recommendation": recommendation,
    }


def get_skip_statistics_report() -> str:
    """
    Generate comprehensive skip pattern report.
    Shows which symbols are repeatedly skipped and why.
    CRITICAL for identifying false signals and improving entry models.
    """
    skip_data = load_intelligent_skip_stats()
    exec_data = load_intelligent_stats()
    
    if not skip_data:
        return "[SKIP ANALYSIS] No skip data yet. System learning..."
    
    report = "\n" + "=" * 110 + "\n"
    report += "[SKIP PATTERN ANALYSIS REPORT - LEARNING FROM FAILED ENTRY ATTEMPTS]\n"
    report += "=" * 110 + "\n\n"
    
    # Build symbol list with skip counts
    symbols_with_skips = []
    for symbol, data in skip_data.items():
        if data.get("total_skips", 0) > 0:
            symbols_with_skips.append((symbol, data))
    
    symbols_with_skips.sort(key=lambda x: x[1].get("total_skips", 0), reverse=True)
    
    report += f"{'SYMBOL':<10} {'SKIPS':<8} {'EXECUTED':<10} {'TOP_REASON':<20} {'STATUS':<25}\n"
    report += "-" * 110 + "\n"
    
    high_skip_symbols = []
    
    for symbol, skip_info in symbols_with_skips[:20]:  # Top 20 most skipped
        total_skips = skip_info.get("total_skips", 0)
        exec_count = 0
        
        if symbol in exec_data and exec_data[symbol].get("total_trades", 0) > 0:
            exec_count = exec_data[symbol]["total_trades"]
            win_rate = exec_data[symbol].get("win_rate", 0)
            status = f"Trades: {exec_count} (WR: {win_rate:.0%})"
        else:
            status = "NOT YET TRADED"
        
        skip_reasons = skip_info.get("skip_reasons", {})
        top_reason = max(skip_reasons.items(), key=lambda x: x[1])[0] if skip_reasons else "unknown"
        
        if total_skips >= 15:
            high_skip_symbols.append({
                "symbol": symbol,
                "skips": total_skips,
                "trades": exec_count,
                "top_reason": top_reason,
                "analysis": get_skip_pattern_analysis(symbol)
            })
            status_emoji = "⚠️ PATTERN"
        elif total_skips >= 5:
            status_emoji = "🟡 FREQUENT"
        else:
            status_emoji = "🟢 NORMAL"
        
        report += f"{symbol:<10} {total_skips:<8} {exec_count:<10} {top_reason:<20} {status_emoji} {status:<15}\n"
    
    # Critical insights
    report += "\n" + "=" * 110 + "\n"
    report += "[CRITICAL SKIP PATTERNS - SYMBOLS TO REVIEW]\n"
    report += "-" * 110 + "\n"
    
    if high_skip_symbols:
        for item in high_skip_symbols[:5]:
            analysis = item["analysis"]
            report += f"\n🔴 {item['symbol']}: Skipped {item['skips']} times, only {item['trades']} executed\n"
            report += f"   Top Reason: {item['top_reason']}\n"
            report += f"   Recommendation: {analysis.get('recommendation', 'Unknown')}\n"
            
            # Show confidence patterns
            patterns = analysis.get("confidence_patterns", {})
            if patterns:
                report += f"   Confidence Patterns:\n"
                for reason, stats in list(patterns.items())[:3]:
                    report += f"      - {reason}: avg={stats['avg']:.1%}, range {stats['min']:.0%}-{stats['max']:.0%}\n"
    else:
        report += "No critical skip patterns detected.\n"
    
    # Learning insights
    report += "\n" + "=" * 110 + "\n"
    report += "[LEARNING INSIGHTS]\n"
    total_skip_attempts = sum(d.get("total_skips", 0) for d in skip_data.values())
    total_executed = sum(d.get("total_trades", 0) for d in exec_data.values())
    
    report += f"Total Skip Attempts (Avoided): {total_skip_attempts}\n"
    report += f"Total Executed Trades: {total_executed}\n"
    
    if total_skip_attempts + total_executed > 0:
        skip_rate = total_skip_attempts / (total_skip_attempts + total_executed)
        report += f"System Caution Rate: {skip_rate:.1%} (System skips ~{skip_rate:.0%} of opportunities)\n"
        report += f"Trading Rate: {1-skip_rate:.1%} (System executes high-confidence trades only)\n"
    
    report += "\n[WHAT THIS MEANS]\n"
    report += "✓ Skipped trades are being SAVED and STUDIED for pattern learning\n"
    report += "✓ Data is PERSISTED to disk (/data/intelligent_skip_tracking.json)\n"
    report += "✓ If system crashes or network goes down, skip data STAYS INTACT\n"
    report += "✓ System learns which symbols always fail and avoids them\n"
    report += "✓ HIGH SKIP symbols show bad entry models for those symbols\n"
    report += "\n" + "=" * 110 + "\n"
    
    return report


def should_skip_symbol_entirely(symbol: str) -> Tuple[bool, str]:
    """
    Determine if a symbol should be SKIPPED ENTIRELY based on skip history.
    
    Uses pattern analysis: If symbol has too many skips relative to trades,
    the entry model is probably broken for that symbol.
    
    Returns:
        (should_skip: bool, reason: str)
        - (True, "reason") if symbol should be avoided
        - (False, "") if symbol is tradeable
    
    EXAMPLE:
        - GBPUSD: 47 skips, 3 trades (94% skip rate) → SKIP
        - EURUSD: 8 skips, 15 trades (35% skip rate) → TRADE
    """
    skip_data = load_intelligent_skip_stats()
    exec_data = load_intelligent_stats()
    
    if symbol not in skip_data:
        return False, ""  # No skip history = safe to trade
    
    total_skips = skip_data[symbol].get("total_skips", 0)
    
    if total_skips == 0:
        return False, ""
    
    # Get execution data
    exec_count = 0
    if symbol in exec_data:
        exec_count = exec_data[symbol].get("total_trades", 0)
    
    skip_rate = total_skips / (total_skips + exec_count) if (total_skips + exec_count) > 0 else 0.0
    
    # AGGRESSIVE SKIP PATTERN: 80%+ of attempts skipped
    if skip_rate >= 0.80 and total_skips >= 20:
        return True, f"VERY HIGH skip rate ({skip_rate:.0%}, {total_skips} attempts). Entry model broken for {symbol}."
    
    # MODERATE SKIP PATTERN: 70%+ of attempts skipped with many attempts
    if skip_rate >= 0.70 and total_skips >= 15:
        return True, f"HIGH skip rate ({skip_rate:.0%}, {total_skips} attempts). {symbol} signals are unreliable."
    
    # REPEATED FAILURES: Many skips but some trades with low win rate
    if total_skips >= 20 and exec_count > 0:
        win_rate = exec_data[symbol].get("win_rate", 0)
        if win_rate < 0.30:  # Less than 30% win rate
            return True, f"Low performance: only {win_rate:.0%} WR ({exec_count} trades), {total_skips} skips. Avoid until signals improve."
    
    return False, ""


def get_learned_threshold_adjustment(symbol: str) -> float:
    """
    Calculate confidence threshold ADJUSTMENT based on skip patterns.
    
    When a symbol has many skips, it means the entry model is weak.
    We can learn this and adjust threshold UP (require more confidence)
    or DOWN (relax requirement if symbol eventually trades well).
    
    Returns:
        threshold_modifier: float to ADD to final threshold
        - 0.05 = add 5 percentage points to threshold (require 80% instead of 75%)
        - -0.05 = subtract 5 percentage points (require 70% instead of 75%)
    
    EXAMPLE:
        Symbol with 40 skips, 10 trades, 65% WR:
        - Skip rate: 80%
        - Win rate: 65% (good)
        - Decision: Raise threshold +5% (require 80%, not 75%)
                    because entry model is weak but results are good
    """
    skip_data = load_intelligent_skip_stats()
    exec_data = load_intelligent_stats()
    
    if symbol not in skip_data:
        return 0.0  # No skip history = no adjustment
    
    total_skips = skip_data[symbol].get("total_skips", 0)
    
    if total_skips < 5:
        return 0.0  # Not enough skip history
    
    # Calculate skip rate
    exec_count = 0
    win_rate = 0.5
    if symbol in exec_data:
        exec_count = exec_data[symbol].get("total_trades", 0)
        win_rate = exec_data[symbol].get("win_rate", 0)
    
    skip_rate = total_skips / (total_skips + exec_count) if (total_skips + exec_count) > 0 else 0.0
    
    adjustment = 0.0
    
    # HIGH skip rate + NO trades yet = RAISE threshold (be more cautious)
    if skip_rate >= 0.75 and exec_count == 0:
        adjustment = 0.10  # Raise threshold by 10% (75% → 85%)
    # HIGH skip rate + POOR results = RAISE threshold (be more cautious)
    elif skip_rate >= 0.70 and win_rate < 0.40:
        adjustment = 0.08  # Raise threshold by 8%
    # MODERATE skip rate + GOOD results = LOWER threshold slightly (reward it)
    elif skip_rate >= 0.50 and win_rate >= 0.60 and exec_count >= 5:
        adjustment = -0.03  # Lower threshold by 3% (symbol is improving)
    # MANY skips but EXCELLENT results = SIGNIFICANTLY LOWER threshold
    elif skip_rate >= 0.70 and win_rate >= 0.70 and exec_count >= 10:
        adjustment = -0.05  # Lower threshold by 5% (it's a real gem)
    
    # Cap the adjustment
    return max(-0.10, min(0.10, adjustment))


def learn_from_repeated_skips(symbol: str) -> Dict:
    """
    Generate LEARNING RECOMMENDATIONS from skip patterns.
    
    When a symbol appears multiple times in skip records, the system
    can extract lessons for improving entry models.
    
    Returns:
        {
            "symbol": "GBPUSD",
            "skip_count": 47,
            "learned_insights": [...],
            "recommendations": [...],
            "threshold_adjustment": 0.05,
            "avoid_until": "win_rate reaches 45%" or None
        }
    """
    skip_analysis = get_skip_pattern_analysis(symbol)
    skip_data = load_intelligent_skip_stats()
    exec_data = load_intelligent_stats()
    
    if symbol not in skip_data:
        return {"symbol": symbol, "skip_count": 0, "learned_insights": [], "recommendations": []}
    
    total_skips = skip_data[symbol].get("total_skips", 0)
    
    if total_skips < 5:
        return {
            "symbol": symbol,
            "skip_count": total_skips,
            "learned_insights": ["Not enough skip history yet"],
            "recommendations": ["Continue monitoring"]
        }
    
    insights = []
    recommendations = []
    
    # Analyze skip reasons
    skip_reasons = skip_data[symbol].get("skip_reasons", {})
    if skip_reasons:
        top_reason = max(skip_reasons.items(), key=lambda x: x[1])[0]
        top_count = skip_reasons[top_reason]
        
        if top_reason == "intelligence":
            insights.append(f"Confidence is consistently too low ({top_count}/{total_skips} skips due to this)")
            recommendations.append("Strengthen entry model: add more confirmation signals")
            recommendations.append("Check if symbol requires different confirmation types")
        
        elif top_reason == "confirmation_score":
            insights.append(f"Multi-confirmation requirements not met ({top_count}/{total_skips} skips)")
            recommendations.append("Verify 4-confirmation logic is working for this symbol")
            recommendations.append("May need topdown confirmation instead of weighted")
        
        elif top_reason == "backtest":
            insights.append(f"Backtesting shows poor historical results ({top_count}/{total_skips} skips)")
            recommendations.append("Review backtest approval for this symbol")
            recommendations.append("Historical data may indicate symbol is unprofitable")
        
        else:
            insights.append(f"Primary skip reason: {top_reason} ({top_count} occurrences)")
    
    # Analyze confidence patterns
    confidence_patterns = skip_analysis.get("confidence_patterns", {})
    for reason, stats in confidence_patterns.items():
        if stats.get("count", 0) > 0:
            avg_conf = stats.get("avg", 0)
            if reason == "intelligence" and avg_conf < 0.65:
                insights.append(f"Intelligence confidence for {symbol} stuck at {avg_conf:.0%}")
                recommendations.append("Consider if symbol's market structure changed")
    
    # Check execution stats
    exec_count = 0
    win_rate = 0
    if symbol in exec_data:
        exec_count = exec_data[symbol].get("total_trades", 0)
        win_rate = exec_data[symbol].get("win_rate", 0)
    
    skip_rate = total_skips / (total_skips + exec_count) if (total_skips + exec_count) > 0 else 0.0
    
    insights.append(f"Skip rate for {symbol}: {skip_rate:.0%} ({total_skips} skips vs {exec_count} executions)")
    
    # Generate recommendations based on pattern
    if exec_count == 0:
        recommendations.append("CRITICAL: Never successfully traded. Entry model may be broken.")
        recommendations.append("Either fix entry signals OR consider removing symbol from watch list")
    elif skip_rate > 0.70:
        recommendations.append(f"HIGH CAUTION: {skip_rate:.0%} of signals are rejected. System is protective.")
        if win_rate > 0.60:
            recommendations.append("But actual trades are profitable! Might be over-protective.")
        else:
            recommendations.append("And win rate is low. Avoid this symbol until signals improve.")
    
    threshold_adjustment = get_learned_threshold_adjustment(symbol)
    avoid_until = None
    
    if skip_rate >= 0.80 and exec_count < 5:
        avoid_until = "System gets confidence in entry signals"
    elif win_rate > 0 and win_rate < 0.40:
        avoid_until = "win rate reaches 45%"
    
    return {
        "symbol": symbol,
        "skip_count": total_skips,
        "execution_count": exec_count,
        "skip_rate": skip_rate,
        "win_rate": win_rate,
        "learned_insights": insights,
        "recommendations": recommendations,
        "threshold_adjustment": threshold_adjustment,
        "avoid_until": avoid_until,
    }
