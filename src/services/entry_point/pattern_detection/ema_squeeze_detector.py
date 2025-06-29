"""
EMA Squeeze Pattern Detector

Detects when price is tightly squeezed against 200EMA, indicating energy accumulation
before a potential breakout.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
import uuid

from src.domain.models.pattern import PatternSignal, PatternType
from src.domain.models.market import MarketContext
from src.models.candlestick import CandlestickData
from .base_detector import BasePatternDetector


class EMASqueezeDetector(BasePatternDetector):
    """Detector for EMA squeeze (ベタ付け) patterns"""
    
    # Configuration parameters
    MIN_SQUEEZE_CANDLES = 5  # Minimum consecutive squeeze candles
    MAX_BODY_DEVIATION = Decimal('3')  # Max deviation from 200EMA in pips
    MAX_WICK_DEVIATION = Decimal('10')  # Max wick deviation from 200EMA
    MAX_RANGE_HEIGHT = Decimal('15')  # Max height of squeeze range in pips
    EMA_CONVERGENCE_THRESHOLD = Decimal('20')  # Max distance between EMAs for convergence
    BOLLINGER_SQUEEZE_RATIO = 0.7  # BB width ratio for squeeze detection
    
    async def detect(self, context: MarketContext) -> List[PatternSignal]:
        """Detect EMA squeeze pattern"""
        # Need at least 10 candles for analysis
        if len(context.recent_candles) < 10:
            return []
        
        # Step 1: Detect squeeze state
        squeeze_info = self._detect_squeeze_state(context)
        if not squeeze_info or squeeze_info['squeeze_count'] < self.MIN_SQUEEZE_CANDLES:
            return []
        
        # Step 2: Check for breakout precursors
        breakout_precursor = self._check_breakout_precursors(context, squeeze_info)
        if not breakout_precursor['has_precursor']:
            return []
        
        # Step 3: Predict breakout direction
        breakout_direction = self._predict_breakout_direction(context, squeeze_info)
        
        # Step 4: Calculate confidence score
        confidence = self._calculate_confidence(squeeze_info, breakout_precursor, context)
        
        # Create pattern signal
        pattern = PatternSignal(
            id=str(uuid.uuid4()),
            symbol=context.symbol,
            timeframe=context.current_candle.timeframe,
            pattern_type=PatternType.EMA_SQUEEZE,
            detected_at=context.timestamp,
            price_level=context.current_candle.close_price,
            confidence=confidence,
            parameters={
                'squeeze_duration': squeeze_info['squeeze_count'],
                'max_deviation': float(squeeze_info['max_deviation']),
                'convergence_level': float(breakout_precursor['convergence_level']),
                'breakout_direction': breakout_direction,
                'ema_convergence': breakout_precursor['ema_convergence'],
                'bollinger_squeeze': breakout_precursor.get('bollinger_squeeze', False),
                'range_height': float(squeeze_info['range_height'])
            },
            zone_id=self._find_nearby_zone(context)
        )
        
        return [pattern]
    
    def _detect_squeeze_state(self, context: MarketContext) -> Optional[Dict[str, Any]]:
        """Detect if price is squeezed against 200EMA"""
        ema200 = context.indicators.ema200
        all_candles = context.recent_candles + [context.current_candle]
        recent_candles = all_candles[-10:]  # Check last 10 candles
        
        squeeze_candles = []
        max_deviation = Decimal('0')
        high_in_range = Decimal('0')
        low_in_range = Decimal('99999')
        
        # Check each candle for squeeze conditions
        for candle in recent_candles:
            # Check body deviation from 200EMA
            body_deviation_high = abs(candle.close_price - ema200)
            body_deviation_low = abs(candle.open_price - ema200)
            body_deviation = max(body_deviation_high, body_deviation_low)
            
            # Check wick deviation
            wick_deviation_high = abs(candle.high_price - ema200)
            wick_deviation_low = abs(candle.low_price - ema200)
            max_wick_deviation = max(wick_deviation_high, wick_deviation_low)
            
            # Determine if candle meets squeeze criteria
            if (body_deviation <= self.MAX_BODY_DEVIATION and 
                max_wick_deviation <= self.MAX_WICK_DEVIATION):
                squeeze_candles.append(candle)
                max_deviation = max(max_deviation, body_deviation)
                high_in_range = max(high_in_range, candle.high_price)
                low_in_range = min(low_in_range, candle.low_price)
        
        # Count consecutive squeeze candles from the end
        consecutive_count = 0
        for i in range(len(recent_candles) - 1, -1, -1):
            if recent_candles[i] in squeeze_candles:
                consecutive_count += 1
            else:
                break
        
        if consecutive_count < self.MIN_SQUEEZE_CANDLES:
            return None
        
        # Calculate range height
        range_height = high_in_range - low_in_range
        
        # Check if range is narrow enough (横ばい condition)
        if range_height > self.MAX_RANGE_HEIGHT:
            return None
        
        return {
            'squeeze_count': consecutive_count,
            'total_squeeze_candles': len(squeeze_candles),
            'max_deviation': max_deviation,
            'range_height': range_height,
            'range_high': high_in_range,
            'range_low': low_in_range,
            'is_valid_squeeze': True
        }
    
    def _check_breakout_precursors(self, context: MarketContext, squeeze_info: Dict[str, Any]) -> Dict[str, Any]:
        """Check for signs of impending breakout"""
        ema20 = context.indicators.ema20
        ema75 = context.indicators.ema75
        ema200 = context.indicators.ema200
        
        # Check EMA convergence
        ema_distance = max(
            abs(ema20 - ema75),
            abs(ema75 - ema200),
            abs(ema20 - ema200)
        )
        
        ema_convergence = ema_distance <= self.EMA_CONVERGENCE_THRESHOLD
        # Better normalization: 0 at threshold, 1 at perfect convergence
        if ema_distance >= self.EMA_CONVERGENCE_THRESHOLD:
            convergence_level = 0.0
        else:
            convergence_level = float(1 - (ema_distance / self.EMA_CONVERGENCE_THRESHOLD))
        convergence_level = max(0, min(1, convergence_level))
        
        # Check for triangle pattern (converging highs and lows)
        triangle_detected = self._check_triangle_pattern(context, squeeze_info)
        
        # Bollinger Band squeeze would be checked here if BB data available
        # For now, we'll use a simplified volatility check
        bollinger_squeeze = self._check_volatility_squeeze(context)
        
        # At least one strong precursor is required
        # EMA convergence is the most important
        has_precursor = ema_convergence and (triangle_detected or bollinger_squeeze or convergence_level > 0.5)
        
        return {
            'has_precursor': has_precursor,
            'ema_convergence': ema_convergence,
            'convergence_level': convergence_level,
            'triangle_pattern': triangle_detected,
            'bollinger_squeeze': bollinger_squeeze,
            'ema_distance': float(ema_distance)
        }
    
    def _predict_breakout_direction(self, context: MarketContext, squeeze_info: Dict[str, Any]) -> str:
        """Predict likely breakout direction"""
        ema20 = context.indicators.ema20
        ema75 = context.indicators.ema75
        ema200 = context.indicators.ema200
        
        # Check MA alignment
        if ema20 > ema75 > ema200:
            ma_bias = "bullish"
        elif ema20 < ema75 < ema200:
            ma_bias = "bearish"
        else:
            ma_bias = "neutral"
        
        # Check recent momentum
        all_candles = context.recent_candles + [context.current_candle]
        recent_5 = all_candles[-5:]
        
        bullish_count = sum(1 for c in recent_5 if c.is_bullish)
        bearish_count = sum(1 for c in recent_5 if c.is_bearish)
        
        if bullish_count > bearish_count:
            momentum_bias = "bullish"
        elif bearish_count > bullish_count:
            momentum_bias = "bearish"
        else:
            momentum_bias = "neutral"
        
        # Position relative to squeeze range
        current_price = context.current_candle.close_price
        range_middle = (squeeze_info['range_high'] + squeeze_info['range_low']) / 2
        
        if current_price > range_middle:
            position_bias = "bullish"
        else:
            position_bias = "bearish"
        
        # Combine biases
        biases = [ma_bias, momentum_bias, position_bias]
        bullish_votes = biases.count("bullish")
        bearish_votes = biases.count("bearish")
        
        if bullish_votes > bearish_votes:
            return "bullish"
        elif bearish_votes > bullish_votes:
            return "bearish"
        else:
            # Default to MA bias if tied
            return ma_bias if ma_bias != "neutral" else "bullish"
    
    def _calculate_confidence(
        self, 
        squeeze_info: Dict[str, Any], 
        breakout_precursor: Dict[str, Any],
        context: MarketContext
    ) -> float:
        """Calculate pattern confidence score (0-100)"""
        confidence = 50.0  # Base confidence
        
        # Squeeze duration factor
        if squeeze_info['squeeze_count'] >= 8:
            confidence += 15
        elif squeeze_info['squeeze_count'] >= 6:
            confidence += 10
        else:
            confidence += 5
        
        # Deviation factor (tighter is better)
        if squeeze_info['max_deviation'] <= 1:
            confidence += 10
        elif squeeze_info['max_deviation'] <= 2:
            confidence += 5
        
        # Range tightness factor
        if squeeze_info['range_height'] <= 10:
            confidence += 10
        elif squeeze_info['range_height'] <= 12:
            confidence += 5
        
        # EMA convergence factor
        if breakout_precursor['ema_convergence']:
            confidence += 15
        elif breakout_precursor['convergence_level'] > 0.8:
            confidence += 10
        elif breakout_precursor['convergence_level'] > 0.6:
            confidence += 5
        
        # Additional precursor factors
        if breakout_precursor.get('triangle_pattern', False):
            confidence += 5
        
        if breakout_precursor.get('bollinger_squeeze', False):
            confidence += 5
        
        # Zone proximity bonus
        if self._find_nearby_zone(context):
            confidence += 5
        
        return min(100.0, max(0.0, confidence))
    
    def _check_triangle_pattern(self, context: MarketContext, squeeze_info: Dict[str, Any]) -> bool:
        """Check if price is forming a triangle pattern"""
        all_candles = context.recent_candles + [context.current_candle]
        squeeze_candles = all_candles[-squeeze_info['squeeze_count']:]
        
        if len(squeeze_candles) < 5:
            return False
        
        # Check if highs are descending and lows are ascending
        highs = [c.high_price for c in squeeze_candles]
        lows = [c.low_price for c in squeeze_candles]
        
        # Simple trend check
        high_trend = highs[0] > highs[-1]  # Descending highs
        low_trend = lows[0] < lows[-1]    # Ascending lows
        
        # Check if range is contracting
        early_range = highs[0] - lows[0]
        recent_range = highs[-1] - lows[-1]
        
        return high_trend and low_trend and recent_range < early_range * Decimal('0.7')
    
    def _check_volatility_squeeze(self, context: MarketContext) -> bool:
        """Check if volatility is contracting (simplified Bollinger Band squeeze)"""
        all_candles = context.recent_candles + [context.current_candle]
        recent_10 = all_candles[-10:]
        
        # Calculate recent volatility (simplified)
        ranges = [c.high_price - c.low_price for c in recent_10]
        avg_range = sum(ranges) / len(ranges)
        
        # Compare to ATR
        atr = context.indicators.atr14
        
        # If recent average range is significantly less than ATR, we have a squeeze
        return avg_range < atr * Decimal(str(self.BOLLINGER_SQUEEZE_RATIO))
    
    def _find_nearby_zone(self, context: MarketContext) -> Optional[str]:
        """Find the closest zone if within reasonable distance"""
        if not context.nearby_zones:
            return None
        
        current_price = context.current_candle.close_price
        
        for zone in context.nearby_zones:
            if zone.contains_price(current_price):
                return str(zone.id)
            
            # Check if zone is very close (within 10 pips)
            distance = zone.distance_to_price(current_price)
            if distance <= Decimal('10'):
                return str(zone.id)
        
        return None