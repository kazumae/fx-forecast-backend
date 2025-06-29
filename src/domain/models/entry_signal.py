from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from decimal import Decimal


class SignalDirection(Enum):
    """エントリー方向"""
    LONG = "long"
    SHORT = "short"


class OrderType(Enum):
    """注文タイプ"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class SignalConfidence(Enum):
    """シグナル信頼度レベル"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class EntryOrderInfo:
    """エントリー注文情報"""
    price: Decimal
    type: OrderType
    valid_until: datetime
    slippage_tolerance: float  # pips


@dataclass
class TakeProfitLevel:
    """テイクプロフィットレベル"""
    price: Decimal
    percentage: float  # 0-100


@dataclass
class StopLossInfo:
    """ストップロス情報"""
    price: Decimal
    trailing: bool = False
    trail_distance_pips: Optional[float] = None


@dataclass
class RiskRewardInfo:
    """リスクリワード情報"""
    risk_pips: float
    reward_pips: float
    ratio: float
    risk_amount: Optional[float] = None  # 通貨単位


@dataclass
class ExecutionInfo:
    """実行情報"""
    recommended_size: float  # ロット
    max_risk_amount: float  # USD
    entry_method: str
    urgency: str  # immediate, normal, patient
    special_instructions: Optional[List[str]] = None


@dataclass
class SignalMetadata:
    """シグナルメタデータ"""
    pattern_type: str
    total_score: float
    confidence: SignalConfidence
    priority: int
    detected_patterns: List[str]
    zone_id: Optional[str] = None
    source_indicators: Optional[Dict[str, Any]] = None
    market_conditions: Optional[Dict[str, Any]] = None


@dataclass
class EntrySignal:
    """エントリーシグナル"""
    id: str
    symbol: str
    timestamp: datetime
    direction: SignalDirection
    
    # エントリー情報
    entry: EntryOrderInfo
    
    # ストップロスとテイクプロフィット
    stop_loss: StopLossInfo
    take_profits: List[TakeProfitLevel]
    
    # リスクリワード
    risk_reward: RiskRewardInfo
    
    # メタデータ
    metadata: SignalMetadata
    
    # 実行情報
    execution: ExecutionInfo
    
    # 追加情報
    timeframe: str = "H1"
    created_at: datetime = None
    expires_at: Optional[datetime] = None
    status: str = "pending"
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction.value,
            "entry": {
                "price": float(self.entry.price),
                "type": self.entry.type.value,
                "valid_until": self.entry.valid_until.isoformat(),
                "slippage_tolerance": self.entry.slippage_tolerance
            },
            "stops": {
                "stop_loss": float(self.stop_loss.price),
                "take_profits": [
                    {
                        "price": float(tp.price),
                        "percentage": tp.percentage
                    }
                    for tp in self.take_profits
                ]
            },
            "risk_reward": {
                "risk_pips": self.risk_reward.risk_pips,
                "reward_pips": self.risk_reward.reward_pips,
                "ratio": self.risk_reward.ratio
            },
            "metadata": {
                "pattern_type": self.metadata.pattern_type,
                "total_score": self.metadata.total_score,
                "confidence": self.metadata.confidence.value,
                "priority": self.metadata.priority,
                "detected_patterns": self.metadata.detected_patterns,
                "zone_id": self.metadata.zone_id
            },
            "execution": {
                "recommended_size": self.execution.recommended_size,
                "max_risk_amount": self.execution.max_risk_amount,
                "entry_method": self.execution.entry_method
            }
        }


@dataclass
class SignalValidationResult:
    """シグナル検証結果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    checks_passed: Dict[str, bool]