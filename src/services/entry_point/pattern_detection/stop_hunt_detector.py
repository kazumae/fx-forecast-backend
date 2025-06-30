"""
Stop Hunt Pattern Detector

Detects stop hunting patterns near zones where large players trigger stops.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
import uuid

from src.domain.models.pattern import PatternSignal, PatternType, PatternDirection
from src.domain.models.market import MarketContext
from src.models.candlestick import CandlestickData
from src.models.zone import Zone
from .base_detector import BasePatternDetector


class StopHuntDetector(BasePatternDetector):
    """Detector for stop hunting patterns"""
    
    # Configuration parameters
    MIN_WICK_RATIO = 3.0  # Wick must be 3x body size
    MAX_CANDLES_FOR_REVERSAL = 3  # Must reverse within 3 candles
    MIN_REVERSAL_PERCENT = 0.3  # Must reverse at least 30% of spike
    ZONE_PROXIMITY_ATR_RATIO = Decimal('0.5')  # Must be within 0.5 * ATR of zone
    
    async def detect(self, context: MarketContext) -> List[PatternSignal]:
        """Detect stop hunt patterns"""
        signals = []
        
        # Need at least 5 candles for analysis
        if len(context.recent_candles) < 5:
            return signals
        
        # Get recent candles including current
        all_candles = context.recent_candles + [context.current_candle]
        recent_candles = all_candles[-5:]
        
        # Check for zones (if available)
        zones = getattr(context, 'nearby_zones', [])
        if not zones:
            # If no zones, use psychological levels
            zones = self._create_psychological_zones(context.current_price)
        
        # Check each zone for stop hunt patterns
        for zone in zones:
            signal = self._check_stop_hunt_near_zone(recent_candles, zone, context)
            if signal:
                signals.append(signal)
                self._log_detection(signal, context)
        
        return signals
    
    def _check_stop_hunt_near_zone(
        self, 
        candles: List[CandlestickData], 
        zone: Zone,
        context: MarketContext
    ) -> Optional[PatternSignal]:
        """Check for stop hunt pattern near a specific zone"""
        
        # Look for spike candles in recent history (not including current)
        spike_info = self._find_spike_candle(candles[:-1], zone)
        if not spike_info:
            return None
        
        spike_index, spike_candle, spike_direction = spike_info
        
        # Check for reversal after spike
        reversal_candles = candles[spike_index + 1:]
        if not self._confirm_reversal(spike_candle, reversal_candles, spike_direction):
            return None
        
        # Calculate pattern strength and confidence
        confidence = self._calculate_confidence(
            spike_candle, 
            reversal_candles, 
            spike_direction,
            zone
        )
        
        # Determine trading direction (opposite of spike)
        pattern_direction = PatternDirection.LONG if spike_direction == 'lower' else PatternDirection.SHORT
        
        # Create pattern signal
        return PatternSignal(
            id=str(uuid.uuid4()),
            symbol=context.symbol,
            timestamp=context.timestamp,
            pattern_type=PatternType.STOP_HUNT,
            direction=pattern_direction,
            confidence=confidence,
            price_level=context.current_price,
            zone_id=getattr(zone, 'id', None),
            timeframe=getattr(context, 'timeframe', '1m'),
            parameters={
                'spike_direction': spike_direction,
                'spike_size': float(self._get_spike_size(spike_candle, spike_direction)),
                'wick_ratio': float(self._get_wick_ratio(spike_candle, spike_direction)),
                'reversal_strength': float(self._calculate_reversal_strength(spike_candle, reversal_candles, spike_direction)),
                'zone_type': getattr(zone, 'zone_type', 'psychological'),
                'zone_strength': getattr(zone, 'strength', 50)
            }
        )
    
    def _find_spike_candle(
        self, 
        candles: List[CandlestickData], 
        zone: Zone
    ) -> Optional[Tuple[int, CandlestickData, str]]:
        """Find a spike candle that penetrates the zone"""
        
        for i, candle in enumerate(candles):
            # Calculate wick sizes
            upper_wick = float(candle.high_price - max(candle.open_price, candle.close_price))
            lower_wick = float(min(candle.open_price, candle.close_price) - candle.low_price)
            body_size = abs(float(candle.close_price - candle.open_price))
            
            # Avoid division by zero
            if body_size < 0.1:  # Very small body
                body_size = 0.1
            
            # Check for upper spike (bearish stop hunt)
            if upper_wick > body_size * self.MIN_WICK_RATIO:
                # Check if spike penetrates upper zone boundary
                if hasattr(zone, 'upper_bound') and candle.high_price > zone.upper_bound:
                    return (i, candle, 'upper')
                # For psychological levels
                elif hasattr(zone, 'price_level') and candle.high_price > zone.price_level:
                    return (i, candle, 'upper')
            
            # Check for lower spike (bullish stop hunt)
            if lower_wick > body_size * self.MIN_WICK_RATIO:
                # Check if spike penetrates lower zone boundary
                if hasattr(zone, 'lower_bound') and candle.low_price < zone.lower_bound:
                    return (i, candle, 'lower')
                # For psychological levels
                elif hasattr(zone, 'price_level') and candle.low_price < zone.price_level:
                    return (i, candle, 'lower')
        
        return None
    
    def _confirm_reversal(
        self, 
        spike_candle: CandlestickData, 
        reversal_candles: List[CandlestickData],
        spike_direction: str
    ) -> bool:
        """Confirm price reversed after the spike"""
        
        if not reversal_candles:
            return False
        
        # Need at least 1 candle for reversal confirmation
        if len(reversal_candles) > self.MAX_CANDLES_FOR_REVERSAL:
            reversal_candles = reversal_candles[:self.MAX_CANDLES_FOR_REVERSAL]
        
        if spike_direction == 'upper':
            # After upper spike, price should move down
            spike_close = float(spike_candle.close_price)
            # Check if all reversal candles closed below spike close
            all_below = all(float(c.close_price) < spike_close for c in reversal_candles)
            
            # Check if we've retraced enough of the spike
            if reversal_candles:
                lowest_close = min(float(c.close_price) for c in reversal_candles)
                spike_range = float(spike_candle.high_price - spike_candle.close_price)
                retracement = spike_close - lowest_close
                
                return all_below and (retracement >= spike_range * self.MIN_REVERSAL_PERCENT)
        
        else:  # lower spike
            # After lower spike, price should move up
            spike_close = float(spike_candle.close_price)
            # Check if all reversal candles closed above spike close
            all_above = all(float(c.close_price) > spike_close for c in reversal_candles)
            
            # Check if we've retraced enough of the spike
            if reversal_candles:
                highest_close = max(float(c.close_price) for c in reversal_candles)
                spike_range = float(spike_candle.close_price - spike_candle.low_price)
                retracement = highest_close - spike_close
                
                return all_above and (retracement >= spike_range * self.MIN_REVERSAL_PERCENT)
        
        return False
    
    def _calculate_confidence(
        self,
        spike_candle: CandlestickData,
        reversal_candles: List[CandlestickData],
        spike_direction: str,
        zone: Zone
    ) -> float:
        """Calculate confidence score for the stop hunt pattern"""
        
        confidence = 50.0  # Base confidence
        
        # 1. Wick ratio factor (larger wick = higher confidence)
        wick_ratio = self._get_wick_ratio(spike_candle, spike_direction)
        if wick_ratio > 5:
            confidence += 15
        elif wick_ratio > 4:
            confidence += 10
        elif wick_ratio > 3:
            confidence += 5
        
        # 2. Reversal strength
        reversal_strength = self._calculate_reversal_strength(spike_candle, reversal_candles, spike_direction)
        if reversal_strength > 0.7:
            confidence += 15
        elif reversal_strength > 0.5:
            confidence += 10
        elif reversal_strength > 0.3:
            confidence += 5
        
        # 3. Zone strength (if available)
        zone_strength = getattr(zone, 'strength', 50)
        if zone_strength > 80:
            confidence += 10
        elif zone_strength > 60:
            confidence += 5
        
        # 4. Number of touches on zone (if available)
        touch_count = getattr(zone, 'touch_count', 0)
        if touch_count >= 3:
            confidence += 10
        elif touch_count >= 2:
            confidence += 5
        
        # 5. Clean reversal (immediate reversal is better)
        if len(reversal_candles) == 1:
            confidence += 5
        
        return min(confidence, 95.0)  # Cap at 95%
    
    def _get_spike_size(self, candle: CandlestickData, direction: str) -> Decimal:
        """Calculate the size of the spike"""
        if direction == 'upper':
            return candle.high_price - max(candle.open_price, candle.close_price)
        else:
            return min(candle.open_price, candle.close_price) - candle.low_price
    
    def _get_wick_ratio(self, candle: CandlestickData, direction: str) -> float:
        """Calculate wick to body ratio"""
        body_size = abs(float(candle.close_price - candle.open_price))
        if body_size < 0.1:
            body_size = 0.1
        
        if direction == 'upper':
            wick_size = float(candle.high_price - max(candle.open_price, candle.close_price))
        else:
            wick_size = float(min(candle.open_price, candle.close_price) - candle.low_price)
        
        return wick_size / body_size
    
    def _calculate_reversal_strength(
        self,
        spike_candle: CandlestickData,
        reversal_candles: List[CandlestickData],
        spike_direction: str
    ) -> float:
        """Calculate how strong the reversal is (0-1)"""
        
        if not reversal_candles:
            return 0.0
        
        if spike_direction == 'upper':
            spike_range = float(spike_candle.high_price - spike_candle.close_price)
            if spike_range <= 0:
                return 0.0
            
            lowest_close = min(float(c.close_price) for c in reversal_candles)
            retracement = float(spike_candle.close_price) - lowest_close
            
        else:  # lower
            spike_range = float(spike_candle.close_price - spike_candle.low_price)
            if spike_range <= 0:
                return 0.0
            
            highest_close = max(float(c.close_price) for c in reversal_candles)
            retracement = highest_close - float(spike_candle.close_price)
        
        return min(retracement / spike_range, 1.0)
    
    def _create_psychological_zones(self, current_price: Decimal) -> List[Zone]:
        """Create psychological level zones if no zones are provided"""
        zones = []
        
        # Round levels (00, 50)
        price_int = int(current_price)
        
        # Levels to check
        levels = [
            price_int - 100,
            price_int - 50,
            price_int,
            price_int + 50,
            price_int + 100
        ]
        
        for level in levels:
            # Skip if too far from current price
            if abs(float(current_price) - level) > 100:
                continue
            
            # Create a simple zone object
            zone = type('Zone', (), {
                'price_level': Decimal(str(level)),
                'zone_type': 'psychological',
                'strength': 60,
                'touch_count': 2
            })()
            
            zones.append(zone)
        
        return zones