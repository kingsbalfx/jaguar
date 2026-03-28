"""
Intelligent Execution System
=============================
10,000% IQ smarter execution for winning AND losing scenarios.

Analyzes:
1. Symbol win/loss patterns
2. Confirmation score reliability
3. Market conditions
4. Dynamic risk based on confidence
5. Loss prevention strategies
6. Position sizing optimization
7. Trade timing intelligence
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, List

INTELLIGENT_STATS_FILE = Path(__file__).resolve().parent.parent / "data" / "intelligent_execution_stats.json"


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
    
    Returns: (lot_size, {details})
    """
    intel = calculate_precise_winning_rate(symbol)
    
    # Base multiplier from risk rating
    risk_multipliers = {
        "LOW": 1.5,           # High confidence = trade bigger
        "MEDIUM": 1.0,        # Normal position
        "MEDIUM-HIGH": 0.7,   # Reduced
        "HIGH": 0.4,          # Very small
        "NEW": 0.6,           # Small for unproven symbols
    }
    
    base_multiplier = risk_multipliers.get(intel["risk_rating"], 1.0)
    
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
    final_multiplier = max(0.1, min(2.5, final_multiplier))  # Keep within 0.1x to 2.5x
    
    final_lot = base_lot * final_multiplier
    
    # Risk check: Never exceed 5% of account per trade
    max_lot_for_risk = (account_balance * (risk_percent / 100.0)) / 100.0  # Simplified
    final_lot = min(final_lot, max_lot_for_risk)
    
    return round(final_lot, 2), {
        "base_lot": base_lot,
        "base_multiplier": round(base_multiplier, 2),
        "opportunity_multiplier": round(opportunity_multiplier, 2),
        "streak_multiplier": round(streak_multiplier, 2),
        "expectancy_multiplier": round(expectancy_multiplier, 2),
        "final_multiplier": round(final_multiplier, 2),
        "final_lot": round(final_lot, 2),
        "reason": f"{intel['risk_rating']} risk + {intel['current_streak']} streak",
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
    
    Returns: (should_trade, {analysis})
    """
    intel = calculate_precise_winning_rate(symbol)
    
    analysis = {
        "symbol": symbol,
        "confirmation_score": confirmation_score,
        "signal_type": signal_type,
        "decision": False,
        "confidence": 0.0,
        "factors": [],
    }
    
    # Factor 1: New symbol (no history) - TRADE SMALL
    if intel["total_trades"] == 0:
        if confirmation_score >= 7.5:
            analysis["factors"].append("New symbol + high confirmation = SMALL trade OK")
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
        analysis["factors"].append(f"Strong win rate ({intel['base_win_rate']:.1%}) = ALWAYS TRADE")
        analysis["decision"] = True
        analysis["confidence"] = 0.95
    
    # Factor 4: Symbol is in good range (45-65% win rate)
    elif intel["base_win_rate"] >= 0.45:
        if confirmation_score >= 7.2:
            analysis["factors"].append(f"Good win rate ({intel['base_win_rate']:.1%}) + high confirmation = TRADE")
            analysis["decision"] = True
            analysis["confidence"] = 0.85
        elif confirmation_score >= 6.8:
            analysis["factors"].append(f"Good win rate ({intel['base_win_rate']:.1%}) + medium confirmation = TRADE")
            analysis["decision"] = True
            analysis["confidence"] = 0.70
        else:
            analysis["factors"].append(f"Good win rate but LOW confirmation = SKIP")
            return False, analysis
    
    # Factor 5: Losing streak penalty
    if intel["current_streak"] == "loss" and intel["loss_streak"] >= 3:
        analysis["factors"].append(f"⚠️ {intel['loss_streak']} loss streak = REDUCE confidence by 30%")
        analysis["confidence"] *= 0.7
        
        # Skip trade if confidence drops below 0.6
        if analysis["confidence"] < 0.6:
            analysis["decision"] = False
            return False, analysis
    
    # Factor 6: Win streak bonus
    if intel["current_streak"] == "win" and intel["win_streak"] >= 2:
        analysis["factors"].append(f"✅ {intel['win_streak']} win streak = INCREASE confidence by 25%")
        analysis["confidence"] = min(0.99, analysis["confidence"] * 1.25)
    
    # Factor 7: Signal type credibility
    signal_credibility = {
        "weighted_confirmation": 0.95,
        "four_confirmation": 0.90,
        "symbol_confidence_high": 0.85,
        "backtest_fallback": 0.75,
    }
    
    credibility = signal_credibility.get(signal_type, 0.70)
    analysis["factors"].append(f"Signal type '{signal_type}' credibility: {credibility:.0%}")
    analysis["confidence"] *= credibility
    
    # Final threshold
    analysis["confidence"] = round(max(0.0, min(0.99, analysis["confidence"])), 2)
    
    if analysis["confidence"] >= 0.65:
        analysis["decision"] = True
        analysis["factors"].append(f"✅ FINAL: Trade with {analysis['confidence']:.0%} confidence")
    else:
        analysis["decision"] = False
        analysis["factors"].append(f"❌ FINAL: Skip - only {analysis['confidence']:.0%} confidence")
    
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
