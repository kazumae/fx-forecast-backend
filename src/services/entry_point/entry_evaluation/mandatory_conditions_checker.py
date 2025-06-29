"""
Mandatory Conditions Checker

Validates that entry signals meet all required conditions before allowing trades.
Checks trend alignment, zone relationship, risk-reward ratio, and market session.
"""
from datetime import datetime, time
from decimal import Decimal
from typing import List, Dict, Any
import asyncio

from src.domain.models.entry_evaluation import (
    ConditionResult, ConditionType, MandatoryConditionsResult,
    EntryContext, ConditionConfig, TrendDirection, MarketSession
)


class MandatoryConditionsChecker:
    """Checker for mandatory entry conditions"""
    
    def __init__(self, config: ConditionConfig = None):
        """Initialize with configuration"""
        self.config = config or ConditionConfig()
    
    async def check_all_conditions(self, context: EntryContext) -> MandatoryConditionsResult:
        """Check all mandatory conditions"""
        # Run all checks in parallel for performance
        tasks = [
            self._check_trend_alignment(context),
            self._check_zone_relationship(context),
            self._check_risk_reward_ratio(context),
            self._check_market_session(context)
        ]
        
        condition_results = await asyncio.gather(*tasks)
        
        # Determine if all conditions are met
        all_passed = all(result.passed for result in condition_results)
        
        # Generate rejection reason if any condition failed
        rejection_reason = None
        if not all_passed:
            failed_conditions = [r for r in condition_results if not r.passed]
            rejection_reason = self._generate_rejection_reason(failed_conditions)
        
        return MandatoryConditionsResult(
            all_conditions_met=all_passed,
            conditions=condition_results,
            rejection_reason=rejection_reason
        )
    
    async def _check_trend_alignment(self, context: EntryContext) -> ConditionResult:
        """Check multi-timeframe trend alignment"""
        current_tf_trend = None
        higher_tf_trends = []
        
        # Find current timeframe trend
        for trend in context.trends:
            if trend.timeframe == context.current_timeframe:
                current_tf_trend = trend
            elif trend.timeframe in self.config.higher_timeframes:
                higher_tf_trends.append(trend)
        
        if not current_tf_trend:
            return ConditionResult(
                condition_type=ConditionType.TREND_ALIGNMENT,
                passed=False,
                score=0.0,
                details="現在時間軸のトレンドデータが不足"
            )
        
        if not higher_tf_trends:
            return ConditionResult(
                condition_type=ConditionType.TREND_ALIGNMENT,
                passed=False,
                score=0.0,
                details="上位時間軸のトレンドデータが不足"
            )
        
        # Calculate alignment score
        alignment_score = self._calculate_trend_alignment_score(
            current_tf_trend, higher_tf_trends
        )
        
        passed = alignment_score >= self.config.min_trend_alignment_score
        
        # Generate details
        higher_tf_details = [f"{t.timeframe}:{t.direction.value}" for t in higher_tf_trends]
        details = f"現在足:{current_tf_trend.direction.value}, 上位足:[{', '.join(higher_tf_details)}], スコア:{alignment_score:.2f}"
        
        return ConditionResult(
            condition_type=ConditionType.TREND_ALIGNMENT,
            passed=passed,
            score=alignment_score,
            details=details,
            metadata={
                'current_trend': current_tf_trend.direction.value,
                'higher_trends': [t.direction.value for t in higher_tf_trends],
                'threshold': self.config.min_trend_alignment_score
            }
        )
    
    async def _check_zone_relationship(self, context: EntryContext) -> ConditionResult:
        """Check relationship with nearest zone"""
        distance = context.nearest_zone_distance
        zone_strength = context.nearest_zone_strength
        
        # Calculate zone relationship score
        if distance <= self.config.zone_proximity_threshold:
            # Very close to zone - excellent
            base_score = 1.0
            proximity_level = "至近"
        elif distance <= self.config.zone_acceptable_threshold:
            # Within acceptable range
            base_score = 0.8 - (float(distance - self.config.zone_proximity_threshold) / 
                               float(self.config.zone_acceptable_threshold - self.config.zone_proximity_threshold)) * 0.3
            proximity_level = "許容範囲"
        else:
            # Too far from zone
            base_score = 0.0
            proximity_level = "遠すぎる"
        
        # Adjust score based on zone strength
        strength_multiplier = {
            'S': 1.0,    # Strong zones get full score
            'A': 0.9,    # Good zones get slight reduction
            'B': 0.8,    # Weaker zones get more reduction
            'C': 0.7     # Weak zones get significant reduction
        }.get(zone_strength, 0.5)
        
        final_score = base_score * strength_multiplier
        
        # Condition passes if distance is within acceptable range
        passed = distance <= self.config.zone_acceptable_threshold
        
        details = f"{zone_strength}級ゾーンから{float(distance):.1f}pips ({proximity_level})"
        
        return ConditionResult(
            condition_type=ConditionType.ZONE_RELATIONSHIP,
            passed=passed,
            score=final_score,
            details=details,
            metadata={
                'distance_pips': float(distance),
                'zone_strength': zone_strength,
                'proximity_threshold': float(self.config.zone_proximity_threshold),
                'acceptable_threshold': float(self.config.zone_acceptable_threshold)
            }
        )
    
    async def _check_risk_reward_ratio(self, context: EntryContext) -> ConditionResult:
        """Check risk-reward ratio"""
        rr_ratio = context.risk_reward_ratio
        
        # Score based on how much the RR ratio exceeds minimum
        if rr_ratio >= self.config.min_risk_reward_ratio:
            # Calculate bonus score for higher RR ratios
            excess_ratio = rr_ratio - self.config.min_risk_reward_ratio
            bonus = min(excess_ratio * 0.1, 0.3)  # Up to 0.3 bonus
            score = min(1.0, 0.7 + bonus)
        else:
            # Proportional score for insufficient RR ratio
            score = rr_ratio / self.config.min_risk_reward_ratio * 0.5
        
        passed = rr_ratio >= self.config.min_risk_reward_ratio
        
        details = f"RR比 1:{rr_ratio:.1f} (必要 1:{self.config.min_risk_reward_ratio})"
        if not passed:
            details += " - 基準未満"
        
        return ConditionResult(
            condition_type=ConditionType.RISK_REWARD_RATIO,
            passed=passed,
            score=score,
            details=details,
            metadata={
                'risk_reward_ratio': rr_ratio,
                'min_required': self.config.min_risk_reward_ratio,
                'risk_pips': float(context.risk_amount),
                'reward_pips': float(context.reward_amount)
            }
        )
    
    async def _check_market_session(self, context: EntryContext) -> ConditionResult:
        """Check market session timing"""
        current_session = context.current_session
        
        # Score based on session preference
        if current_session in self.config.preferred_sessions:
            if current_session == MarketSession.OVERLAP_LONDON_NY:
                score = 1.0  # Best session
            elif current_session in [MarketSession.LONDON, MarketSession.NEW_YORK]:
                score = 0.9  # Good sessions
            else:
                score = 0.7  # Acceptable
        else:
            if current_session == MarketSession.TOKYO:
                score = 0.6  # Tokyo can be acceptable
            else:
                score = 0.3  # Quiet session
        
        passed = score >= self.config.min_session_score
        
        # Generate session description
        session_names = {
            MarketSession.TOKYO: "東京時間",
            MarketSession.LONDON: "ロンドン時間",
            MarketSession.NEW_YORK: "ニューヨーク時間",
            MarketSession.OVERLAP_LONDON_NY: "ロンドン・NY重複時間",
            MarketSession.QUIET: "閑散時間"
        }
        
        session_desc = session_names.get(current_session, current_session.value)
        recommendation = "推奨" if passed else "非推奨"
        
        details = f"{session_desc} ({recommendation})"
        
        return ConditionResult(
            condition_type=ConditionType.MARKET_SESSION,
            passed=passed,
            score=score,
            details=details,
            metadata={
                'current_session': current_session.value,
                'preferred_sessions': [s.value for s in self.config.preferred_sessions],
                'min_score': self.config.min_session_score
            }
        )
    
    def _calculate_trend_alignment_score(
        self, 
        current_trend, 
        higher_trends: List
    ) -> float:
        """Calculate trend alignment score"""
        if not higher_trends:
            return 0.0
        
        aligned_count = 0
        total_weight = 0
        
        for trend in higher_trends:
            # Weight higher timeframes more heavily
            weight = self._get_timeframe_weight(trend.timeframe)
            total_weight += weight
            
            # Check alignment
            if current_trend.direction == trend.direction:
                # Perfect alignment gets full weight
                aligned_count += weight * trend.strength
            elif current_trend.direction == TrendDirection.RANGE or trend.direction == TrendDirection.RANGE:
                # Range is partially aligned
                aligned_count += weight * 0.3
            # Opposite direction gets 0 points
        
        if total_weight == 0:
            return 0.0
        
        return min(1.0, aligned_count / total_weight)
    
    def _get_timeframe_weight(self, timeframe: str) -> float:
        """Get weight for timeframe in alignment calculation"""
        weights = {
            '15m': 1.0,
            '1h': 1.5,
            '4h': 2.0,
            '1d': 2.5
        }
        return weights.get(timeframe, 1.0)
    
    def _generate_rejection_reason(self, failed_conditions: List[ConditionResult]) -> str:
        """Generate human-readable rejection reason"""
        if len(failed_conditions) == 1:
            condition = failed_conditions[0]
            reasons = {
                ConditionType.TREND_ALIGNMENT: "上位時間軸とのトレンド整合性が不足",
                ConditionType.ZONE_RELATIONSHIP: "ゾーンから距離が離れすぎ",
                ConditionType.RISK_REWARD_RATIO: "リスクリワード比が基準未満",
                ConditionType.MARKET_SESSION: "取引に適さない時間帯"
            }
            return reasons.get(condition.condition_type, "条件未達成")
        else:
            # Multiple failed conditions
            condition_names = {
                ConditionType.TREND_ALIGNMENT: "トレンド整合性",
                ConditionType.ZONE_RELATIONSHIP: "ゾーン関係",
                ConditionType.RISK_REWARD_RATIO: "RR比",
                ConditionType.MARKET_SESSION: "時間帯"
            }
            
            failed_names = [
                condition_names.get(c.condition_type, c.condition_type.value) 
                for c in failed_conditions
            ]
            
            return f"複数条件未達成: {', '.join(failed_names)}"
    
    def get_market_session(self, timestamp: datetime) -> MarketSession:
        """Determine market session based on timestamp (UTC)"""
        utc_time = timestamp.time()
        
        # Session times in UTC
        # Tokyo: 00:00-09:00 UTC
        # London: 08:00-17:00 UTC  
        # New York: 13:00-22:00 UTC
        
        tokyo_start = time(0, 0)
        tokyo_end = time(9, 0)
        london_start = time(8, 0)
        london_end = time(17, 0)
        ny_start = time(13, 0)
        ny_end = time(22, 0)
        
        # Check for overlaps first
        if london_start <= utc_time <= london_end and ny_start <= utc_time <= ny_end:
            return MarketSession.OVERLAP_LONDON_NY
        
        # Individual sessions
        if london_start <= utc_time <= london_end:
            return MarketSession.LONDON
        elif ny_start <= utc_time <= ny_end:
            return MarketSession.NEW_YORK
        elif tokyo_start <= utc_time <= tokyo_end:
            return MarketSession.TOKYO
        else:
            return MarketSession.QUIET