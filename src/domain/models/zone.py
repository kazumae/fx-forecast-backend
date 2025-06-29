"""ゾーン関連のドメインモデル"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any


class ZoneType(Enum):
    """ゾーンタイプ"""
    SUPPORT = "support"
    RESISTANCE = "resistance"
    NEUTRAL = "neutral"


class ZoneStatus(Enum):
    """ゾーンステータス"""
    ACTIVE = "active"
    BROKEN = "broken"
    INACTIVE = "inactive"
    PENDING = "pending"


@dataclass
class Zone:
    """価格ゾーン"""
    id: str
    symbol: str
    upper_bound: Decimal
    lower_bound: Decimal
    zone_type: ZoneType
    strength: float  # 0.0 - 1.0
    touch_count: int
    status: ZoneStatus
    created_at: datetime
    last_touched: Optional[datetime] = None
    role_history: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.role_history is None:
            self.role_history = []
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def width(self) -> Decimal:
        """ゾーン幅を計算"""
        return self.upper_bound - self.lower_bound
    
    @property
    def center(self) -> Decimal:
        """ゾーンの中心価格"""
        return (self.upper_bound + self.lower_bound) / 2
    
    def contains_price(self, price: Decimal) -> bool:
        """価格がゾーン内にあるか判定"""
        return self.lower_bound <= price <= self.upper_bound
    
    def distance_to_price(self, price: Decimal) -> Decimal:
        """価格からゾーンまでの最小距離"""
        if self.contains_price(price):
            return Decimal("0")
        
        if price < self.lower_bound:
            return self.lower_bound - price
        else:
            return price - self.upper_bound
    
    def proximity_score(self, price: Decimal, max_distance: Decimal = Decimal("50")) -> float:
        """価格の近接度スコア（0-1）"""
        distance = self.distance_to_price(price)
        if distance >= max_distance:
            return 0.0
        return float(1 - distance / max_distance)
    
    def is_recently_touched(self, hours: int = 24) -> bool:
        """最近タッチされたか"""
        if not self.last_touched:
            return False
        
        from datetime import timezone
        now = datetime.now(timezone.utc)
        time_diff = now - self.last_touched
        return time_diff.total_seconds() < hours * 3600