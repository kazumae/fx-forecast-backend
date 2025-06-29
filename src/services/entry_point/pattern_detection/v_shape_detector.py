"""
V-Shape Reversal Pattern Detector

Detects sharp drops followed by immediate reversals, especially near 200EMA and zones.
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


class VShapeDetector(BasePatternDetector):
    """Detector for V-shape reversal patterns"""
    
    # Configuration parameters
    MIN_DROP_ANGLE = 45  # degrees
    MIN_CANDLES_FOR_ANALYSIS = 20
    BODY_SIZE_MULTIPLIER = 2.0  # Body must be 2x average
    MIN_BEARISH_RATIO = 0.6  # 60% of recent candles should be bearish
    EMA_ZONE_THRESHOLD_ATR_RATIO = Decimal('0.3')  # Distance must be within 0.3 * ATR
    PIN_BAR_WICK_RATIO = 2.0  # Lower wick must be 2x body for pin bar
    IMMEDIATE_BOUNCE_THRESHOLD = Decimal('5')  # 5 pips for immediate bounce
    
    async def detect(self, context: MarketContext) -> List[PatternSignal]:
        """Detect V-shape reversal pattern"""
        # Need at least 20 candles for analysis
        if len(context.recent_candles) < 20:
            return []
        
        # Step 1: Detect sharp drop
        drop_info = self._detect_sharp_drop(context)
        if not drop_info:
            return []
        
        # Step 2: Check 200EMA and zone overlap
        if not self._check_ema_zone_overlap(context):
            return []
        
        # Step 3: Detect reversal signal
        reversal_signal = self._detect_reversal_signal(context)
        if not reversal_signal:
            return []
        
        # Step 4: Calculate confidence and create pattern signal
        confidence = self._calculate_confidence(drop_info, reversal_signal, context)
        
        # Find matching zone
        zone_id = None
        for zone in context.nearby_zones:
            if zone.contains_price(context.current_candle.low_price):
                zone_id = str(zone.id)
                break
        
        pattern = PatternSignal(
            id=str(uuid.uuid4()),
            symbol=context.symbol,
            timeframe=context.current_candle.timeframe,
            pattern_type=PatternType.V_SHAPE_REVERSAL,
            detected_at=context.timestamp,
            price_level=context.current_candle.close_price,
            confidence=confidence,
            parameters={
                'drop_start_price': float(drop_info['start_price']),
                'drop_low_price': float(drop_info['low_price']),
                'drop_pips': float(drop_info['drop_pips']),
                'drop_angle': drop_info['angle'],
                'reversal_type': reversal_signal['type'],
                'reversal_strength': reversal_signal['strength'],
                'ema_touch': drop_info.get('ema_touch', False)
            },
            zone_id=zone_id
        )
        
        return [pattern]
    
    def _detect_sharp_drop(self, context: MarketContext) -> Optional[Dict[str, Any]]:
        """Detect if there was a sharp drop in recent candles"""
        # Need at least 20 candles
        if len(context.recent_candles) < 20:
            return None
            
        # Get last 20 candles including current
        all_candles = context.recent_candles + [context.current_candle]
        candles = all_candles[-20:]
        
        # Find the high point in the first 10 candles
        start_price = max(c.high_price for c in candles[:10])
        
        # Find the low point in the last 5 candles
        low_price = min(c.low_price for c in candles[-5:])
        
        # Calculate drop
        drop_pips = float(start_price - low_price)
        
        # Calculate angle (simplified)
        time_span = 15  # approximate minutes for the drop
        angle = math.degrees(math.atan(drop_pips / time_span)) if time_span > 0 else 0
        
        # Count bearish candles in drop period
        drop_candles = candles[10:]
        bearish_count = sum(1 for c in drop_candles if c.is_bearish)
        
        # Check if sharp drop criteria met
        if (angle >= 45 and bearish_count >= 3 and drop_pips >= 15):
            # Check if drop touched 200EMA
            ema_touch = False
            for c in drop_candles:
                if abs(c.low_price - context.indicators.ema200) <= Decimal('5'):
                    ema_touch = True
                    break
                    
            return {
                'start_price': start_price,
                'low_price': low_price,
                'drop_pips': drop_pips,
                'angle': angle,
                'ema_touch': ema_touch,
                'strength': bearish_count / len(drop_candles) if drop_candles else 0
            }
        
        return None
    
    def _check_ema_zone_overlap(self, context: MarketContext) -> bool:
        """Check if 200EMA overlaps with a zone"""
        ema200 = context.indicators.ema200
        atr = context.indicators.atr14
        threshold = atr * self.EMA_ZONE_THRESHOLD_ATR_RATIO
        
        # Check each nearby zone
        for zone in context.nearby_zones:
            # Check if EMA is within threshold distance of zone
            distance_to_upper = abs(ema200 - zone.upper_bound)
            distance_to_lower = abs(ema200 - zone.lower_bound)
            
            if (distance_to_upper <= threshold or 
                distance_to_lower <= threshold or
                zone.lower_bound <= ema200 <= zone.upper_bound):
                self.logger.debug(
                    f"200EMA ({ema200}) overlaps with zone "
                    f"[{zone.lower_bound}-{zone.upper_bound}]"
                )
                return True
        
        return False
    
    def _detect_reversal_signal(self, context: MarketContext) -> Optional[Dict[str, Any]]:
        """Detect reversal signal (pin bar, breakout, or immediate bounce)"""
        current = context.current_candle
        recent = context.get_candles_range(3)
        ema200 = context.indicators.ema200
        
        # Check for pin bar (long lower wick)
        if current.lower_wick >= current.body_size * Decimal(str(self.PIN_BAR_WICK_RATIO)):
            # Check if pin bar is near 200EMA
            distance_to_ema = abs(current.low_price - ema200)
            if distance_to_ema <= Decimal('5'):  # Within 5 pips
                return {
                    'type': 'pin_bar',
                    'strength': float(current.lower_wick),
                    'ema_touch': True,
                    'wick_ratio': float(current.lower_wick / current.body_size) if current.body_size > 0 else 0
                }
        
        # Check for previous bar high breakout
        if len(recent) >= 2 and current.close_price > recent[-2].high_price:
            bounce_strength = current.close_price - recent[-1].low_price
            return {
                'type': 'breakout',
                'strength': float(bounce_strength),
                'ema_touch': abs(recent[-1].low_price - ema200) <= Decimal('5'),
                'breakout_pips': float(current.close_price - recent[-2].high_price)
            }
        
        # Check for immediate bounce (5+ pips)
        if current.close_price - current.open_price >= self.IMMEDIATE_BOUNCE_THRESHOLD:
            return {
                'type': 'immediate_bounce',
                'strength': float(current.close_price - current.open_price),
                'ema_touch': abs(current.low_price - ema200) <= Decimal('5'),
                'bounce_pips': float(current.close_price - current.open_price)
            }
        
        return None
    
    def _calculate_confidence(
        self, 
        drop_info: Dict[str, Any], 
        reversal_signal: Dict[str, Any],
        context: MarketContext
    ) -> float:
        """Calculate pattern confidence score (0-100)"""
        confidence = 50.0  # Base confidence
        
        # Drop quality factors
        if drop_info['angle'] >= 60:
            confidence += 10
        elif drop_info['angle'] >= 50:
            confidence += 5
        
        if drop_info['drop_pips'] >= 30:
            confidence += 10
        elif drop_info['drop_pips'] >= 20:
            confidence += 5
        
        if drop_info.get('strength', 0) >= 0.8:
            confidence += 5
        
        # Reversal quality factors
        if reversal_signal['type'] == 'pin_bar':
            confidence += 15
        elif reversal_signal['type'] == 'breakout':
            confidence += 10
        elif reversal_signal['type'] == 'immediate_bounce':
            confidence += 8
        
        if reversal_signal.get('ema_touch', False):
            confidence += 10
        
        # Zone proximity bonus
        if context.nearby_zones:
            confidence += 5
        
        # EMA alignment bonus
        if context.indicators.ema_alignment == "bullish":
            confidence += 5
        
        return min(100.0, max(0.0, confidence))
    
    def _calculate_dynamic_threshold(self, context: MarketContext, threshold_type: str) -> float:
        """Calculate dynamic threshold based on ATR"""
        atr = float(context.indicators.atr14)
        
        base_thresholds = {
            'drop_pips': 15.0,  # Lowered for testing
            'reversal_pips': 5.0,
            'zone_width': 15.0,
            'ema_distance': 3.0
        }
        
        # Adjust based on volatility (simplified version)
        base = base_thresholds.get(threshold_type, 10.0)
        
        # If ATR is high, increase threshold
        if atr > 10:
            return base * 1.5
        elif atr < 5:
            return base * 0.7
        else:
            return base
    
    def _count_consecutive_bearish(self, candles: List[CandlestickData]) -> int:
        """Count consecutive bearish candles from the end"""
        count = 0
        for candle in reversed(candles):
            if candle.close_price < candle.open_price:
                count += 1
            else:
                break
        return count
    
    def _find_nearby_zone_id(self, context: MarketContext) -> Optional[str]:
        """Find the closest zone ID if within reasonable distance"""
        if not context.nearby_zones:
            return None
        
        current_price = context.current_price
        closest_zone = None
        min_distance = Decimal('999999')
        
        for zone in context.nearby_zones:
            # Calculate distance to zone
            if zone.lower_bound <= current_price <= zone.upper_bound:
                # Price is inside zone
                return str(zone.id)
            
            distance = min(
                abs(current_price - zone.upper_bound),
                abs(current_price - zone.lower_bound)
            )
            
            if distance < min_distance and distance <= Decimal('20'):  # Within 20 pips
                min_distance = distance
                closest_zone = zone
        
        return str(closest_zone.id) if closest_zone else None