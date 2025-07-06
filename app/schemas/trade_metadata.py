from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class PatternType(str, Enum):
    """パターンタイプ"""
    POINT_1 = "point_1"  # トレンド初動
    POINT_2 = "point_2"  # トレンド継続
    POINT_3_1 = "point_3_1"  # 上昇→下降（ショート）
    POINT_3_2 = "point_3_2"  # 上昇→下降（ショート）
    POINT_4 = "point_4"  # 押し目買い
    POINT_5 = "point_5"  # 戻り売り
    POINT_6 = "point_6"  # ブレイクアウト
    POINT_7 = "point_7"  # レンジブレイク
    POINT_8 = "point_8"  # マルチタイム
    POINT_9 = "point_9"  # その他のパターン


class TradeOutcome(str, Enum):
    """トレード結果"""
    LONG_SUCCESS = "long_success"
    LONG_FAILURE = "long_failure"
    SHORT_SUCCESS = "short_success"
    SHORT_FAILURE = "short_failure"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class TimeframeStats(BaseModel):
    """時間足別の統計"""
    timeframe: str
    total_trades: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    average_pips: float = 0.0
    average_rr_ratio: float = 0.0  # Risk-Reward ratio


class PatternStats(BaseModel):
    """パターン別の統計"""
    pattern_type: PatternType
    total_occurrences: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    average_score: float = 0.0
    common_timeframes: List[str] = []
    typical_market_conditions: List[str] = []


class CurrencyPairStats(BaseModel):
    """通貨ペア別の統計"""
    currency_pair: str
    total_analyses: int = 0
    total_trades: int = 0
    success_rate: float = 0.0
    best_patterns: List[PatternType] = []
    worst_patterns: List[PatternType] = []
    best_timeframes: List[str] = []
    average_volatility: float = 0.0


class MarketConditionStats(BaseModel):
    """市場状況別の統計"""
    condition_type: str  # "trending_up", "trending_down", "ranging", "volatile"
    success_rate: float = 0.0
    best_patterns: List[PatternType] = []
    recommended_timeframes: List[str] = []
    average_risk_reward: float = 0.0


class TradePatternMetadata(BaseModel):
    """個別トレードパターンのメタデータ"""
    pattern_type: PatternType
    currency_pair: str
    timeframe: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float]
    risk_reward_ratio: float
    market_condition: str
    technical_indicators: Dict[str, Any]  # MA positions, support/resistance levels
    outcome: Optional[TradeOutcome] = None
    actual_pips: Optional[float] = None
    trade_score: Optional[float] = None
    timestamp: datetime
    

class HistoricalPatternSummary(BaseModel):
    """過去のパターン分析サマリー"""
    currency_pair: str
    analysis_period: str  # e.g., "last_30_days", "last_90_days"
    total_patterns_analyzed: int
    
    # パターン別統計
    pattern_stats: List[PatternStats]
    
    # 時間足別統計
    timeframe_stats: List[TimeframeStats]
    
    # 市場状況別統計
    market_condition_stats: List[MarketConditionStats]
    
    # 成功パターンの特徴
    successful_pattern_characteristics: Dict[str, Any]
    
    # 失敗パターンの特徴
    failure_pattern_characteristics: Dict[str, Any]
    
    # 推奨事項
    recommendations: List[str]
    
    # 信頼度スコア（データ量に基づく）
    confidence_score: float
    
    generated_at: datetime


class SimilarPatternMatch(BaseModel):
    """類似パターンのマッチング結果"""
    pattern_id: int
    similarity_score: float  # 0-1
    pattern_type: PatternType
    currency_pair: str
    timeframe: str
    outcome: TradeOutcome
    entry_conditions: Dict[str, Any]
    trade_result: Dict[str, Any]
    key_differences: List[str]
    key_similarities: List[str]
    occurred_at: datetime