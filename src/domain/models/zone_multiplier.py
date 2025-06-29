from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class PowerLevel(Enum):
    """パワーゾーンの強度レベル"""
    NONE = 0
    WEAK = 1
    MODERATE = 2  
    STRONG = 3
    VERY_STRONG = 4
    EXTREME = 5


class PowerZoneType(Enum):
    """パワーゾーンコンポーネントの種類"""
    EMA_OVERLAP = "ema_overlap"
    ZONE_CLUSTER = "zone_cluster"
    ROLE_REVERSAL = "role_reversal"
    MULTI_TIMEFRAME = "multi_timeframe"


class ExecutionPrivilege(Enum):
    """実行特権の種類"""
    IMMEDIATE_EXECUTION = "immediate_execution"
    BYPASS_CORRELATION = "bypass_correlation"
    QUEUE_PRIORITY = "queue_priority"


@dataclass
class PowerZoneComponent:
    """パワーゾーンを構成するコンポーネント"""
    component_type: PowerZoneType
    strength: float  # 0.0 - 1.0
    multiplier_contribution: float  # このコンポーネントの乗数への寄与
    detected_at: datetime
    details: Dict[str, Any]


@dataclass
class ZoneMultiplierResult:
    """ゾーン掛け算分析の結果"""
    is_power_zone: bool
    power_level: PowerLevel
    components: List[PowerZoneComponent]
    final_multiplier: float  # 最大3.0でキャップ
    enhanced_rr: float  # 強化されたリスクリワード比
    immediate_execution: bool  # 即時実行フラグ
    execution_privileges: List[ExecutionPrivilege]
    confidence_score: float  # 0.0 - 1.0


@dataclass
class MultiplierConfig:
    """ゾーン掛け算システムの設定"""
    # EMA重なり検出設定
    ema_overlap_distance_pips: float = 10.0
    ema_overlap_base_multiplier: float = 1.5
    
    # ゾーンクラスター検出設定  
    cluster_distance_pips: float = 50.0
    cluster_min_zones: int = 3
    cluster_base_multiplier: float = 2.0
    
    # 役割転換設定
    role_reversal_min_changes: int = 2
    role_reversal_base_multiplier: float = 1.3
    
    # 全体制限
    max_total_multiplier: float = 3.0
    immediate_execution_threshold: float = 2.5
    
    # リスクリワード最適化設定
    max_sl_reduction_percent: float = 40.0
    max_tp_extension_percent: float = 200.0


@dataclass 
class MultiplierContext:
    """ゾーン掛け算分析のコンテキスト"""
    target_zone: Any  # ZoneInfo型（循環参照回避のためAny）
    nearby_zones: List[Any]  # List[ZoneInfo]
    ema_values: List[Any]  # List[EMAInfo]
    market_data: Dict[str, Any]
    timeframe: str
    analysis_timestamp: datetime
    config: MultiplierConfig


@dataclass
class RiskRewardAdjustment:
    """リスクリワード調整結果"""
    original_sl_distance: float
    original_tp_distance: float
    optimized_sl_distance: float
    optimized_tp_distance: float
    enhanced_rr_ratio: float
    sl_reduction_percent: float
    tp_extension_percent: float
    confidence_level: float
    next_major_zone_price: Optional[float] = None