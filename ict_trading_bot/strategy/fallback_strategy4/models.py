"""
FALLBACK STRATEGY 4 - Models
=============================
Data structures for Fallback 4 analysis results and state tracking.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BoundaryZone:
    """A clustered boundary zone of a detected range."""
    price: float                   # Center price of the zone
    zone_low: float                # Lower edge of the zone (price - tolerance)
    zone_high: float               # Upper edge of the zone (price + tolerance)
    interaction_count: int = 0     # Number of candles touching this zone
    swing_prices: List[float] = field(default_factory=list)
    liquidity_quality: float = 0.0  # 0.0 = none, 1.0 = excellent


@dataclass
class RangeResult:
    """Complete range detection result."""
    detected: bool = False
    range_high: float = 0.0          # Confirmed upper boundary price
    range_low: float = 0.0           # Confirmed lower boundary price
    range_width: float = 0.0         # range_high - range_low
    range_midpoint: float = 0.0      # range_low + 0.5 * range_width
    range_25: float = 0.0            # range_low + 0.25 * range_width
    range_75: float = 0.0            # range_low + 0.75 * range_width
    range_width_atr: float = 0.0     # range_width / atr
    start_index: int = -1            # Candle index where range began
    end_index: int = -1              # Candle index where range ended
    duration: int = 0                # Number of candles in range
    upper_zone: Optional[BoundaryZone] = None
    lower_zone: Optional[BoundaryZone] = None
    upper_interactions: int = 0
    lower_interactions: int = 0
    rotations: int = 0               # Alternating touches between boundaries
    quality_score: int = 0           # 0-100
    rejected: bool = False
    rejection_reason: str = ""
    slope: float = 0.0               # Directional slope (positive = bullish bias)
    is_valid: bool = False


@dataclass
class SweepResult:
    """Result of sweep / breakout classification."""
    detected: bool = False
    side: Optional[str] = None        # "sell_side" (swept below) or "buy_side" (swept above)
    direction: str = ""               # "bullish" or "bearish" for the anticipated reversal
    extreme_price: float = 0.0        # Lowest price below range (bullish) or highest above (bearish)
    penetration: float = 0.0          # Absolute distance beyond boundary
    penetration_atr: float = 0.0      # penetration / ATR
    penetration_ratio: float = 0.0    # penetration / range_width
    candles_outside: int = 0          # Candles fully/partially outside range
    max_candles_outside: int = 0
    average_body_outside: float = 0.0
    momentum_decelerated: bool = False
    classification: str = "unknown"   # "sweep", "probable_sweep", "probable_breakout", "genuine_breakout", "uncertain"
    sweep_score: float = 0.0          # 0.0 = breakout, 1.0 = certain sweep
    breakout_score: float = 0.0       # 0.0 = sweep, 1.0 = certain breakout
    failed_outside_acceptance: bool = False


@dataclass
class ReclaimResult:
    """Result of range boundary reclaim analysis."""
    reclaimed: bool = False
    side: Optional[str] = None        # Which side was reclaimed ("sell_side" or "buy_side")
    reclaim_candle_index: int = -1
    reclaim_candle_close: float = 0.0
    reclaim_candle_body_ratio: float = 0.0
    reclaim_strength: float = 0.0     # 0-100
    reclaim_buffer_met: bool = False
    follow_through_confirmed: bool = False
    mode_used: str = "none"
    failure_reason: str = ""


@dataclass
class DisplacementResult:
    """Result of opposing displacement analysis."""
    detected: bool = False
    direction: Optional[str] = None   # Direction of displacement (bullish/bearish)
    candle_index: int = -1
    body_ratio: float = 0.0
    range_atr_ratio: float = 0.0      # Candle range / ATR
    close_position_quality: float = 0.0  # 0.0-1.0 (how close to extreme)
    score: int = 0                     # 0-100
    fvg_created: bool = False          # Fair value gap formed
    swing_broken: bool = False         # Internal swing broken


@dataclass
class StructureChangeResult:
    """Result of CHOCH / BOS confirmation."""
    confirmed: bool = False
    direction: Optional[str] = None   # bullish / bearish
    method: str = ""                   # "choch" or "bos"
    swing_level: float = 0.0
    close_level: float = 0.0
    break_candle_index: int = -1
    body_ratio: float = 0.0
    close_distance_atr: float = 0.0
    invalidated: bool = False
    rejection_reason: str = ""


@dataclass
class EntryResult:
    """Result of entry zone / trigger analysis."""
    confirmed: bool = False
    model: str = ""                    # A/B/C/D
    entry_price: float = 0.0
    zone_low: float = 0.0
    zone_high: float = 0.0
    retracement_ratio: float = 0.0
    fib_level_used: Optional[float] = None
    rejection_reason: str = ""


@dataclass
class RangeTarget:
    """A single range-based take-profit target."""
    level: float
    label: str                         # "tp1", "tp2", "tp3", "final"
    allocation: float = 0.0            # 0.0-100.0
    reached: bool = False


@dataclass
class Fallback4SetupResult:
    """Complete result from Fallback 4 analysis."""
    symbol: str = ""
    direction: Optional[str] = None
    executable: bool = False
    reason: str = ""
    states: List[Dict[str, Any]] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    score: int = 0
    score_components: Dict[str, int] = field(default_factory=dict)

    # Core analysis
    execution_timeframe: str = "M5"
    context_timeframe: str = "M15"
    context_bias: Optional[str] = None   # "bullish" / "bearish" / "neutral" / "conflicting"

    # Range
    range_data: RangeResult = field(default_factory=RangeResult)

    # Sweep
    sweep: SweepResult = field(default_factory=SweepResult)

    # Reclaim
    reclaim: ReclaimResult = field(default_factory=ReclaimResult)

    # Displacement
    displacement: DisplacementResult = field(default_factory=DisplacementResult)

    # Structure change
    structure_change: StructureChangeResult = field(default_factory=StructureChangeResult)

    # Entry
    entry: EntryResult = field(default_factory=EntryResult)
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_primary: Optional[float] = None
    risk_reward: float = 0.0
    position_size: float = 0.0
    targets: List[RangeTarget] = field(default_factory=list)

    # Strategy priority context
    strategy_1_result: str = ""
    strategy_2_result: str = ""
    fallback_3_result: str = ""
    setup_id: str = ""
    activated: bool = False
    rejection_reason: str = ""
    failed_stage: str = ""

    # Mirror
    source_strategy: str = "fallback4"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging and API."""
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "executable": self.executable,
            "reason": self.reason,
            "strategy": "fallback4",
            "score": self.score,
            "score_components": self.score_components,
            "states": self.states,
            "range_high": self.range_data.range_high,
            "range_low": self.range_data.range_low,
            "range_width": self.range_data.range_width,
            "range_width_atr": self.range_data.range_width_atr,
            "range_quality": self.range_data.quality_score,
            "sweep_side": self.sweep.side,
            "sweep_extreme": self.sweep.extreme_price,
            "sweep_penetration_atr": self.sweep.penetration_atr,
            "sweep_classification": self.sweep.classification,
            "reclaim_status": "confirmed" if self.reclaim.reclaimed else "none",
            "displacement_score": self.displacement.score,
            "choch_status": "confirmed" if self.structure_change.confirmed else "none",
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit_primary,
            "risk_reward": self.risk_reward,
            "position_size": self.position_size,
            "targets": [(t.label, t.level, t.allocation) for t in self.targets],
            "setup_id": self.setup_id,
            "activated": self.activated,
            "rejection_reason": self.rejection_reason,
            "failed_stage": self.failed_stage,
        }


@dataclass
class Fallback4TradeRequest:
    """Trade request output from Fallback 4."""
    symbol: str
    direction: str
    entry: float
    sl: float
    tp: float
    lot: float
    order_type: str = "market"
    strategy: str = "fallback4"
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
