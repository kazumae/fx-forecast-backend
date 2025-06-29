"""
Domain models for Zone Multiplier Logic (US-014)

Handles power zone detection and score multiplication effects
when zones overlap with EMA, multiple zones cluster, or show
role reversal history.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from enum import Enum
from decimal import Decimal


class PowerZoneType(Enum):
    """Types of power zone components"""
    ZONE_EMA_OVERLAP = "zone_ema_overlap"
    MULTI_ZONE_CLUSTER = "multi_zone_cluster"
    ROLE_REVERSAL = "role_reversal"
    MULTI_TIMEFRAME = "multi_timeframe"
    PSYCHOLOGICAL_LEVEL = "psychological_level"


class PowerLevel(Enum):
    """Power zone strength levels"""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4
    EXTREME = 5


@dataclass
class ZoneInfo:
    """Zone information for multiplier calculation"""
    zone_id: str
    price_level: Decimal
    zone_type: str  # "support" or "resistance"
    timeframe: str  # "1H", "4H", "1D", etc.
    strength: float  # 0.0-1.0
    role_history: List[str]  # ["support", "resistance", "support"]
    created_at: str
    last_tested: Optional[str] = None
    test_count: int = 0


@dataclass
class EMAInfo:
    """EMA information for overlap detection"""
    period: int  # 20, 75, 200
    value: Decimal
    timeframe: str


@dataclass
class PowerZoneComponent:
    """Individual component contributing to power zone"""
    component_type: PowerZoneType
    zone_id: Optional[str] = None
    zones: Optional[List[str]] = None
    ema_period: Optional[int] = None
    distance: Optional[Decimal] = None
    span: Optional[Decimal] = None  # pips for cluster
    history: Optional[List[str]] = None
    multiplier_contribution: float = 1.0


@dataclass
class ZoneMultiplierResult:
    """Result of zone multiplier calculation"""
    # Zone analysis
    is_power_zone: bool
    power_level: PowerLevel
    components: List[PowerZoneComponent]
    
    # Score multipliers
    base_multiplier: float
    ema_overlap_multiplier: float
    multi_zone_multiplier: float
    role_reversal_multiplier: float
    multi_timeframe_multiplier: float
    final_multiplier: float  # capped at 3.0
    
    # Enhanced scores
    original_zone_score: float
    multiplied_zone_score: float
    total_score_boost: float
    
    # Risk reward enhancement
    original_rr: float
    enhanced_rr: float
    sl_reduction_percent: float
    tp_extension_percent: float
    recommended_size_multiplier: float
    
    # Execution priority
    base_priority: int
    power_zone_boost: int
    final_priority: int
    immediate_execution: bool


@dataclass
class ZoneCluster:
    """Group of zones within close proximity"""
    zones: List[ZoneInfo]
    center_price: Decimal
    span_pips: Decimal
    cluster_strength: float  # combined strength of all zones
    dominant_type: str  # "support" or "resistance"


@dataclass
class MultiplierContext:
    """Context for zone multiplier calculations"""
    target_zone: ZoneInfo
    nearby_zones: List[ZoneInfo]  # within 100 pips
    ema_values: List[EMAInfo]
    current_price: Decimal
    timeframe: str
    psychological_levels: List[Decimal]  # .00, .50 levels
    market_session: str  # "london", "ny", etc.


@dataclass
class MultiplierConfig:
    """Configuration for zone multiplier system"""
    # Multiplier values
    ema_overlap_multiplier: float = 1.5
    multi_zone_multiplier: float = 2.0
    role_reversal_multiplier: float = 1.3
    multi_timeframe_multiplier: float = 1.2
    psychological_level_multiplier: float = 1.1
    
    # Thresholds
    max_multiplier: float = 3.0
    cluster_distance_pips: Decimal = Decimal("50.0")
    ema_overlap_distance_pips: Decimal = Decimal("10.0")
    min_cluster_zones: int = 3
    min_role_reversals: int = 2
    
    # Power level thresholds
    power_level_thresholds: Dict[float, PowerLevel] = None
    
    def __post_init__(self):
        if self.power_level_thresholds is None:
            self.power_level_thresholds = {
                1.0: PowerLevel.WEAK,
                1.5: PowerLevel.MODERATE,
                2.0: PowerLevel.STRONG,
                2.5: PowerLevel.VERY_STRONG,
                3.0: PowerLevel.EXTREME
            }


@dataclass
class RiskRewardAdjustment:
    """Risk reward adjustments for power zones"""
    original_sl_distance: Decimal
    original_tp_distance: Decimal
    original_rr_ratio: float
    
    adjusted_sl_distance: Decimal
    adjusted_tp_distance: Decimal
    enhanced_rr_ratio: float
    
    sl_reduction_pips: Decimal
    tp_extension_pips: Decimal
    confidence_boost: float


# Type aliases for better readability
ZoneScore = float
Multiplier = float
Priority = int
PipDistance = Decimal