"""
Jaguar Trend Dynamics Analyzer
Analyzes market position (Reversal vs Continuation vs Swing) with ICT Displacement.
"""

class TrendDynamicsAnalyzer:
    def __init__(self):
        self.states = ["CONTINUATION", "REVERSAL", "MSS", "SWING_RETRACEMENT", "COMPLEX_CHOPI"]

    def analyze_market_position(self, htf_data, mtf_data, current_price, direction):
        """
        Determines the current phase of the market relative to structure.
        htf_data: D1/H1 structure
        mtf_data: M15 swing structure
        """
        # Safety check to prevent crash on empty data
        if not mtf_data or len(mtf_data) < 5:
            return {"score": 0.5, "label": "UNKNOWN", "position_in_range": 0.5, "htf_alignment": False}

        # 1. Identify Swing Points on MTF (M15)
        recent_data = mtf_data[-20:]
        recent_high = max([x['high'] for x in recent_data])
        recent_low = min([x['low'] for x in recent_data])
        swing_range = recent_high - recent_low
        
        # 2. Calculate Premium/Discount (Market Position)
        # 0% is Low, 100% is High
        position_percent = (current_price - recent_low) / swing_range if swing_range > 0 else 0.5

        # 3. Trend Alignment
        htf_trend = self._get_trend(htf_data) # 'bullish' or 'bearish'
        mtf_trend = self._get_trend(mtf_data)

        # 3.1 Displacement Factor (ICT Displacement)
        displacement = self._calculate_displacement(mtf_data[-3:])

        # Logic for REVERSAL Identification
        # (HTF is Bullish, but MTF just broke a Low = Potential Reversal or Deep Swing)
        is_reversal = False
        if direction == "buy" and mtf_trend == "bearish" and htf_trend == "bullish":
            # Potential "Buy the Dip" or Reversal back to trend
            is_reversal = True

        # 3.2 Market Structure Shift (MSS) Detection
        # MSS is the first change in character with displacement
        is_mss = False
        if is_reversal and displacement > 0.7:
            is_mss = True

        # Logic for CONTINUATION
        is_continuation = (htf_trend == mtf_trend == ("bullish" if direction == "buy" else "bearish"))

        # 4. Scoring Logic
        dynamics_score = 0.5 # Neutral base
        
        if is_continuation:
            # Strong continuation: Price is NOT in premium/discount extremes
            if direction == "buy" and position_percent < 0.7:
                dynamics_score = 0.9  # High quality continuation
            elif direction == "sell" and position_percent > 0.3:
                dynamics_score = 0.9
            else:
                dynamics_score = 0.7  # Continuation but extended (risky)

        elif is_reversal:
            # Reversal setups need specific "Rejection" at extremes
            if direction == "buy" and position_percent < 0.2:
                dynamics_score = 0.85 # Strong "Sweep into Reversal" setup
            elif direction == "sell" and position_percent > 0.8:
                dynamics_score = 0.85
            else:
                dynamics_score = 0.4

        # Boost score if MSS with Displacement is detected
        if is_mss:
            dynamics_score = min(1.0, dynamics_score + 0.15)
            label = "MSS"
        else:
            label = "CONTINUATION" if is_continuation else "REVERSAL" if is_reversal else "SWING"

        # 5. Swing/Retracement Check (Optimal Trade Entry - OTE)
        # Check if price is in the 62%-79% retracement zone of the recent swing
        if direction == "buy" and 0.2 < position_percent < 0.4:
            dynamics_score = max(dynamics_score, 0.8) # Strong Swing Pullback
        elif direction == "sell" and 0.6 > position_percent > 0.8:
            dynamics_score = max(dynamics_score, 0.8)

        return {
            "score": dynamics_score,
            "label": label,
            "position_in_range": position_percent,
            "htf_alignment": htf_trend == mtf_trend,
            "displacement": displacement
        }

    def _calculate_displacement(self, candles):
        """Measures ICT displacement: strong body, minimal wicks, large size relative to recent candles."""
        if len(candles) < 3: return 0.5
        bodies = [abs(c['close'] - c['open']) for c in candles]
        ranges = [c['high'] - c['low'] for c in candles]
        
        # Displacement if last body is large and body accounts for most of the range
        last_body = bodies[-1]
        last_range = ranges[-1]
        avg_body = sum(bodies[:-1]) / (len(bodies) - 1) if len(bodies) > 1 else bodies[0]
        
        if last_body > (avg_body * 1.5) and (last_body / last_range if last_range > 0 else 0) > 0.7:
            return 0.9
        return 0.5

    def _get_trend(self, data):
        """Helper to determine simple HH/HL structure"""
        if len(data) < 10: return "neutral"
        
        # IMPROVEMENT: Use Swing Points instead of simple candle offset
        highs = [x['high'] for x in data[-15:]]
        lows = [x['low'] for x in data[-15:]]
        
        current_close = data[-1]['close']
        if current_close > max(highs[:-2]) and data[-1]['low'] > min(lows[-5:]):
            return "bullish"
        if current_close < min(lows[:-2]) and data[-1]['high'] < max(highs[-5:]):
            return "bearish"
        return "neutral"