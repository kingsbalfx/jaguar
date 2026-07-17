"""
FALLBACK STRATEGY 3 - Models
=============================
Data structures for Fallback 3 analysis results and state tracking.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

# Direction type alias
Direction = str  # "buy" or "sell"


@dataclass
class SweepResult:
    """Result of liquidity sweep analysis."""
    detected: bool = False
    sweep_direction: Optional[str] = None       # "buy" or "sell" — direction of sweep movement
    sweep_level: Optional[float] = None          # Price level of the swept liquidity
    penetration_distance: float = 0.0            # How far price went beyond level
    sweep_type: str = "none"                     # "wick", "multi_candle", "displacement"
    candle_count_beyond: int = 0                 # Candles trading beyond level
    return_inside: bool = False                  # Whether price returned inside prior range
    momentum_weak_beyond: bool = False           # Weakening momentum beyond level
    classification: str = "unknown"              # "sweep", "breakout", "uncertain"
    classification_score: float = 0.0            # 0.0 = breakout, 1.0 = sweep
    displacement_detected: bool = False          # Opposing displacement after sweep
    displacement_index: Optional[int] = None
    displacement_body_ratio: float = 0.0
    displacement_range_ratio: float = 0.0
    displaced_high: Optional[float] = None
    displaced_low: Optional[float] = None


@dataclass
class CHOCHResult:
    """Result of lower-timeframe CHOCH analysis."""
    detected: bool = False
    direction: Optional[str] = None              # "bullish" or "bearish"
    swing_level: Optional[float] = None          # Internal swing high/low broken
    close_level: Optional[float] = None          # Close of the CHOCH candle
    candle_index: int = -1
    close_distance_above_swing: float = 0.0      # How far close is beyond swing
    body_ratio: float = 0.0                      # Body to range ratio of break candle
    close_above_proportion: float = 0.0          # Close distance relative to ATR
    break_candle_confirmed: bool = False         # Candle is fully closed
    immediately_invalidated: bool = False        # Next candle reversed


@dataclass
class MACDResult:
    """Result of MACD confirmation."""
    macd_line: float = 0.0
    signal_line: float = 0.0
    histogram: float = 0.0
    histogram_increasing: bool = False
    histogram_decreasing: bool = False
    histogram_positive: bool = False
    histogram_negative: bool = False
    cross_detected: bool = False
    cross_direction: Optional[str] = None        # "bullish" or "bearish"
    cross_age: int = 999                         # Candles since crossover
    zero_cross: bool = False                     # MACD line crossed zero
    bullish_divergence: bool = False
    bearish_divergence: bool = False
    confirmed: bool = False
    contradiction: bool = False                  # Strongly opposes CHOCH
    data_complete: bool = True


@dataclass
class SMAResult:
    """Result of SMA crossover confirmation."""
    fast_sma: float = 0.0
    slow_sma: float = 0.0
    fast_slope: float = 0.0                      # Positive = rising, negative = falling
    slow_slope: float = 0.0
    cross_detected: bool = False
    cross_direction: Optional[str] = None        # "bullish" or "bearish"
    cross_age: int = 999
    both_sloping_up: bool = False
    both_sloping_down: bool = False
    both_flat: bool = False
    price_above_both: bool = False
    price_below_both: bool = False
    price_trapped: bool = False                  # Price between fast and slow
    distance_expanding: bool = False             # SMA gap expanding after cross
    compression_detected: bool = False           # Tightly compressed
    confirmed: bool = False
    contradiction: bool = False


@dataclass
class ConsolidationResult:
    """Consolidation detection result."""
    consolidating: bool = False
    confidence: float = 0.0                      # 0-1
    atr_ratio: float = 0.0
    sma_distance: float = 0.0
    crossover_frequency: int = 0
    reasons: List[str] = field(default_factory=list)


@dataclass
class EntryZoneResult:
    """Fibonacci retracement entry zone."""
    found: bool = False
    direction: Optional[str] = None
    fib_level: Optional[float] = None
    zone_low: float = 0.0
    zone_high: float = 0.0
    midpoint: float = 0.0
    confluence_types: List[str] = field(default_factory=list)  # e.g. ["fib", "fvg", "order_block"]
    quality_score: float = 0.0                    # 0-1
    price_in_zone: bool = False
    retracement_ratio: float = 0.0               # How far price retraced (0.0 = none, 1.0 = full)


@dataclass
class FallbackSetupResult:
    """Complete result from Fallback 3 analysis."""
    symbol: str = ""
    direction: Optional[str] = None               # "buy" / "sell" / None
    executable: bool = False                      # Can we trade?
    reason: str = ""
    states: List[Dict[str, Any]] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    score: int = 0
    score_components: Dict[str, int] = field(default_factory=dict)

    # Core analysis
    htf_bias: Optional[str] = None                # "bullish" / "bearish" / "neutral"
    htf_bias_confidence: float = 0.0

    # Liquidity
    sweep: SweepResult = field(default_factory=SweepResult)
    choch: CHOCHResult = field(default_factory=CHOCHResult)

    # Indicators
    macd: MACDResult = field(default_factory=MACDResult)
    sma: SMAResult = field(default_factory=SMAResult)
    consolidation: ConsolidationResult = field(default_factory=ConsolidationResult)

    # Entry
    entry_zone: EntryZoneResult = field(default_factory=EntryZoneResult)
    entry_price: Optional[float] = None
    entry_trigger: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward: float = 0.0
    position_size: float = 0.0

    # Strategy context
    strategy_1_result: str = ""
    strategy_1_reason: str = ""
    strategy_2_result: str = ""
    strategy_2_reason: str = ""
    setup_id: str = ""
    activated: bool = False
    rejection_reason: str = ""
    failed_stage: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging and API."""
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "executable": self.executable,
            "reason": self.reason,
            "score": self.score,
            "score_components": self.score_components,
            "states": self.states,
            "htf_bias": self.htf_bias,
            "htf_bias_confidence": self.htf_bias_confidence,
            "sweep_classification": self.sweep.classification,
            "sweep_detected": self.sweep.detected,
            "choch_detected": self.choch.detected,
            "choch_direction": self.choch.direction,
            "macd_confirmed": self.macd.confirmed,
            "macd_contradiction": self.macd.contradiction,
            "sma_confirmed": self.sma.confirmed,
            "sma_contradiction": self.sma.contradiction,
            "consolidating": self.consolidation.consolidating,
            "entry_zone_found": self.entry_zone.found,
            "entry_price": self.entry_price,
            "entry_trigger": self.entry_trigger,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward": self.risk_reward,
            "position_size": self.position_size,
            "strategy_1_result": self.strategy_1_result,
            "strategy_1_reason": self.strategy_1_reason,
            "strategy_2_result": self.strategy_2_result,
            "strategy_2_reason": self.strategy_2_reason,
            "setup_id": self.setup_id,
            "activated": self.activated,
            "rejection_reason": self.rejection_reason,
            "failed_stage": self.failed_stage,
        }


@dataclass
class FallbackTradeRequest:
    """Trade request output from Fallback 3, compatible with main.py execution pipeline."""
    symbol: str
    direction: str
    entry: float
    sl: float
    tp: float
    lot: float
    order_type: str = "market"
    strategy: str = "fallback3"
    identity: Optional[str] = None
    identity_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "entry": self.entry,
            "sl": self.sl,
            "tp": self.tp,
            "lot": self.lot,
            "order_type": self.order_type,
            "strategy": self.strategy,
            "identity": self.identity,
            "identity_context": self.identity_context,
        }


def make_state(name: str, confirmed: bool, evidence: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    """Create a standardized state machine step."""
    return {
        "name": name,
        "confirmed": bool(confirmed),
        "evidence": evidence or {},
        "reason": reason or "",
    }
