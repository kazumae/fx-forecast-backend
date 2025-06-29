"""
Scoring engine domain models
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Any, Optional


class ConfidenceLevel(str, Enum):
    """Confidence levels based on score ranges"""
    HIGH = "high"     # 80+
    MEDIUM = "medium" # 70-79
    LOW = "low"       # 65-69


class PatternType(str, Enum):
    """Pattern types for scoring"""
    V_SHAPE_REVERSAL = "v_shape_reversal"
    EMA_SQUEEZE = "ema_squeeze"
    TREND_CONTINUATION = "trend_continuation"
    FALSE_BREAKOUT = "false_breakout"


class ZoneStrength(str, Enum):
    """Zone strength classifications"""
    S = "S"  # Strong
    A = "A"  # Good
    B = "B"  # Acceptable
    C = "C"  # Weak


@dataclass
class ScoreComponent:
    """Individual score component result"""
    name: str
    score: float
    max_score: float
    weight: float
    details: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate score ranges"""
        if not 0.0 <= self.score <= self.max_score:
            raise ValueError(f"Score {self.score} must be between 0.0 and {self.max_score}")
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"Weight {self.weight} must be between 0.0 and 1.0")


@dataclass
class ScoringResult:
    """Complete scoring result"""
    total_score: float
    pass_threshold: float
    passed: bool
    score_breakdown: List[ScoreComponent]
    confidence_level: ConfidenceLevel
    timestamp: datetime
    
    def __post_init__(self):
        """Calculate derived fields"""
        calculated_total = sum(component.score for component in self.score_breakdown)
        if abs(self.total_score - calculated_total) > 0.01:
            raise ValueError(f"Total score {self.total_score} doesn't match sum of components {calculated_total}")
        
        # Determine confidence level
        if self.total_score >= 80:
            self.confidence_level = ConfidenceLevel.HIGH
        elif self.total_score >= 70:
            self.confidence_level = ConfidenceLevel.MEDIUM
        else:
            self.confidence_level = ConfidenceLevel.LOW
        
        self.passed = self.total_score >= self.pass_threshold


@dataclass
class PatternSignal:
    """Pattern detection signal for scoring"""
    pattern_type: PatternType
    confidence: float  # 0.0 - 1.0
    strength: float    # 0.0 - 1.0
    detected_at: datetime
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MovingAverageData:
    """Moving Average configuration and values"""
    period: int
    value: Decimal
    slope: float  # Angle/direction of MA
    timeframe: str


@dataclass
class ZoneData:
    """Zone information for scoring"""
    strength: ZoneStrength
    distance_pips: Decimal
    last_touch_candles_ago: int
    support_or_resistance: str  # "support" or "resistance"


@dataclass
class PriceActionData:
    """Price action pattern data"""
    has_pinbar: bool = False
    has_engulfing: bool = False
    has_momentum_candle: bool = False
    volume_spike: bool = False
    wick_to_body_ratio: float = 0.0
    candle_size_rank: int = 0  # Relative size compared to recent candles


@dataclass
class MarketEnvironmentData:
    """Market environment information"""
    volatility_level: str  # "low", "medium", "high"
    trend_strength: float  # 0.0 - 1.0
    session_overlap: bool
    news_event_proximity: bool = False


@dataclass
class ScoringContext:
    """Complete context for scoring calculation"""
    symbol: str
    timestamp: datetime
    current_price: Decimal
    
    # Pattern information
    pattern_signal: PatternSignal
    
    # Technical indicators
    moving_averages: List[MovingAverageData]
    
    # Zone information
    zone_data: ZoneData
    
    # Price action
    price_action: PriceActionData
    
    # Market environment
    market_environment: MarketEnvironmentData


@dataclass
class ScoringConfig:
    """Configuration for scoring engine"""
    # Score thresholds
    pass_threshold: float = 65.0
    
    # Maximum scores for each component
    max_pattern_score: float = 30.0
    max_ma_score: float = 20.0
    max_zone_score: float = 25.0
    max_price_action_score: float = 15.0
    max_market_environment_score: float = 10.0
    
    # Pattern base scores
    pattern_base_scores: Dict[PatternType, float] = field(default_factory=lambda: {
        PatternType.V_SHAPE_REVERSAL: 20.0,
        PatternType.EMA_SQUEEZE: 18.0,
        PatternType.TREND_CONTINUATION: 22.0,
        PatternType.FALSE_BREAKOUT: 19.0
    })
    
    # Zone strength multipliers
    zone_strength_multipliers: Dict[ZoneStrength, float] = field(default_factory=lambda: {
        ZoneStrength.S: 1.0,
        ZoneStrength.A: 0.9,
        ZoneStrength.B: 0.7,
        ZoneStrength.C: 0.5
    })
    
    # Distance thresholds for zone scoring
    zone_excellent_distance: Decimal = Decimal('3.0')  # pips
    zone_good_distance: Decimal = Decimal('8.0')       # pips
    zone_acceptable_distance: Decimal = Decimal('20.0') # pips
    
    # MA configuration
    required_ma_periods: List[int] = field(default_factory=lambda: [20, 50, 200])
    perfect_order_bonus: float = 10.0
    
    def __post_init__(self):
        """Validate configuration"""
        total_max = (self.max_pattern_score + self.max_ma_score + 
                    self.max_zone_score + self.max_price_action_score + 
                    self.max_market_environment_score)
        if total_max != 100.0:
            raise ValueError(f"Total maximum scores must equal 100.0, got {total_max}")