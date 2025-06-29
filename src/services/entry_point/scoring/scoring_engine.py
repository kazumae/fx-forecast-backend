"""
Scoring Engine

Evaluates trading patterns and market conditions to generate a 0-100 score.
Passes signals with 65+ points, providing quantitative entry prioritization.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any
import asyncio
import math

from src.domain.models.scoring import (
    ScoringResult, ScoreComponent, ScoringContext, ScoringConfig,
    PatternType, ZoneStrength, ConfidenceLevel
)


class ScoringEngine:
    """Main scoring engine for pattern evaluation"""
    
    def __init__(self, config: ScoringConfig = None):
        """Initialize with configuration"""
        self.config = config or ScoringConfig()
    
    async def calculate_score(self, context: ScoringContext) -> ScoringResult:
        """Calculate complete score for given context"""
        # Run all scoring components in parallel
        tasks = [
            self._score_pattern_strength(context),
            self._score_ma_alignment(context),
            self._score_zone_quality(context),
            self._score_price_action(context),
            self._score_market_environment(context)
        ]
        
        score_components = await asyncio.gather(*tasks)
        
        # Calculate total score
        total_score = sum(component.score for component in score_components)
        
        return ScoringResult(
            total_score=total_score,
            pass_threshold=self.config.pass_threshold,
            passed=total_score >= self.config.pass_threshold,
            score_breakdown=score_components,
            confidence_level=self._determine_confidence_level(total_score),
            timestamp=datetime.utcnow()
        )
    
    async def _score_pattern_strength(self, context: ScoringContext) -> ScoreComponent:
        """Score pattern strength (max 30 points)"""
        pattern = context.pattern_signal
        
        # Get base score for pattern type
        base_score = self.config.pattern_base_scores.get(pattern.pattern_type, 15.0)
        
        # Apply confidence multiplier
        confidence_multiplier = pattern.confidence
        
        # Apply strength multiplier
        strength_multiplier = pattern.strength
        
        # Calculate final score
        final_score = base_score * confidence_multiplier * strength_multiplier
        final_score = min(final_score, self.config.max_pattern_score)
        
        details = f"{pattern.pattern_type.value} (信頼度:{pattern.confidence:.2f}, 強度:{pattern.strength:.2f})"
        
        return ScoreComponent(
            name="パターン強度",
            score=final_score,
            max_score=self.config.max_pattern_score,
            weight=0.3,
            details=details,
            metadata={
                'pattern_type': pattern.pattern_type.value,
                'base_score': base_score,
                'confidence': pattern.confidence,
                'strength': pattern.strength
            }
        )
    
    async def _score_ma_alignment(self, context: ScoringContext) -> ScoreComponent:
        """Score Moving Average alignment (max 20 points)"""
        mas = context.moving_averages
        price = context.current_price
        
        if not mas or len(mas) < 3:
            return ScoreComponent(
                name="MA配置",
                score=0.0,
                max_score=self.config.max_ma_score,
                weight=0.2,
                details="MA データ不足"
            )
        
        # Sort MAs by period
        sorted_mas = sorted(mas, key=lambda x: x.period)
        
        # Check for perfect order
        perfect_order_score = 0.0
        if self._check_perfect_order(sorted_mas, price):
            perfect_order_score = self.config.perfect_order_bonus
        
        # Calculate price position score
        price_position_score = self._calculate_price_position_score(sorted_mas, price)
        
        # Calculate slope consistency score
        slope_score = self._calculate_slope_consistency_score(sorted_mas)
        
        total_score = perfect_order_score + price_position_score + slope_score
        total_score = min(total_score, self.config.max_ma_score)
        
        details = f"Perfect Order: {'有' if perfect_order_score > 0 else '無'}, " \
                 f"価格位置: {price_position_score:.1f}, 傾き: {slope_score:.1f}"
        
        return ScoreComponent(
            name="MA配置",
            score=total_score,
            max_score=self.config.max_ma_score,
            weight=0.2,
            details=details,
            metadata={
                'perfect_order': perfect_order_score > 0,
                'price_position_score': price_position_score,
                'slope_score': slope_score,
                'ma_count': len(sorted_mas)
            }
        )
    
    async def _score_zone_quality(self, context: ScoringContext) -> ScoreComponent:
        """Score zone quality (max 25 points)"""
        zone = context.zone_data
        
        # Base score from zone strength
        strength_multiplier = self.config.zone_strength_multipliers.get(
            zone.strength, 0.5
        )
        base_score = self.config.max_zone_score * strength_multiplier
        
        # Distance penalty
        distance_multiplier = self._calculate_distance_multiplier(zone.distance_pips)
        
        # Time factor (recent touches are better)
        time_multiplier = self._calculate_time_multiplier(zone.last_touch_candles_ago)
        
        final_score = base_score * distance_multiplier * time_multiplier
        final_score = min(final_score, self.config.max_zone_score)
        
        details = f"{zone.strength.value}級ゾーン, 距離:{float(zone.distance_pips):.1f}pips, " \
                 f"前回タッチ:{zone.last_touch_candles_ago}本前"
        
        return ScoreComponent(
            name="ゾーン品質",
            score=final_score,
            max_score=self.config.max_zone_score,
            weight=0.25,
            details=details,
            metadata={
                'zone_strength': zone.strength.value,
                'distance_pips': float(zone.distance_pips),
                'last_touch_candles_ago': zone.last_touch_candles_ago,
                'distance_multiplier': distance_multiplier,
                'time_multiplier': time_multiplier
            }
        )
    
    async def _score_price_action(self, context: ScoringContext) -> ScoreComponent:
        """Score price action patterns (max 15 points)"""
        pa = context.price_action
        
        score = 0.0
        signals = []
        
        # Pinbar scoring
        if pa.has_pinbar:
            pinbar_score = 5.0 + (pa.wick_to_body_ratio * 2.0)
            score += min(pinbar_score, 7.0)
            signals.append("ピンバー")
        
        # Engulfing pattern
        if pa.has_engulfing:
            score += 6.0
            signals.append("エンゴルフィング")
        
        # Momentum candle
        if pa.has_momentum_candle:
            momentum_score = 3.0 + (pa.candle_size_rank * 0.5)
            score += min(momentum_score, 5.0)
            signals.append("モメンタムキャンドル")
        
        # Volume spike bonus
        if pa.volume_spike:
            score += 2.0
            signals.append("ボリューム急増")
        
        final_score = min(score, self.config.max_price_action_score)
        
        details = f"シグナル: {', '.join(signals) if signals else 'なし'}"
        
        return ScoreComponent(
            name="プライスアクション",
            score=final_score,
            max_score=self.config.max_price_action_score,
            weight=0.15,
            details=details,
            metadata={
                'signals': signals,
                'pinbar': pa.has_pinbar,
                'engulfing': pa.has_engulfing,
                'momentum': pa.has_momentum_candle,
                'volume_spike': pa.volume_spike,
                'wick_to_body_ratio': pa.wick_to_body_ratio
            }
        )
    
    async def _score_market_environment(self, context: ScoringContext) -> ScoreComponent:
        """Score market environment (max 10 points)"""
        env = context.market_environment
        
        score = 0.0
        
        # Volatility scoring
        volatility_scores = {
            "low": 2.0,
            "medium": 4.0,
            "high": 3.0  # High volatility gets less score due to risk
        }
        score += volatility_scores.get(env.volatility_level, 2.0)
        
        # Trend strength
        trend_score = env.trend_strength * 3.0
        score += trend_score
        
        # Session overlap bonus
        if env.session_overlap:
            score += 2.0
        
        # News event proximity penalty
        if env.news_event_proximity:
            score -= 1.0
        
        final_score = max(0.0, min(score, self.config.max_market_environment_score))
        
        details = f"ボラ:{env.volatility_level}, トレンド強度:{env.trend_strength:.2f}, " \
                 f"重複セッション:{'有' if env.session_overlap else '無'}"
        
        return ScoreComponent(
            name="市場環境",
            score=final_score,
            max_score=self.config.max_market_environment_score,
            weight=0.1,
            details=details,
            metadata={
                'volatility_level': env.volatility_level,
                'trend_strength': env.trend_strength,
                'session_overlap': env.session_overlap,
                'news_proximity': env.news_event_proximity
            }
        )
    
    def _check_perfect_order(self, sorted_mas: List, price: Decimal) -> bool:
        """Check if MAs are in perfect order"""
        if len(sorted_mas) < 3:
            return False
        
        # Check if MAs are properly ordered (short > medium > long for uptrend)
        for i in range(len(sorted_mas) - 1):
            if sorted_mas[i].value <= sorted_mas[i + 1].value:
                return False
        
        # Check if price is above all MAs for uptrend
        return price > sorted_mas[0].value
    
    def _calculate_price_position_score(self, sorted_mas: List, price: Decimal) -> float:
        """Calculate score based on price position relative to MAs"""
        if not sorted_mas:
            return 0.0
        
        # Count how many MAs price is above
        above_count = sum(1 for ma in sorted_mas if price > ma.value)
        
        # Score proportional to position
        return (above_count / len(sorted_mas)) * 5.0
    
    def _calculate_slope_consistency_score(self, sorted_mas: List) -> float:
        """Calculate score based on MA slope consistency"""
        if len(sorted_mas) < 2:
            return 0.0
        
        # Check if all slopes are in same direction (positive for uptrend)
        positive_slopes = sum(1 for ma in sorted_mas if ma.slope > 0)
        
        if positive_slopes == len(sorted_mas):
            # All slopes positive - perfect
            return 5.0
        elif positive_slopes >= len(sorted_mas) * 0.7:
            # Most slopes positive - good
            return 3.0
        else:
            # Mixed slopes - poor
            return 1.0
    
    def _calculate_distance_multiplier(self, distance_pips: Decimal) -> float:
        """Calculate multiplier based on distance to zone"""
        if distance_pips <= self.config.zone_excellent_distance:
            return 1.0
        elif distance_pips <= self.config.zone_good_distance:
            return 0.8
        elif distance_pips <= self.config.zone_acceptable_distance:
            return 0.5
        else:
            return 0.2
    
    def _calculate_time_multiplier(self, candles_ago: int) -> float:
        """Calculate multiplier based on time since last touch"""
        if candles_ago <= 5:
            return 1.0
        elif candles_ago <= 20:
            return 0.9
        elif candles_ago <= 50:
            return 0.7
        else:
            return 0.5
    
    def _determine_confidence_level(self, score: float) -> ConfidenceLevel:
        """Determine confidence level based on score"""
        if score >= 80:
            return ConfidenceLevel.HIGH
        elif score >= 70:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW