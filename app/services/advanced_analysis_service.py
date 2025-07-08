"""Advanced analysis service with volatility and multi-timeframe analysis"""
import re
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import statistics


class TrendDirection(Enum):
    """Trend direction enumeration"""
    STRONG_UP = "strong_up"
    UP = "up"
    SIDEWAYS = "sideways"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


class MarketCondition(Enum):
    """Market condition enumeration"""
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"


@dataclass
class TimeframeTrend:
    """Trend information for a specific timeframe"""
    timeframe: str
    direction: TrendDirection
    strength: float  # 0-1
    ema_alignment: str  # "bullish", "bearish", "mixed"
    distance_from_200ema: float  # in pips
    volatility: float  # ATR-based
    support_levels: List[float]
    resistance_levels: List[float]


@dataclass
class VolatilityAnalysis:
    """Volatility analysis results"""
    current_volatility: float
    average_volatility: float
    volatility_percentile: float  # 0-100
    volatility_trend: str  # "increasing", "decreasing", "stable"
    recommended_stop_distance: float  # in pips
    recommended_target_distance: float  # in pips


@dataclass
class MultiTimeframeAnalysis:
    """Multi-timeframe analysis results"""
    primary_trend: TrendDirection  # Based on higher timeframes
    entry_timeframe_trend: TrendDirection
    execution_timeframe_trend: TrendDirection
    trend_alignment: bool  # True if all timeframes aligned
    pullback_detected: bool
    pullback_quality: float  # 0-1
    entry_zone: Optional[Tuple[float, float]]  # (lower_bound, upper_bound)
    risk_reward_ratio: float


class AdvancedAnalysisService:
    """Service for advanced technical analysis including volatility and multi-timeframe analysis"""
    
    def __init__(self):
        # Timeframe hierarchy for multi-timeframe analysis
        self.timeframe_hierarchy = {
            "1分": 1,
            "5分": 5,
            "15分": 15,
            "30分": 30,
            "1時間": 60,
            "4時間": 240,
            "日足": 1440
        }
        
        # Volatility multipliers for different market conditions
        self.volatility_multipliers = {
            MarketCondition.TRENDING: 1.0,
            MarketCondition.RANGING: 0.8,
            MarketCondition.VOLATILE: 1.5,
            MarketCondition.QUIET: 0.6
        }
    
    def analyze_volatility(self, price_data: Dict[str, Any], timeframe: str) -> VolatilityAnalysis:
        """Analyze market volatility to determine optimal stop loss and take profit distances"""
        
        # Extract ATR (Average True Range) or calculate from price movements
        # This is a simplified calculation - in production, you'd use actual ATR
        recent_ranges = price_data.get("recent_ranges", [])
        if not recent_ranges:
            # Default values if no data available
            recent_ranges = [20, 25, 30, 22, 28, 35, 20, 25]  # Example pip ranges
        
        current_volatility = recent_ranges[-1] if recent_ranges else 25
        average_volatility = statistics.mean(recent_ranges)
        
        # Calculate volatility percentile
        sorted_ranges = sorted(recent_ranges)
        position = sorted_ranges.index(current_volatility) if current_volatility in sorted_ranges else len(sorted_ranges) // 2
        volatility_percentile = (position / len(sorted_ranges)) * 100
        
        # Determine volatility trend
        if len(recent_ranges) >= 3:
            recent_avg = statistics.mean(recent_ranges[-3:])
            older_avg = statistics.mean(recent_ranges[:-3])
            if recent_avg > older_avg * 1.2:
                volatility_trend = "increasing"
            elif recent_avg < older_avg * 0.8:
                volatility_trend = "decreasing"
            else:
                volatility_trend = "stable"
        else:
            volatility_trend = "stable"
        
        # Calculate recommended distances based on volatility
        # Adjust multipliers based on timeframe
        timeframe_multiplier = self._get_timeframe_multiplier(timeframe)
        
        recommended_stop_distance = max(
            current_volatility * 0.8 * timeframe_multiplier,
            15  # Minimum stop distance
        )
        
        recommended_target_distance = max(
            current_volatility * 1.5 * timeframe_multiplier,
            recommended_stop_distance * 1.5  # Minimum 1.5:1 RR
        )
        
        return VolatilityAnalysis(
            current_volatility=current_volatility,
            average_volatility=average_volatility,
            volatility_percentile=volatility_percentile,
            volatility_trend=volatility_trend,
            recommended_stop_distance=round(recommended_stop_distance, 1),
            recommended_target_distance=round(recommended_target_distance, 1)
        )
    
    def analyze_timeframe_trend(self, chart_data: Dict[str, Any], timeframe: str) -> TimeframeTrend:
        """Analyze trend for a specific timeframe"""
        
        # Extract EMA positions (simplified - in production, calculate from price data)
        ema20_position = chart_data.get("ema20", 0)
        ema75_position = chart_data.get("ema75", 0)
        ema200_position = chart_data.get("ema200", 0)
        current_price = chart_data.get("current_price", 0)
        
        # Determine EMA alignment
        if ema20_position > ema75_position > ema200_position:
            ema_alignment = "bullish"
        elif ema20_position < ema75_position < ema200_position:
            ema_alignment = "bearish"
        else:
            ema_alignment = "mixed"
        
        # Calculate distance from 200 EMA
        distance_from_200ema = abs(current_price - ema200_position)
        
        # Determine trend direction based on multiple factors
        price_above_200ema = current_price > ema200_position
        ema_bullish = ema_alignment == "bullish"
        
        if price_above_200ema and ema_bullish:
            direction = TrendDirection.STRONG_UP
            strength = 0.9
        elif price_above_200ema:
            direction = TrendDirection.UP
            strength = 0.7
        elif not price_above_200ema and ema_alignment == "bearish":
            direction = TrendDirection.STRONG_DOWN
            strength = 0.9
        elif not price_above_200ema:
            direction = TrendDirection.DOWN
            strength = 0.7
        else:
            direction = TrendDirection.SIDEWAYS
            strength = 0.5
        
        # Extract support and resistance levels
        support_levels = chart_data.get("support_levels", [])
        resistance_levels = chart_data.get("resistance_levels", [])
        
        # Get volatility for this timeframe
        volatility = chart_data.get("atr", 25)  # Default ATR of 25 pips
        
        return TimeframeTrend(
            timeframe=timeframe,
            direction=direction,
            strength=strength,
            ema_alignment=ema_alignment,
            distance_from_200ema=distance_from_200ema,
            volatility=volatility,
            support_levels=support_levels,
            resistance_levels=resistance_levels
        )
    
    def perform_multi_timeframe_analysis(
        self, 
        timeframe_data: Dict[str, Dict[str, Any]]
    ) -> MultiTimeframeAnalysis:
        """Perform comprehensive multi-timeframe analysis"""
        
        # Analyze each timeframe
        timeframe_trends = {}
        for tf, data in timeframe_data.items():
            timeframe_trends[tf] = self.analyze_timeframe_trend(data, tf)
        
        # Determine primary trend from higher timeframes
        higher_timeframes = ["4時間", "1時間", "日足"]
        primary_trends = []
        for tf in higher_timeframes:
            if tf in timeframe_trends:
                primary_trends.append(timeframe_trends[tf])
        
        if primary_trends:
            # Weight higher timeframes more heavily
            weighted_direction = self._calculate_weighted_trend(primary_trends)
            primary_trend = weighted_direction
        else:
            primary_trend = TrendDirection.SIDEWAYS
        
        # Get entry and execution timeframe trends
        entry_timeframes = ["15分", "5分"]
        execution_timeframes = ["1分", "5分"]
        
        entry_trend = TrendDirection.SIDEWAYS
        for tf in entry_timeframes:
            if tf in timeframe_trends:
                entry_trend = timeframe_trends[tf].direction
                break
        
        execution_trend = TrendDirection.SIDEWAYS
        for tf in execution_timeframes:
            if tf in timeframe_trends:
                execution_trend = timeframe_trends[tf].direction
                break
        
        # Check trend alignment
        trend_alignment = self._check_trend_alignment(
            primary_trend, entry_trend, execution_trend
        )
        
        # Detect pullbacks
        pullback_detected, pullback_quality = self._detect_pullback(
            primary_trend, entry_trend, timeframe_trends
        )
        
        # Determine entry zone
        entry_zone = self._calculate_entry_zone(
            timeframe_trends, primary_trend, pullback_detected
        )
        
        # Calculate risk-reward ratio based on volatility and trend strength
        risk_reward_ratio = self._calculate_risk_reward_ratio(
            timeframe_trends, primary_trend
        )
        
        return MultiTimeframeAnalysis(
            primary_trend=primary_trend,
            entry_timeframe_trend=entry_trend,
            execution_timeframe_trend=execution_trend,
            trend_alignment=trend_alignment,
            pullback_detected=pullback_detected,
            pullback_quality=pullback_quality,
            entry_zone=entry_zone,
            risk_reward_ratio=risk_reward_ratio
        )
    
    def _get_timeframe_multiplier(self, timeframe: str) -> float:
        """Get multiplier based on timeframe"""
        multipliers = {
            "1分": 0.5,
            "5分": 0.7,
            "15分": 1.0,
            "30分": 1.2,
            "1時間": 1.5,
            "4時間": 2.0,
            "日足": 3.0
        }
        return multipliers.get(timeframe, 1.0)
    
    def _calculate_weighted_trend(self, trends: List[TimeframeTrend]) -> TrendDirection:
        """Calculate weighted trend direction from multiple timeframes"""
        if not trends:
            return TrendDirection.SIDEWAYS
        
        # Assign numeric values to trend directions
        direction_values = {
            TrendDirection.STRONG_UP: 2,
            TrendDirection.UP: 1,
            TrendDirection.SIDEWAYS: 0,
            TrendDirection.DOWN: -1,
            TrendDirection.STRONG_DOWN: -2
        }
        
        # Weight by timeframe importance and trend strength
        weighted_sum = 0
        total_weight = 0
        
        for i, trend in enumerate(trends):
            weight = (len(trends) - i) * trend.strength  # Higher timeframes get more weight
            weighted_sum += direction_values[trend.direction] * weight
            total_weight += weight
        
        if total_weight == 0:
            return TrendDirection.SIDEWAYS
        
        average_value = weighted_sum / total_weight
        
        # Convert back to trend direction
        if average_value >= 1.5:
            return TrendDirection.STRONG_UP
        elif average_value >= 0.5:
            return TrendDirection.UP
        elif average_value <= -1.5:
            return TrendDirection.STRONG_DOWN
        elif average_value <= -0.5:
            return TrendDirection.DOWN
        else:
            return TrendDirection.SIDEWAYS
    
    def _check_trend_alignment(
        self, 
        primary: TrendDirection, 
        entry: TrendDirection, 
        execution: TrendDirection
    ) -> bool:
        """Check if trends are aligned across timeframes"""
        up_trends = [TrendDirection.STRONG_UP, TrendDirection.UP]
        down_trends = [TrendDirection.STRONG_DOWN, TrendDirection.DOWN]
        
        if primary in up_trends:
            return entry in up_trends or execution in up_trends
        elif primary in down_trends:
            return entry in down_trends or execution in down_trends
        else:
            return False
    
    def _detect_pullback(
        self, 
        primary_trend: TrendDirection, 
        entry_trend: TrendDirection,
        timeframe_trends: Dict[str, TimeframeTrend]
    ) -> Tuple[bool, float]:
        """Detect if there's a quality pullback for entry"""
        up_trends = [TrendDirection.STRONG_UP, TrendDirection.UP]
        down_trends = [TrendDirection.STRONG_DOWN, TrendDirection.DOWN]
        
        pullback_detected = False
        pullback_quality = 0.0
        
        # Check for pullback conditions
        if primary_trend in up_trends and entry_trend in down_trends:
            # Bullish pullback
            pullback_detected = True
            
            # Assess pullback quality based on:
            # 1. Distance to 200 EMA
            # 2. Support levels nearby
            # 3. Not too deep (preserving trend structure)
            
            quality_factors = []
            
            # Check 200 EMA proximity in lower timeframes
            for tf in ["15分", "5分", "1分"]:
                if tf in timeframe_trends:
                    trend = timeframe_trends[tf]
                    if trend.distance_from_200ema < 50:  # Within 50 pips
                        quality_factors.append(0.8)
                    elif trend.distance_from_200ema < 100:
                        quality_factors.append(0.6)
                    else:
                        quality_factors.append(0.4)
            
            pullback_quality = statistics.mean(quality_factors) if quality_factors else 0.5
            
        elif primary_trend in down_trends and entry_trend in up_trends:
            # Bearish pullback
            pullback_detected = True
            
            quality_factors = []
            for tf in ["15分", "5分", "1分"]:
                if tf in timeframe_trends:
                    trend = timeframe_trends[tf]
                    if trend.distance_from_200ema < 50:
                        quality_factors.append(0.8)
                    elif trend.distance_from_200ema < 100:
                        quality_factors.append(0.6)
                    else:
                        quality_factors.append(0.4)
            
            pullback_quality = statistics.mean(quality_factors) if quality_factors else 0.5
        
        return pullback_detected, pullback_quality
    
    def _calculate_entry_zone(
        self, 
        timeframe_trends: Dict[str, TimeframeTrend],
        primary_trend: TrendDirection,
        pullback_detected: bool
    ) -> Optional[Tuple[float, float]]:
        """Calculate optimal entry zone based on analysis"""
        # Get current price from lowest timeframe available
        current_price = None
        for tf in ["1分", "5分", "15分"]:
            if tf in timeframe_trends:
                # In production, this would come from actual chart data
                current_price = 150.00  # Example for USD/JPY
                break
        
        if not current_price:
            return None
        
        up_trends = [TrendDirection.STRONG_UP, TrendDirection.UP]
        down_trends = [TrendDirection.STRONG_DOWN, TrendDirection.DOWN]
        
        # Calculate entry zone based on trend and pullback
        if primary_trend in up_trends:
            if pullback_detected:
                # Entry zone is below current price (buying the dip)
                lower_bound = current_price - 0.30  # 30 pips below
                upper_bound = current_price - 0.10  # 10 pips below
            else:
                # Breakout entry
                lower_bound = current_price
                upper_bound = current_price + 0.20  # 20 pips above
        elif primary_trend in down_trends:
            if pullback_detected:
                # Entry zone is above current price (selling the rally)
                lower_bound = current_price + 0.10  # 10 pips above
                upper_bound = current_price + 0.30  # 30 pips above
            else:
                # Breakdown entry
                lower_bound = current_price - 0.20  # 20 pips below
                upper_bound = current_price
        else:
            # Ranging market - no clear entry zone
            return None
        
        return (lower_bound, upper_bound)
    
    def _calculate_risk_reward_ratio(
        self, 
        timeframe_trends: Dict[str, TimeframeTrend],
        primary_trend: TrendDirection
    ) -> float:
        """Calculate recommended risk-reward ratio based on market conditions"""
        # Base risk-reward ratio
        base_rr = 1.5
        
        # Adjust based on trend strength
        if primary_trend in [TrendDirection.STRONG_UP, TrendDirection.STRONG_DOWN]:
            base_rr = 2.0  # Strong trends allow for better RR
        elif primary_trend == TrendDirection.SIDEWAYS:
            base_rr = 1.2  # Ranging markets have limited profit potential
        
        # Adjust based on volatility
        volatilities = []
        for trend in timeframe_trends.values():
            volatilities.append(trend.volatility)
        
        if volatilities:
            avg_volatility = statistics.mean(volatilities)
            if avg_volatility > 40:  # High volatility
                base_rr *= 1.2
            elif avg_volatility < 20:  # Low volatility
                base_rr *= 0.8
        
        return round(base_rr, 1)
    
    def generate_enhanced_analysis_prompt(
        self,
        volatility_analysis: VolatilityAnalysis,
        mtf_analysis: MultiTimeframeAnalysis
    ) -> str:
        """Generate enhanced prompt with volatility and MTF analysis"""
        
        trend_descriptions = {
            TrendDirection.STRONG_UP: "強い上昇トレンド",
            TrendDirection.UP: "上昇トレンド",
            TrendDirection.SIDEWAYS: "レンジ相場",
            TrendDirection.DOWN: "下降トレンド",
            TrendDirection.STRONG_DOWN: "強い下降トレンド"
        }
        
        prompt = f"""
【高度な市場分析結果】

■ ボラティリティ分析
現在のボラティリティ: {volatility_analysis.current_volatility:.1f} pips
平均ボラティリティ: {volatility_analysis.average_volatility:.1f} pips
ボラティリティパーセンタイル: {volatility_analysis.volatility_percentile:.0f}%
ボラティリティトレンド: {volatility_analysis.volatility_trend}
推奨損切り幅: {volatility_analysis.recommended_stop_distance:.1f} pips
推奨利確幅: {volatility_analysis.recommended_target_distance:.1f} pips

■ マルチタイムフレーム分析
上位足トレンド: {trend_descriptions[mtf_analysis.primary_trend]}
エントリー足トレンド: {trend_descriptions[mtf_analysis.entry_timeframe_trend]}
執行足トレンド: {trend_descriptions[mtf_analysis.execution_timeframe_trend]}
トレンド整合性: {'整合' if mtf_analysis.trend_alignment else '不整合'}
押し目/戻り検出: {'検出' if mtf_analysis.pullback_detected else '未検出'}
"""
        
        if mtf_analysis.pullback_detected:
            prompt += f"押し目/戻り品質: {mtf_analysis.pullback_quality:.0%}\n"
        
        if mtf_analysis.entry_zone:
            prompt += f"推奨エントリーゾーン: {mtf_analysis.entry_zone[0]:.2f} - {mtf_analysis.entry_zone[1]:.2f}\n"
        
        prompt += f"推奨リスクリワード比: 1:{mtf_analysis.risk_reward_ratio}\n"
        
        prompt += """
【重要】この高度な分析を考慮して、以下の点を必ず含めてください：
1. ボラティリティに基づいた適切な損切り・利確設定
2. 上位足のトレンド方向に沿ったエントリー（逆張りは避ける）
3. 押し目買い・戻り売りの機会を優先的に検討
4. トレンドが不整合の場合は様子見を推奨
"""
        
        return prompt