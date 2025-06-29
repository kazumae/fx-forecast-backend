"""
Entry evaluation domain models
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Any, Optional


class ConditionType(str, Enum):
    """Types of mandatory conditions"""
    TREND_ALIGNMENT = "trend_alignment"
    ZONE_RELATIONSHIP = "zone_relationship" 
    RISK_REWARD_RATIO = "risk_reward_ratio"
    MARKET_SESSION = "market_session"


class TrendDirection(str, Enum):
    """Trend direction types"""
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    RANGE = "range"


class MarketSession(str, Enum):
    """Market session types"""
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP_LONDON_NY = "overlap_london_ny"
    QUIET = "quiet"


@dataclass
class ConditionResult:
    """Result of a single condition check"""
    condition_type: ConditionType
    passed: bool
    score: float  # 0.0 - 1.0
    details: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Validate score range"""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.score}")
        
        if self.metadata is None:
            self.metadata = {}


@dataclass
class MandatoryConditionsResult:
    """Result of all mandatory conditions check"""
    all_conditions_met: bool
    conditions: List[ConditionResult]
    rejection_reason: Optional[str] = None
    overall_score: float = 0.0
    
    def __post_init__(self):
        """Calculate overall score"""
        if self.conditions:
            self.overall_score = sum(c.score for c in self.conditions) / len(self.conditions)
    
    @property
    def passed_conditions_count(self) -> int:
        """Count of passed conditions"""
        return sum(1 for c in self.conditions if c.passed)
    
    @property
    def failed_conditions_count(self) -> int:
        """Count of failed conditions"""
        return sum(1 for c in self.conditions if not c.passed)


@dataclass
class TrendData:
    """Multi-timeframe trend data"""
    timeframe: str
    direction: TrendDirection
    strength: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0


@dataclass
class EntryContext:
    """Context data for entry evaluation"""
    symbol: str
    timestamp: datetime
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    pattern_type: str
    pattern_confidence: float
    
    # Multi-timeframe trend data
    current_timeframe: str
    trends: List[TrendData]
    
    # Zone information
    nearest_zone_distance: Decimal
    nearest_zone_strength: str
    
    # Market session
    current_session: MarketSession
    
    @property
    def risk_amount(self) -> Decimal:
        """Calculate risk amount in pips"""
        return abs(self.entry_price - self.stop_loss)
    
    @property
    def reward_amount(self) -> Decimal:
        """Calculate reward amount in pips"""
        return abs(self.take_profit - self.entry_price)
    
    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk:reward ratio"""
        if self.risk_amount == 0:
            return 0.0
        return float(self.reward_amount / self.risk_amount)


@dataclass
class ConditionConfig:
    """Configuration for mandatory conditions"""
    # Trend alignment
    min_trend_alignment_score: float = 0.5
    higher_timeframes: List[str] = None
    
    # Zone relationship
    zone_proximity_threshold: Decimal = Decimal('5')  # pips
    zone_acceptable_threshold: Decimal = Decimal('20')  # pips
    
    # Risk reward ratio
    min_risk_reward_ratio: float = 1.5
    
    # Market session
    preferred_sessions: List[MarketSession] = None
    min_session_score: float = 0.3
    
    def __post_init__(self):
        if self.higher_timeframes is None:
            self.higher_timeframes = ["15m", "1h", "4h"]
        
        if self.preferred_sessions is None:
            self.preferred_sessions = [
                MarketSession.LONDON,
                MarketSession.NEW_YORK,
                MarketSession.OVERLAP_LONDON_NY
            ]