from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any


class CalculationMethod(Enum):
    """価格計算方法"""
    ZONE_BASED = "zone_based"
    SWING_BASED = "swing_based"
    ATR_BASED = "atr_based"
    FIXED_PIPS = "fixed_pips"
    HYBRID = "hybrid"


class AdjustmentType(Enum):
    """調整タイプ"""
    VOLATILITY = "volatility"
    SESSION = "session"
    NEWS = "news"
    CORRELATION = "correlation"


@dataclass
class StopLossCalculation:
    """ストップロス計算結果"""
    price: Decimal
    distance_pips: float
    calculation_method: CalculationMethod
    details: str
    zone_reference: Optional[str] = None
    swing_reference: Optional[str] = None
    atr_factor: Optional[float] = None
    
    def is_valid(self, min_pips: float = 10.0, max_pips: float = 50.0) -> bool:
        """有効なSL設定かチェック"""
        return min_pips <= self.distance_pips <= max_pips


@dataclass
class TakeProfitLevel:
    """テイクプロフィットレベル"""
    level: int
    price: Decimal
    distance_pips: float
    percentage: float  # 決済割合
    reason: str
    zone_reference: Optional[str] = None
    psychological_level: Optional[Decimal] = None
    fibonacci_level: Optional[float] = None


@dataclass
class RiskRewardAnalysis:
    """リスクリワード分析結果"""
    risk_amount: float  # リスクpips
    reward_tp1: float
    reward_tp2: Optional[float]
    reward_tp3: Optional[float]
    rr_ratio_tp1: float
    rr_ratio_weighted: float  # 加重平均RR比
    meets_minimum: bool
    recommended_adjustment: Optional[str] = None


@dataclass
class PriceAdjustments:
    """価格調整情報"""
    volatility_factor: float = 1.0
    session_factor: float = 1.0
    news_factor: float = 1.0
    final_multiplier: float = 1.0
    adjustment_reasons: List[str] = None
    
    def __post_init__(self):
        if self.adjustment_reasons is None:
            self.adjustment_reasons = []
        self.final_multiplier = self.volatility_factor * self.session_factor * self.news_factor


@dataclass
class PriceCalculationResult:
    """価格計算の総合結果"""
    stop_loss: StopLossCalculation
    take_profits: List[TakeProfitLevel]
    risk_reward_analysis: RiskRewardAnalysis
    adjustments: PriceAdjustments
    calculated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "stop_loss": {
                "price": float(self.stop_loss.price),
                "distance_pips": self.stop_loss.distance_pips,
                "calculation_method": self.stop_loss.calculation_method.value,
                "details": self.stop_loss.details
            },
            "take_profits": [
                {
                    "level": tp.level,
                    "price": float(tp.price),
                    "distance_pips": tp.distance_pips,
                    "percentage": tp.percentage,
                    "reason": tp.reason
                }
                for tp in self.take_profits
            ],
            "risk_reward_analysis": {
                "risk_amount": self.risk_reward_analysis.risk_amount,
                "reward_tp1": self.risk_reward_analysis.reward_tp1,
                "reward_tp2": self.risk_reward_analysis.reward_tp2,
                "reward_tp3": self.risk_reward_analysis.reward_tp3,
                "rr_ratio_tp1": self.risk_reward_analysis.rr_ratio_tp1,
                "rr_ratio_weighted": self.risk_reward_analysis.rr_ratio_weighted,
                "meets_minimum": self.risk_reward_analysis.meets_minimum
            },
            "adjustments": {
                "volatility_factor": self.adjustments.volatility_factor,
                "session_factor": self.adjustments.session_factor,
                "final_multiplier": self.adjustments.final_multiplier
            }
        }


@dataclass
class PriceCalculationInput:
    """価格計算の入力パラメータ"""
    entry_price: Decimal
    pattern_type: str
    current_atr: float
    zone_info: Dict[str, Any]
    volatility_level: str = "normal"  # low, normal, high
    existing_positions: List[Dict[str, Any]] = None
    market_session: str = "london"  # asian, london, newyork
    news_impact: bool = False