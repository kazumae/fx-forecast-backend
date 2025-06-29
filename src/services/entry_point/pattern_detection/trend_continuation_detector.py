"""
Trend Continuation Pattern Detector

Detects pullback patterns in uptrends where price temporarily corrects towards 200EMA
before resuming the trend, providing high-probability trend-following opportunities.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import math
import uuid

from src.domain.models.pattern import PatternSignal, PatternType
from src.domain.models.market import MarketContext
from src.models.candlestick import CandlestickData
from .base_detector import BasePatternDetector


class TrendContinuationDetector(BasePatternDetector):
    """Detector for trend continuation (pullback) patterns"""
    
    # Configuration parameters
    MIN_TREND_CANDLES = 60  # Minimum candles for trend analysis
    MIN_TREND_STRENGTH = 60  # Minimum trend strength score
    MIN_TREND_DURATION_HOURS = 1  # Minimum trend duration in hours
    MAX_PULLBACK_ANGLE = 30  # Maximum pullback angle in degrees
    EMA200_DISTANCE_THRESHOLD = Decimal('20')  # Max distance to 200EMA in pips
    MIN_PULLBACK_BARS = 5  # Minimum bars for pullback formation
    MAX_PULLBACK_BARS = 25  # Maximum bars for pullback formation
    FIBONACCI_TOLERANCE = Decimal('0.1')  # Tolerance for Fibonacci levels
    MIN_HIGHER_HIGHS = 3  # Minimum number of higher highs for trend confirmation
    
    async def detect(self, context: MarketContext) -> List[PatternSignal]:
        """Detect trend continuation pattern"""
        # Need at least 60 candles for trend analysis
        if len(context.recent_candles) < self.MIN_TREND_CANDLES:
            return []
        
        # Step 1: Confirm uptrend
        trend_info = self._analyze_uptrend(context)
        if not trend_info or trend_info['strength'] < self.MIN_TREND_STRENGTH:
            return []
        
        # Step 2: Detect pullback formation
        pullback_info = self._detect_pullback(context, trend_info)
        if not pullback_info or not pullback_info['is_valid_pullback']:
            return []
        
        # Step 3: Check 200EMA proximity
        ema_proximity = self._check_ema200_proximity(context)
        if not ema_proximity['is_near_ema']:
            return []
        
        # Step 4: Detect reversal signals
        reversal_signals = self._detect_reversal_signals(context)
        if not reversal_signals['has_signals']:
            return []
        
        # Step 5: Calculate confidence
        confidence = self._calculate_confidence(
            trend_info, pullback_info, ema_proximity, reversal_signals, context
        )
        
        # Create pattern signal
        pattern = PatternSignal(
            id=str(uuid.uuid4()),
            symbol=context.symbol,
            timeframe=context.current_candle.timeframe,
            pattern_type=PatternType.TREND_CONTINUATION,
            detected_at=context.timestamp,
            price_level=context.current_candle.close_price,
            confidence=confidence,
            parameters={
                'trend_strength': trend_info['strength'],
                'pullback_depth': float(pullback_info['depth_percentage']),
                'ema200_distance': float(ema_proximity['distance']),
                'formation_bars': pullback_info['duration_bars'],
                'pullback_angle': pullback_info['angle'],
                'fibonacci_level': float(pullback_info.get('fibonacci_level', 0)),
                'reversal_type': reversal_signals['primary_signal'],
                'trend_duration_hours': trend_info['duration_hours']
            },
            zone_id=self._find_nearby_zone(context)
        )
        
        return [pattern]
    
    def _analyze_uptrend(self, context: MarketContext) -> Optional[Dict[str, Any]]:
        """Analyze if we're in a valid uptrend"""
        all_candles = context.recent_candles + [context.current_candle]
        
        # Check EMA alignment
        ema20 = context.indicators.ema20
        ema75 = context.indicators.ema75
        ema200 = context.indicators.ema200
        
        # EMA alignment: 75EMA above 200EMA (trend structure)
        # Price can be temporarily below 75EMA during pullback
        if ema75 <= ema200:
            return None
        
        # Price should be above 200EMA (overall trend direction)
        current_price = context.current_candle.close_price
        if current_price <= ema200:
            return None
        
        # EMA slope analysis (simplified)
        if len(all_candles) >= 10:
            recent_10 = all_candles[-10:]
            # Check if 200EMA is trending upward (simplified check)
            early_low = min(c.low_price for c in recent_10[:5])
            recent_low = min(c.low_price for c in recent_10[-5:])
            ema_trending_up = recent_low > early_low
        else:
            ema_trending_up = True
        
        # Find higher highs
        higher_highs = self._count_higher_highs(all_candles[-40:])  # Last 40 candles
        
        if higher_highs < self.MIN_HIGHER_HIGHS:
            return None
        
        # Calculate trend strength
        trend_strength = self._calculate_trend_strength(all_candles, context.indicators)
        
        # Calculate trend duration
        trend_duration = self._calculate_trend_duration(all_candles)
        
        if trend_duration < self.MIN_TREND_DURATION_HOURS:
            return None
        
        return {
            'strength': trend_strength,
            'duration_hours': trend_duration,
            'higher_highs': higher_highs,
            'ema_alignment': True,
            'ema_trending_up': ema_trending_up
        }
    
    def _detect_pullback(self, context: MarketContext, trend_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect valid pullback formation"""
        all_candles = context.recent_candles + [context.current_candle]
        
        # Find recent swing high (before pullback)
        swing_high_idx, swing_high_price = self._find_recent_swing_high(all_candles)
        if swing_high_idx is None:
            return None
        
        # Analyze pullback from swing high
        pullback_candles = all_candles[swing_high_idx:]
        
        if len(pullback_candles) < self.MIN_PULLBACK_BARS:
            return None
        
        if len(pullback_candles) > self.MAX_PULLBACK_BARS:
            return None
        
        # Check for lower highs pattern
        if not self._has_lower_highs_pattern(pullback_candles):
            return None
        
        # Calculate pullback metrics
        current_price = context.current_candle.close_price
        pullback_depth = swing_high_price - current_price
        pullback_percentage = float((pullback_depth / swing_high_price) * 100)
        
        # Calculate pullback angle
        time_span = len(pullback_candles)
        pullback_angle = math.degrees(math.atan(float(pullback_depth) / time_span)) if time_span > 0 else 0
        
        # Check angle constraint
        if pullback_angle > self.MAX_PULLBACK_ANGLE:
            return None
        
        # Check Fibonacci retracement levels
        fibonacci_level = self._calculate_fibonacci_level(swing_high_price, current_price, trend_info)
        
        return {
            'is_valid_pullback': True,
            'swing_high_price': swing_high_price,
            'depth_percentage': Decimal(str(pullback_percentage)),
            'angle': pullback_angle,
            'duration_bars': len(pullback_candles),
            'fibonacci_level': fibonacci_level,
            'lower_highs_count': self._count_lower_highs(pullback_candles)
        }
    
    def _check_ema200_proximity(self, context: MarketContext) -> Dict[str, Any]:
        """Check proximity to 200EMA"""
        current_price = context.current_candle.close_price
        ema200 = context.indicators.ema200
        
        distance = abs(current_price - ema200)
        is_near_ema = distance <= self.EMA200_DISTANCE_THRESHOLD
        
        # Check convergence trend (last 5 candles moving towards EMA)
        all_candles = context.recent_candles + [context.current_candle]
        recent_5 = all_candles[-5:]
        
        converging_to_ema = self._is_converging_to_ema(recent_5, ema200)
        
        return {
            'is_near_ema': is_near_ema,
            'distance': distance,
            'converging': converging_to_ema,
            'ema200_level': ema200
        }
    
    def _detect_reversal_signals(self, context: MarketContext) -> Dict[str, Any]:
        """Detect reversal signals near 200EMA"""
        current = context.current_candle
        all_candles = context.recent_candles + [context.current_candle]
        recent_3 = all_candles[-3:]
        
        signals = []
        primary_signal = None
        
        # Pin bar detection
        if (current.lower_wick >= current.body_size * Decimal('2') and 
            current.is_bullish):
            signals.append('pin_bar')
            primary_signal = 'pin_bar'
        
        # Engulfing pattern
        if len(recent_3) >= 2:
            prev_candle = recent_3[-2]
            if (prev_candle.is_bearish and current.is_bullish and
                current.open_price <= prev_candle.close_price and
                current.close_price >= prev_candle.open_price):
                signals.append('engulfing')
                if not primary_signal:
                    primary_signal = 'engulfing'
        
        # Lower wick pattern (buying pressure)
        lower_wick_count = sum(1 for c in recent_3 if c.lower_wick >= c.body_size)
        if lower_wick_count >= 2:
            signals.append('lower_wicks')
            if not primary_signal:
                primary_signal = 'lower_wicks'
        
        # Doji or hammer patterns
        if current.body_size <= current.lower_wick * Decimal('0.3'):
            signals.append('doji_hammer')
            if not primary_signal:
                primary_signal = 'doji_hammer'
        
        # Volume increase detection (simplified - using tick count as proxy)
        if len(all_candles) >= 5:
            recent_volume = current.tick_count
            avg_volume = sum(c.tick_count for c in all_candles[-5:-1]) / 4
            volume_increase = recent_volume > avg_volume * 1.2
            
            if volume_increase:
                signals.append('volume_increase')
        
        return {
            'has_signals': len(signals) > 0,
            'signals': signals,
            'primary_signal': primary_signal or 'none',
            'signal_count': len(signals)
        }
    
    def _calculate_confidence(
        self, 
        trend_info: Dict[str, Any],
        pullback_info: Dict[str, Any],
        ema_proximity: Dict[str, Any],
        reversal_signals: Dict[str, Any],
        context: MarketContext
    ) -> float:
        """Calculate pattern confidence score (0-100)"""
        confidence = 50.0  # Base confidence
        
        # Trend strength factor
        if trend_info['strength'] >= 80:
            confidence += 15
        elif trend_info['strength'] >= 70:
            confidence += 10
        else:
            confidence += 5
        
        # Pullback quality
        pullback_depth = float(pullback_info['depth_percentage'])
        if 30 <= pullback_depth <= 50:  # Ideal pullback depth
            confidence += 10
        elif 20 <= pullback_depth <= 60:
            confidence += 5
        
        # Pullback angle (shallower is better)
        if pullback_info['angle'] <= 20:
            confidence += 10
        elif pullback_info['angle'] <= 25:
            confidence += 5
        
        # EMA proximity
        if ema_proximity['distance'] <= 10:
            confidence += 15
        elif ema_proximity['distance'] <= 15:
            confidence += 10
        else:
            confidence += 5
        
        # EMA convergence
        if ema_proximity['converging']:
            confidence += 10
        
        # Reversal signals
        signal_count = reversal_signals['signal_count']
        if signal_count >= 3:
            confidence += 15
        elif signal_count >= 2:
            confidence += 10
        elif signal_count >= 1:
            confidence += 5
        
        # Primary signal bonus
        primary = reversal_signals['primary_signal']
        if primary == 'pin_bar':
            confidence += 8
        elif primary == 'engulfing':
            confidence += 6
        elif primary in ['lower_wicks', 'doji_hammer']:
            confidence += 4
        
        # Fibonacci level bonus
        fib_level = float(pullback_info.get('fibonacci_level', 0))
        if abs(fib_level - 38.2) <= 5:  # Near 38.2% retracement
            confidence += 5
        elif abs(fib_level - 50) <= 5:  # Near 50% retracement
            confidence += 3
        elif abs(fib_level - 61.8) <= 5:  # Near 61.8% retracement
            confidence += 3
        
        # Zone proximity bonus
        if self._find_nearby_zone(context):
            confidence += 5
        
        # Trend duration bonus
        if trend_info['duration_hours'] >= 4:
            confidence += 5
        elif trend_info['duration_hours'] >= 2:
            confidence += 3
        
        return min(100.0, max(0.0, confidence))
    
    def _count_higher_highs(self, candles: List[CandlestickData]) -> int:
        """Count higher highs in the given candles"""
        if len(candles) < 6:
            return 0
        
        higher_highs = 0
        # Check every 5 candles for swing highs
        for i in range(5, len(candles), 5):
            current_segment = candles[i-5:i]
            prev_segment = candles[max(0, i-10):i-5] if i >= 10 else []
            
            if prev_segment:
                current_high = max(c.high_price for c in current_segment)
                prev_high = max(c.high_price for c in prev_segment)
                
                if current_high > prev_high:
                    higher_highs += 1
        
        return higher_highs
    
    def _calculate_trend_strength(self, candles: List[CandlestickData], indicators) -> float:
        """Calculate trend strength score (0-100)"""
        if len(candles) < 20:
            return 0
        
        strength = 0
        
        # EMA alignment strength
        current_price = candles[-1].close_price
        ema20 = indicators.ema20
        ema75 = indicators.ema75
        ema200 = indicators.ema200
        
        if current_price > ema20 > ema75 > ema200:
            strength += 30
        elif current_price > ema75 > ema200:
            strength += 20
        elif current_price > ema200:
            strength += 10
        
        # Price vs EMA distance
        distance_20 = float(abs(current_price - ema20) / ema20 * 100)
        distance_75 = float(abs(current_price - ema75) / ema75 * 100)
        
        if distance_20 <= 1 and distance_75 <= 2:
            strength += 15  # Close to EMAs (healthy trend)
        elif distance_20 <= 2 and distance_75 <= 3:
            strength += 10
        
        # Bullish candle ratio
        recent_20 = candles[-20:]
        bullish_count = sum(1 for c in recent_20 if c.is_bullish)
        bullish_ratio = bullish_count / len(recent_20)
        
        if bullish_ratio >= 0.7:
            strength += 25
        elif bullish_ratio >= 0.6:
            strength += 15
        elif bullish_ratio >= 0.5:
            strength += 10
        
        # Higher highs consistency
        higher_highs = self._count_higher_highs(candles[-30:])
        if higher_highs >= 5:
            strength += 20
        elif higher_highs >= 3:
            strength += 15
        elif higher_highs >= 2:
            strength += 10
        
        # Momentum (simple price change)
        if len(candles) >= 10:
            price_change = float((candles[-1].close_price - candles[-10].close_price) / candles[-10].close_price * 100)
            if price_change >= 2:
                strength += 10
            elif price_change >= 1:
                strength += 5
        
        return min(100.0, max(0.0, strength))
    
    def _calculate_trend_duration(self, candles: List[CandlestickData]) -> float:
        """Calculate trend duration in hours (simplified)"""
        if len(candles) < 20:
            return 0
        
        # Simplified approach: if we have 60+ candles with overall upward movement
        # and the total time span is 1+ hours, consider it valid
        
        # Check overall price movement
        early_price = sum(c.close_price for c in candles[:10]) / 10
        recent_price = sum(c.close_price for c in candles[-10:]) / 10
        
        price_increase = recent_price > early_price * Decimal('1.005')  # At least 0.5% increase
        
        if price_increase and len(candles) >= 60:  # 60 minutes = 1 hour
            return len(candles) / 60.0
        
        return 0
    
    def _find_recent_swing_high(self, candles: List[CandlestickData]) -> tuple:
        """Find the most recent swing high"""
        if len(candles) < 10:
            return None, None
        
        # Look for swing high in last 25 candles
        search_range = candles[-25:]
        swing_high_price = Decimal('0')
        swing_high_idx = None
        
        for i in range(2, len(search_range) - 2):
            current_high = search_range[i].high_price
            
            # Check if it's a local high
            if (current_high > search_range[i-1].high_price and
                current_high > search_range[i-2].high_price and
                current_high > search_range[i+1].high_price and
                current_high > search_range[i+2].high_price):
                
                if current_high > swing_high_price:
                    swing_high_price = current_high
                    swing_high_idx = len(candles) - len(search_range) + i
        
        return swing_high_idx, swing_high_price
    
    def _has_lower_highs_pattern(self, pullback_candles: List[CandlestickData]) -> bool:
        """Check if pullback shows lower highs pattern"""
        if len(pullback_candles) < 6:
            return False
        
        lower_highs_count = 0
        
        # Check every 3 candles
        for i in range(3, len(pullback_candles), 3):
            if i + 3 <= len(pullback_candles):
                current_segment = pullback_candles[i:i+3]
                prev_segment = pullback_candles[i-3:i]
                
                current_high = max(c.high_price for c in current_segment)
                prev_high = max(c.high_price for c in prev_segment)
                
                if current_high < prev_high - Decimal('5'):  # At least 5 pips lower
                    lower_highs_count += 1
        
        return lower_highs_count >= 1
    
    def _count_lower_highs(self, pullback_candles: List[CandlestickData]) -> int:
        """Count lower highs in pullback"""
        if len(pullback_candles) < 6:
            return 0
        
        count = 0
        for i in range(3, len(pullback_candles), 3):
            if i + 3 <= len(pullback_candles):
                current_segment = pullback_candles[i:i+3]
                prev_segment = pullback_candles[i-3:i]
                
                current_high = max(c.high_price for c in current_segment)
                prev_high = max(c.high_price for c in prev_segment)
                
                if current_high < prev_high - Decimal('5'):
                    count += 1
        
        return count
    
    def _is_converging_to_ema(self, candles: List[CandlestickData], ema200: Decimal) -> bool:
        """Check if price is converging to 200EMA"""
        if len(candles) < 3:
            return False
        
        distances = [abs(c.close_price - ema200) for c in candles]
        
        # Check if distance is generally decreasing
        decreasing_count = 0
        for i in range(1, len(distances)):
            if distances[i] < distances[i-1]:
                decreasing_count += 1
        
        return decreasing_count >= len(distances) // 2
    
    def _calculate_fibonacci_level(self, swing_high: Decimal, current_price: Decimal, trend_info: Dict[str, Any]) -> Decimal:
        """Calculate Fibonacci retracement level"""
        # Find swing low (start of trend move)
        # Simplified: use a percentage of the swing high as approximation
        estimated_swing_low = swing_high * Decimal('0.85')  # Assume 15% move
        
        total_move = swing_high - estimated_swing_low
        current_retracement = swing_high - current_price
        
        if total_move > 0:
            fib_percentage = (current_retracement / total_move) * 100
            return fib_percentage
        
        return Decimal('0')
    
    def _find_nearby_zone(self, context: MarketContext) -> Optional[str]:
        """Find the closest zone if within reasonable distance"""
        if not context.nearby_zones:
            return None
        
        current_price = context.current_candle.close_price
        
        for zone in context.nearby_zones:
            if zone.contains_price(current_price):
                return str(zone.id)
            
            # Check if zone is very close (within 15 pips)
            distance = zone.distance_to_price(current_price)
            if distance <= Decimal('15'):
                return str(zone.id)
        
        return None