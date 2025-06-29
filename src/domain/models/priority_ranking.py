"""
Priority ranking domain models
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Any, Optional

from src.domain.models.scoring import ScoringResult, ConfidenceLevel, PatternType


class ExclusionReason(str, Enum):
    """Reasons for signal exclusion"""
    CORRELATION_SAME_DIRECTION = "correlation_same_direction"
    CORRELATION_STOP_LOSS_OVERLAP = "correlation_stop_loss_overlap"
    POSITION_LIMIT_EXCEEDED = "position_limit_exceeded"
    PATTERN_DIVERSITY_CONFLICT = "pattern_diversity_conflict"
    TIMEFRAME_CONFLICT = "timeframe_conflict"
    LOW_QUALITY_SCORE = "low_quality_score"


class SignalStatus(str, Enum):
    """Signal processing status"""
    PRIORITIZED = "prioritized"
    EXCLUDED = "excluded"
    PENDING = "pending"


@dataclass
class EntrySignal:
    """Entry signal for prioritization"""
    signal_id: str
    symbol: str
    timestamp: datetime
    pattern_type: PatternType
    timeframe: str
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    scoring_result: ScoringResult
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get confidence level from scoring result"""
        return self.scoring_result.confidence_level
    
    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk-reward ratio"""
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        return float(reward / risk) if risk > 0 else 0.0
    
    @property
    def composite_score(self) -> float:
        """Get composite score from scoring result"""
        return self.scoring_result.total_score


@dataclass
class ExistingPosition:
    """Current open position"""
    position_id: str
    symbol: str
    direction: str  # "long" or "short"
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    timeframe: str
    pattern_type: PatternType


@dataclass
class CorrelationInfo:
    """Correlation information between signals"""
    signal1_id: str
    signal2_id: str
    correlation_type: ExclusionReason
    distance_pips: float
    description: str


@dataclass
class PrioritizedSignal:
    """Prioritized signal with ranking information"""
    signal: EntrySignal
    priority_rank: int
    priority_score: float
    ranking_reasons: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            'signal_id': self.signal.signal_id,
            'symbol': self.signal.symbol,
            'pattern_type': self.signal.pattern_type.value,
            'timeframe': self.signal.timeframe,
            'priority_rank': self.priority_rank,
            'priority_score': self.priority_score,
            'confidence_level': self.signal.confidence_level.value,
            'risk_reward_ratio': self.signal.risk_reward_ratio,
            'composite_score': self.signal.composite_score,
            'entry_price': float(self.signal.entry_price),
            'stop_loss': float(self.signal.stop_loss),
            'take_profit': float(self.signal.take_profit),
            'ranking_reasons': self.ranking_reasons
        }


@dataclass
class ExcludedSignal:
    """Excluded signal with exclusion information"""
    signal: EntrySignal
    exclusion_reason: ExclusionReason
    exclusion_details: str
    correlations: List[CorrelationInfo] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            'signal_id': self.signal.signal_id,
            'symbol': self.signal.symbol,
            'pattern_type': self.signal.pattern_type.value,
            'timeframe': self.signal.timeframe,
            'exclusion_reason': self.exclusion_reason.value,
            'exclusion_details': self.exclusion_details,
            'confidence_level': self.signal.confidence_level.value,
            'risk_reward_ratio': self.signal.risk_reward_ratio,
            'composite_score': self.signal.composite_score,
            'correlations': [
                {
                    'correlated_signal_id': corr.signal2_id if corr.signal1_id == self.signal.signal_id else corr.signal1_id,
                    'correlation_type': corr.correlation_type.value,
                    'distance_pips': corr.distance_pips,
                    'description': corr.description
                }
                for corr in self.correlations
            ]
        }


@dataclass
class PriorityRankingResult:
    """Complete priority ranking result"""
    prioritized_signals: List[PrioritizedSignal]
    excluded_signals: List[ExcludedSignal]
    timestamp: datetime
    
    @property
    def statistics(self) -> Dict[str, Any]:
        """Generate ranking statistics"""
        return {
            'total_signals_processed': len(self.prioritized_signals) + len(self.excluded_signals),
            'prioritized_count': len(self.prioritized_signals),
            'excluded_count': len(self.excluded_signals),
            'average_confidence_level': self._calculate_average_confidence(),
            'average_risk_reward_ratio': self._calculate_average_rr_ratio(),
            'average_composite_score': self._calculate_average_score(),
            'exclusion_reasons_breakdown': self._get_exclusion_breakdown(),
            'pattern_type_distribution': self._get_pattern_distribution(),
            'timeframe_distribution': self._get_timeframe_distribution()
        }
    
    def _calculate_average_confidence(self) -> str:
        """Calculate average confidence level"""
        if not self.prioritized_signals:
            return "N/A"
        
        confidence_scores = {
            ConfidenceLevel.HIGH: 3,
            ConfidenceLevel.MEDIUM: 2,
            ConfidenceLevel.LOW: 1
        }
        
        total = sum(confidence_scores[signal.signal.confidence_level] for signal in self.prioritized_signals)
        avg = total / len(self.prioritized_signals)
        
        if avg >= 2.5:
            return "HIGH"
        elif avg >= 1.5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _calculate_average_rr_ratio(self) -> float:
        """Calculate average risk-reward ratio"""
        if not self.prioritized_signals:
            return 0.0
        
        return sum(signal.signal.risk_reward_ratio for signal in self.prioritized_signals) / len(self.prioritized_signals)
    
    def _calculate_average_score(self) -> float:
        """Calculate average composite score"""
        if not self.prioritized_signals:
            return 0.0
        
        return sum(signal.signal.composite_score for signal in self.prioritized_signals) / len(self.prioritized_signals)
    
    def _get_exclusion_breakdown(self) -> Dict[str, int]:
        """Get breakdown of exclusion reasons"""
        breakdown = {}
        for excluded in self.excluded_signals:
            reason = excluded.exclusion_reason.value
            breakdown[reason] = breakdown.get(reason, 0) + 1
        return breakdown
    
    def _get_pattern_distribution(self) -> Dict[str, int]:
        """Get pattern type distribution for prioritized signals"""
        distribution = {}
        for prioritized in self.prioritized_signals:
            pattern = prioritized.signal.pattern_type.value
            distribution[pattern] = distribution.get(pattern, 0) + 1
        return distribution
    
    def _get_timeframe_distribution(self) -> Dict[str, int]:
        """Get timeframe distribution for prioritized signals"""
        distribution = {}
        for prioritized in self.prioritized_signals:
            timeframe = prioritized.signal.timeframe
            distribution[timeframe] = distribution.get(timeframe, 0) + 1
        return distribution
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            'prioritized_signals': [signal.to_dict() for signal in self.prioritized_signals],
            'excluded_signals': [signal.to_dict() for signal in self.excluded_signals],
            'statistics': self.statistics,
            'timestamp': self.timestamp.isoformat(),
            'processing_summary': {
                'total_processed': self.statistics['total_signals_processed'],
                'final_recommendations': len(self.prioritized_signals),
                'exclusion_rate': f"{(self.statistics['excluded_count'] / max(1, self.statistics['total_signals_processed'])) * 100:.1f}%"
            }
        }


@dataclass
class PriorityRankingConfig:
    """Configuration for priority ranking system"""
    # Correlation detection settings
    same_direction_correlation_threshold_pips: float = 20.0
    stop_loss_overlap_threshold_pips: float = 5.0
    
    # Position limits
    max_positions_same_direction: int = 3
    max_total_positions: int = 5
    
    # Priority scoring weights
    confidence_level_weights: Dict[ConfidenceLevel, float] = field(default_factory=lambda: {
        ConfidenceLevel.HIGH: 1.0,
        ConfidenceLevel.MEDIUM: 0.7,
        ConfidenceLevel.LOW: 0.4
    })
    
    # Risk management
    min_risk_reward_ratio: float = 1.5
    min_composite_score: float = 65.0
    
    # Time decay settings
    enable_time_decay: bool = False
    time_decay_factor_per_minute: float = 0.01
    
    # Pattern complexity scoring (simpler patterns preferred)
    pattern_complexity_scores: Dict[PatternType, float] = field(default_factory=lambda: {
        PatternType.TREND_CONTINUATION: 1.0,     # Simplest
        PatternType.V_SHAPE_REVERSAL: 0.9,
        PatternType.FALSE_BREAKOUT: 0.8,
        PatternType.EMA_SQUEEZE: 0.7             # Most complex
    })
    
    # Diversity bonuses
    timeframe_diversity_bonus: float = 0.1
    pattern_diversity_bonus: float = 0.1