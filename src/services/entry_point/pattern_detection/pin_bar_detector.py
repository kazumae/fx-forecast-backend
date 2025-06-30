"""
Pin Bar Pattern Detector

Detects pin bar (hammer/shooting star) candlestick patterns at key levels.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
import uuid

from src.domain.models.pattern import PatternSignal, PatternType, PatternDirection
from src.domain.models.market import MarketContext
from src.models.candlestick import CandlestickData
from .base_detector import BasePatternDetector


class PinBarDetector(BasePatternDetector):
    """Detector for pin bar candlestick patterns"""
    
    # Configuration parameters
    MIN_WICK_RATIO = 2.5  # Wick must be 2.5x body size
    MAX_OPPOSITE_WICK_RATIO = 0.5  # Opposite wick must be less than 0.5x body
    MIN_BODY_SIZE_PIPS = Decimal('1')  # Minimum body size to avoid doji
    KEY_LEVEL_DISTANCE_ATR = Decimal('0.3')  # Must be within 0.3 * ATR of key level
    
    async def detect(self, context: MarketContext) -> List[PatternSignal]:
        """Detect pin bar patterns"""
        signals = []
        
        # Check current candle for pin bar
        current_signal = self._check_pin_bar(
            context.current_candle,
            context
        )
        if current_signal:
            signals.append(current_signal)
            self._log_detection(current_signal, context)
        
        # Also check the previous candle (common to wait for confirmation)
        if context.recent_candles:
            prev_signal = self._check_pin_bar(
                context.recent_candles[-1],
                context,
                is_previous=True
            )
            if prev_signal:
                signals.append(prev_signal)
                self._log_detection(prev_signal, context)
        
        return signals
    
    def _check_pin_bar(
        self, 
        candle: CandlestickData,
        context: MarketContext,
        is_previous: bool = False
    ) -> Optional[PatternSignal]:
        """Check if a candle is a valid pin bar"""
        
        # Calculate candle components
        body_size = abs(candle.close_price - candle.open_price)
        upper_wick = candle.high_price - max(candle.open_price, candle.close_price)
        lower_wick = min(candle.open_price, candle.close_price) - candle.low_price
        
        # Skip if body is too small (doji)
        if body_size < self.MIN_BODY_SIZE_PIPS:
            return None
        
        # Check for bullish pin bar (hammer)
        is_bullish_pin = (
            lower_wick >= body_size * self.MIN_WICK_RATIO and
            upper_wick <= body_size * self.MAX_OPPOSITE_WICK_RATIO
        )
        
        # Check for bearish pin bar (shooting star)
        is_bearish_pin = (
            upper_wick >= body_size * self.MIN_WICK_RATIO and
            lower_wick <= body_size * self.MAX_OPPOSITE_WICK_RATIO
        )
        
        if not (is_bullish_pin or is_bearish_pin):
            return None
        
        # Check if pin bar is at a key level
        location_info = self._evaluate_location(candle, context, is_bullish_pin)
        if not location_info['is_at_key_level']:
            return None
        
        # For previous candle, check if current candle confirms the pattern
        if is_previous:
            if not self._is_pattern_confirmed(candle, context.current_candle, is_bullish_pin):
                return None
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            candle,
            is_bullish_pin,
            location_info,
            context
        )
        
        # Determine direction
        direction = PatternDirection.LONG if is_bullish_pin else PatternDirection.SHORT
        
        # Create pattern signal
        return PatternSignal(
            id=str(uuid.uuid4()),
            symbol=context.symbol,
            timestamp=candle.open_time if is_previous else context.timestamp,
            pattern_type=PatternType.PIN_BAR,
            direction=direction,
            confidence=confidence,
            price_level=candle.close_price,
            zone_id=location_info.get('zone_id'),
            timeframe=getattr(context, 'timeframe', '1m'),
            parameters={
                'pin_type': 'bullish_hammer' if is_bullish_pin else 'bearish_shooting_star',
                'wick_ratio': float(lower_wick / body_size if is_bullish_pin else upper_wick / body_size),
                'body_size': float(body_size),
                'location_type': location_info['location_type'],
                'location_strength': location_info['location_strength'],
                'is_confirmed': is_previous,
                'candle_color': 'green' if candle.close_price > candle.open_price else 'red'
            }
        )
    
    def _evaluate_location(
        self, 
        candle: CandlestickData,
        context: MarketContext,
        is_bullish: bool
    ) -> Dict[str, Any]:
        """Evaluate if pin bar is at a key level"""
        
        location_info = {
            'is_at_key_level': False,
            'location_type': None,
            'location_strength': 0,
            'zone_id': None
        }
        
        # Check distance to EMAs
        if context.indicators:
            ema_check = self._check_ema_proximity(candle, context.indicators, is_bullish)
            if ema_check['is_near_ema']:
                location_info.update(ema_check)
                return location_info
        
        # Check zones
        zones = getattr(context, 'nearby_zones', [])
        zone_check = self._check_zone_proximity(candle, zones, is_bullish)
        if zone_check['is_near_zone']:
            location_info.update(zone_check)
            return location_info
        
        # Check psychological levels
        psych_check = self._check_psychological_levels(candle, is_bullish)
        if psych_check['is_near_level']:
            location_info.update(psych_check)
            return location_info
        
        # Check previous support/resistance
        sr_check = self._check_support_resistance(candle, context.recent_candles, is_bullish)
        if sr_check['is_near_sr']:
            location_info.update(sr_check)
        
        return location_info
    
    def _check_ema_proximity(
        self,
        candle: CandlestickData,
        indicators,
        is_bullish: bool
    ) -> Dict[str, Any]:
        """Check if pin bar is near important EMAs"""
        
        result = {
            'is_near_ema': False,
            'is_at_key_level': False,
            'location_type': None,
            'location_strength': 0
        }
        
        # Get ATR for distance calculation
        atr = getattr(indicators, 'atr14', Decimal('10'))
        threshold = atr * self.KEY_LEVEL_DISTANCE_ATR
        
        # For bullish pin bar, check if low is near EMA
        if is_bullish:
            test_price = candle.low_price
        else:
            test_price = candle.high_price
        
        # Check each EMA
        ema_checks = [
            ('ema200', indicators.ema200, 90),
            ('ema75', indicators.ema75, 70),
            ('ema20', indicators.ema20, 60)
        ]
        
        for ema_name, ema_value, strength in ema_checks:
            if ema_value and abs(test_price - ema_value) <= threshold:
                result['is_near_ema'] = True
                result['is_at_key_level'] = True
                result['location_type'] = ema_name
                result['location_strength'] = strength
                break
        
        return result
    
    def _check_zone_proximity(
        self,
        candle: CandlestickData,
        zones: List,
        is_bullish: bool
    ) -> Dict[str, Any]:
        """Check if pin bar is near a zone"""
        
        result = {
            'is_near_zone': False,
            'is_at_key_level': False,
            'location_type': None,
            'location_strength': 0,
            'zone_id': None
        }
        
        if not zones:
            return result
        
        # For bullish pin bar, check if low touched zone
        # For bearish pin bar, check if high touched zone
        for zone in zones:
            if hasattr(zone, 'upper_bound') and hasattr(zone, 'lower_bound'):
                if is_bullish and zone.lower_bound <= candle.low_price <= zone.upper_bound:
                    result['is_near_zone'] = True
                    result['is_at_key_level'] = True
                    result['location_type'] = 'support_zone'
                    result['location_strength'] = getattr(zone, 'strength', 70)
                    result['zone_id'] = getattr(zone, 'id', None)
                    break
                elif not is_bullish and zone.lower_bound <= candle.high_price <= zone.upper_bound:
                    result['is_near_zone'] = True
                    result['is_at_key_level'] = True
                    result['location_type'] = 'resistance_zone'
                    result['location_strength'] = getattr(zone, 'strength', 70)
                    result['zone_id'] = getattr(zone, 'id', None)
                    break
        
        return result
    
    def _check_psychological_levels(
        self,
        candle: CandlestickData,
        is_bullish: bool
    ) -> Dict[str, Any]:
        """Check if pin bar is at psychological levels (round numbers)"""
        
        result = {
            'is_near_level': False,
            'is_at_key_level': False,
            'location_type': None,
            'location_strength': 0
        }
        
        # Test price depends on pin bar type
        test_price = float(candle.low_price if is_bullish else candle.high_price)
        
        # Check round numbers (00, 50)
        for level in range(int(test_price - 50), int(test_price + 50), 10):
            if level % 50 == 0:  # Major levels (00, 50)
                distance = abs(test_price - level)
                if distance <= 5:  # Within 5 pips
                    result['is_near_level'] = True
                    result['is_at_key_level'] = True
                    result['location_type'] = 'psychological_major'
                    result['location_strength'] = 80 if level % 100 == 0 else 70
                    break
            elif level % 10 == 0:  # Minor levels
                distance = abs(test_price - level)
                if distance <= 3:  # Within 3 pips
                    result['is_near_level'] = True
                    result['is_at_key_level'] = True
                    result['location_type'] = 'psychological_minor'
                    result['location_strength'] = 60
                    break
        
        return result
    
    def _check_support_resistance(
        self,
        candle: CandlestickData,
        recent_candles: List[CandlestickData],
        is_bullish: bool
    ) -> Dict[str, Any]:
        """Check if pin bar is at previous support/resistance"""
        
        result = {
            'is_near_sr': False,
            'is_at_key_level': False,
            'location_type': None,
            'location_strength': 0
        }
        
        if len(recent_candles) < 20:
            return result
        
        # Get recent highs and lows
        recent_highs = [float(c.high_price) for c in recent_candles[-20:]]
        recent_lows = [float(c.low_price) for c in recent_candles[-20:]]
        
        test_price = float(candle.low_price if is_bullish else candle.high_price)
        
        # Count how many times price reversed near this level
        reversal_count = 0
        threshold = 5  # 5 pips
        
        for high, low in zip(recent_highs, recent_lows):
            if abs(test_price - high) <= threshold or abs(test_price - low) <= threshold:
                reversal_count += 1
        
        if reversal_count >= 2:
            result['is_near_sr'] = True
            result['is_at_key_level'] = True
            result['location_type'] = 'support' if is_bullish else 'resistance'
            result['location_strength'] = min(50 + (reversal_count * 10), 80)
        
        return result
    
    def _is_pattern_confirmed(
        self,
        pin_bar_candle: CandlestickData,
        current_candle: CandlestickData,
        is_bullish: bool
    ) -> bool:
        """Check if the pin bar pattern is confirmed by the next candle"""
        
        if is_bullish:
            # For bullish pin bar, next candle should close higher
            return current_candle.close_price > pin_bar_candle.close_price
        else:
            # For bearish pin bar, next candle should close lower
            return current_candle.close_price < pin_bar_candle.close_price
    
    def _calculate_confidence(
        self,
        candle: CandlestickData,
        is_bullish: bool,
        location_info: Dict[str, Any],
        context: MarketContext
    ) -> float:
        """Calculate confidence score for the pin bar pattern"""
        
        confidence = 50.0  # Base confidence
        
        # 1. Wick ratio factor
        body_size = abs(float(candle.close_price - candle.open_price))
        if body_size < 0.1:
            body_size = 0.1
        
        if is_bullish:
            wick_ratio = float(min(candle.open_price, candle.close_price) - candle.low_price) / body_size
        else:
            wick_ratio = float(candle.high_price - max(candle.open_price, candle.close_price)) / body_size
        
        if wick_ratio > 4:
            confidence += 15
        elif wick_ratio > 3:
            confidence += 10
        elif wick_ratio > 2.5:
            confidence += 5
        
        # 2. Location strength
        location_strength = location_info.get('location_strength', 0)
        if location_strength >= 80:
            confidence += 15
        elif location_strength >= 70:
            confidence += 10
        elif location_strength >= 60:
            confidence += 5
        
        # 3. Candle color alignment
        # Bullish pin bar closing green is better
        if is_bullish and candle.close_price > candle.open_price:
            confidence += 5
        # Bearish pin bar closing red is better
        elif not is_bullish and candle.close_price < candle.open_price:
            confidence += 5
        
        # 4. Trend alignment (if available)
        if context.indicators and hasattr(context.indicators, 'ema20'):
            current_price = float(context.current_price)
            ema20 = float(context.indicators.ema20)
            
            # Bullish pin in uptrend
            if is_bullish and current_price > ema20:
                confidence += 10
            # Bearish pin in downtrend
            elif not is_bullish and current_price < ema20:
                confidence += 10
        
        # 5. Volume consideration (if we had volume data)
        # High volume pin bars are more reliable
        # This would be implemented if volume data was available
        
        return min(confidence, 90.0)  # Cap at 90%