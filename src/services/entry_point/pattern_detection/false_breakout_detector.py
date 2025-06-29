"""
False Breakout Pattern Detector

Detects false breakout patterns where price temporarily breaks through a zone
but quickly returns, creating opportunities to trade against retail sentiment.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import uuid

from src.domain.models.pattern import PatternSignal, PatternType
from src.domain.models.market import MarketContext
from src.models.candlestick import CandlestickData
from .base_detector import BasePatternDetector


class FalseBreakoutDetector(BasePatternDetector):
    """Detector for false breakout patterns"""
    
    # Configuration parameters
    MIN_BREAKOUT_DEPTH = Decimal('20')  # Minimum breakout depth in pips
    MAX_BREAKOUT_DURATION = 5  # Maximum candles for valid false breakout
    MIN_RETURN_SPEED_RATIO = 0.5  # Return speed vs breakout speed ratio
    MIN_SPIKE_WICK_RATIO = 3.0  # Wick to body ratio for spike detection
    ZONE_PROXIMITY_THRESHOLD = Decimal('5')  # Pips for zone proximity
    MIN_ZONE_STRENGTH_TOUCHES = 2  # Minimum touches for zone strength
    
    async def detect(self, context: MarketContext) -> List[PatternSignal]:
        """Detect false breakout pattern"""
        # Need at least 20 candles for analysis
        if len(context.recent_candles) < 20:
            return []
        
        # Must have nearby zones to break
        if not context.nearby_zones:
            return []
        
        # Step 1: Find recent zone breakouts
        breakout_info = self._detect_zone_breakouts(context)
        if not breakout_info:
            return []
        
        # Step 2: Check for false breakout conditions
        false_breakout_validation = self._validate_false_breakout(context, breakout_info)
        if not false_breakout_validation['is_false_breakout']:
            return []
        
        # Step 3: Identify stop hunting patterns
        stop_hunt_signals = self._detect_stop_hunting(context, breakout_info)
        
        # Step 4: Validate entry timing
        entry_timing = self._validate_entry_timing(context, breakout_info)
        if not entry_timing['is_valid_entry']:
            return []
        
        # Step 5: Calculate confidence score
        confidence = self._calculate_confidence(
            breakout_info, false_breakout_validation, stop_hunt_signals, entry_timing, context
        )
        
        # Create pattern signal
        pattern = PatternSignal(
            id=str(uuid.uuid4()),
            symbol=context.symbol,
            timeframe=context.current_candle.timeframe,
            pattern_type=PatternType.FALSE_BREAKOUT,
            detected_at=context.timestamp,
            price_level=context.current_candle.close_price,
            confidence=confidence,
            parameters={
                'breakout_depth': float(breakout_info['breakout_depth']),
                'return_speed': float(false_breakout_validation['return_speed']),
                'zone_strength': breakout_info['target_zone']['strength'],
                'spike_detected': stop_hunt_signals['has_spike'],
                'volume_surge': stop_hunt_signals.get('volume_ratio', 1.0),
                'breakout_direction': breakout_info['breakout_direction'],
                'return_duration': false_breakout_validation['return_duration'],
                'zone_id': breakout_info['target_zone']['id'],
                'risk_reward_ratio': entry_timing['risk_reward_ratio']
            },
            zone_id=str(breakout_info['target_zone']['id'])
        )
        
        return [pattern]
    
    def _detect_zone_breakouts(self, context: MarketContext) -> Optional[Dict[str, Any]]:
        """Detect recent zone breakouts in the last 10 candles"""
        all_candles = context.recent_candles + [context.current_candle]
        recent_candles = all_candles[-10:]  # Look at last 10 candles
        
        for zone in context.nearby_zones:
            # Check if we had a recent breakout of this zone
            breakout_info = self._analyze_zone_breakout(recent_candles, zone, context)
            if breakout_info:
                return breakout_info
        
        return None
    
    def _analyze_zone_breakout(self, candles: List[CandlestickData], zone, context: MarketContext) -> Optional[Dict[str, Any]]:
        """Analyze if there was a breakout of the given zone"""
        current_price = context.current_candle.close_price
        
        # Check if we're currently back inside the zone
        if not zone.contains_price(current_price):
            return None
        
        # Look for candles that broke the zone
        breakout_candles = []
        max_breakout_depth = Decimal('0')
        breakout_direction = None
        
        for i, candle in enumerate(candles):
            # Check for upward breakout (above zone upper bound)
            if candle.close_price > zone.upper_bound:
                depth = candle.close_price - zone.upper_bound
                if depth >= self.MIN_BREAKOUT_DEPTH:
                    breakout_candles.append({
                        'candle': candle,
                        'index': i,
                        'depth': depth,
                        'direction': 'upward'
                    })
                    if depth > max_breakout_depth:
                        max_breakout_depth = depth
                        breakout_direction = 'upward'
            
            # Check for downward breakout (below zone lower bound)
            elif candle.close_price < zone.lower_bound:
                depth = zone.lower_bound - candle.close_price
                if depth >= self.MIN_BREAKOUT_DEPTH:
                    breakout_candles.append({
                        'candle': candle,
                        'index': i,
                        'depth': depth,
                        'direction': 'downward'
                    })
                    if depth > max_breakout_depth:
                        max_breakout_depth = depth
                        breakout_direction = 'downward'
        
        if not breakout_candles:
            return None
        
        # Find the most recent significant breakout
        latest_breakout = max(breakout_candles, key=lambda x: x['index'])
        
        # Check if breakout was recent enough (within MAX_BREAKOUT_DURATION)
        candles_since_breakout = len(candles) - 1 - latest_breakout['index']
        if candles_since_breakout > self.MAX_BREAKOUT_DURATION:
            return None
        
        return {
            'target_zone': {
                'id': zone.id,
                'upper_bound': zone.upper_bound,
                'lower_bound': zone.lower_bound,
                'strength': zone.strength,
                'touch_count': zone.touch_count
            },
            'breakout_depth': max_breakout_depth,
            'breakout_direction': breakout_direction,
            'breakout_candle': latest_breakout['candle'],
            'candles_since_breakout': candles_since_breakout,
            'total_breakout_candles': len(breakout_candles)
        }
    
    def _validate_false_breakout(self, context: MarketContext, breakout_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that this is indeed a false breakout"""
        all_candles = context.recent_candles + [context.current_candle]
        
        # Find breakout candle index in full candle list
        breakout_candle = breakout_info['breakout_candle']
        breakout_index = None
        
        for i, candle in enumerate(all_candles):
            if (candle.open_time == breakout_candle.open_time and 
                candle.close_price == breakout_candle.close_price):
                breakout_index = i
                break
        
        if breakout_index is None:
            return {'is_false_breakout': False}
        
        # Analyze return to zone
        candles_after_breakout = all_candles[breakout_index + 1:]
        return_duration = len(candles_after_breakout)
        
        # Check return speed
        breakout_depth = breakout_info['breakout_depth']
        
        # Calculate how quickly price returned to zone
        if return_duration > 0:
            return_speed = breakout_depth / return_duration  # pips per candle
        else:
            return_speed = Decimal('0')
        
        # Calculate breakout speed for comparison
        # Assume breakout happened over 1-2 candles
        breakout_speed = breakout_depth / 2  # Conservative estimate
        
        # Check if return was faster than breakout
        speed_ratio = float(return_speed / breakout_speed) if breakout_speed > 0 else 0
        
        # Validate false breakout conditions
        is_false_breakout = (
            return_duration <= self.MAX_BREAKOUT_DURATION and
            speed_ratio >= self.MIN_RETURN_SPEED_RATIO
        )
        
        return {
            'is_false_breakout': is_false_breakout,
            'return_duration': return_duration,
            'return_speed': return_speed,
            'breakout_speed': breakout_speed,
            'speed_ratio': speed_ratio
        }
    
    def _detect_stop_hunting(self, context: MarketContext, breakout_info: Dict[str, Any]) -> Dict[str, Any]:
        """Detect stop hunting patterns (spikes with large wicks)"""
        all_candles = context.recent_candles + [context.current_candle]
        
        # Look for spike candles around the breakout
        spike_signals = []
        volume_surge = 1.0
        
        # Check the breakout candle and surrounding candles
        breakout_candle = breakout_info['breakout_candle']
        
        for candle in all_candles[-5:]:  # Check last 5 candles
            # Calculate wick to body ratio
            if candle.body_size > 0:
                upper_wick_ratio = float(candle.upper_wick / candle.body_size)
                lower_wick_ratio = float(candle.lower_wick / candle.body_size)
                max_wick_ratio = max(upper_wick_ratio, lower_wick_ratio)
                
                # Check for spike pattern
                if max_wick_ratio >= self.MIN_SPIKE_WICK_RATIO:
                    spike_signals.append({
                        'candle': candle,
                        'wick_ratio': max_wick_ratio,
                        'spike_direction': 'upper' if upper_wick_ratio > lower_wick_ratio else 'lower'
                    })
            else:
                # Handle doji/small body cases - check for large wicks
                total_range = candle.high_price - candle.low_price
                if total_range >= Decimal('15'):  # Large range indicates spike
                    spike_signals.append({
                        'candle': candle,
                        'wick_ratio': float(total_range),  # Use total range as indicator
                        'spike_direction': 'large_range'
                    })
        
        # Check volume surge (using tick_count as proxy)
        if len(all_candles) >= 5:
            recent_volume = sum(c.tick_count for c in all_candles[-3:]) / 3
            baseline_volume = sum(c.tick_count for c in all_candles[-8:-3]) / 5
            
            if baseline_volume > 0:
                volume_surge = recent_volume / baseline_volume
        
        has_spike = len(spike_signals) > 0
        
        return {
            'has_spike': has_spike,
            'spike_count': len(spike_signals),
            'volume_ratio': volume_surge,
            'spike_details': spike_signals
        }
    
    def _validate_entry_timing(self, context: MarketContext, breakout_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate if this is a good entry timing"""
        current_price = context.current_candle.close_price
        zone = breakout_info['target_zone']
        
        # Check zone stability (multiple candles back in zone)
        all_candles = context.recent_candles + [context.current_candle]
        recent_candles = all_candles[-3:]  # Last 3 candles
        
        candles_in_zone = 0
        for candle in recent_candles:
            if (zone['lower_bound'] <= candle.close_price <= zone['upper_bound']):
                candles_in_zone += 1
        
        zone_stability = candles_in_zone >= 2  # At least 2 of last 3 candles in zone
        
        # Check for momentum in reversal direction
        breakout_direction = breakout_info['breakout_direction']
        expected_reversal_direction = 'bearish' if breakout_direction == 'upward' else 'bullish'
        
        # Count reversal momentum candles
        reversal_candles = 0
        for candle in recent_candles:
            if ((expected_reversal_direction == 'bullish' and candle.is_bullish) or
                (expected_reversal_direction == 'bearish' and candle.is_bearish)):
                reversal_candles += 1
        
        momentum_confirmation = reversal_candles >= 2
        
        # Calculate risk-reward ratio
        zone_height = zone['upper_bound'] - zone['lower_bound']
        
        if breakout_direction == 'upward':
            # Expect bearish reversal
            stop_loss = zone['upper_bound'] + Decimal('10')  # 10 pips above zone
            target = zone['lower_bound'] - zone_height  # Zone height below lower bound
        else:
            # Expect bullish reversal
            stop_loss = zone['lower_bound'] - Decimal('10')  # 10 pips below zone
            target = zone['upper_bound'] + zone_height  # Zone height above upper bound
        
        risk = abs(current_price - stop_loss)
        reward = abs(target - current_price)
        
        risk_reward_ratio = float(reward / risk) if risk > 0 else 0
        
        is_valid_entry = (
            zone_stability and
            momentum_confirmation and
            risk_reward_ratio >= 0.5  # Minimum 1:2 RR (we're in a good position)
        )
        
        return {
            'is_valid_entry': is_valid_entry,
            'zone_stability': zone_stability,
            'momentum_confirmation': momentum_confirmation,
            'risk_reward_ratio': risk_reward_ratio,
            'reversal_direction': expected_reversal_direction
        }
    
    def _calculate_confidence(
        self,
        breakout_info: Dict[str, Any],
        false_breakout_validation: Dict[str, Any],
        stop_hunt_signals: Dict[str, Any],
        entry_timing: Dict[str, Any],
        context: MarketContext
    ) -> float:
        """Calculate pattern confidence score (0-100)"""
        confidence = 50.0  # Base confidence
        
        # Zone strength factor
        zone_strength = breakout_info['target_zone']['strength']
        if zone_strength == 'S':  # Strong zone
            confidence += 20
        elif zone_strength == 'A':
            confidence += 15
        elif zone_strength == 'B':
            confidence += 10
        else:
            confidence += 5
        
        # Zone touch count factor
        touch_count = breakout_info['target_zone']['touch_count']
        if touch_count >= 5:
            confidence += 10
        elif touch_count >= 3:
            confidence += 5
        
        # Breakout depth factor
        breakout_depth = float(breakout_info['breakout_depth'])
        if 20 <= breakout_depth <= 30:  # Ideal depth
            confidence += 10
        elif 15 <= breakout_depth <= 40:
            confidence += 5
        
        # Return speed factor
        speed_ratio = false_breakout_validation['speed_ratio']
        if speed_ratio >= 2.0:
            confidence += 15
        elif speed_ratio >= 1.5:
            confidence += 10
        elif speed_ratio >= 1.2:
            confidence += 5
        
        # Stop hunting signals
        if stop_hunt_signals['has_spike']:
            confidence += 10
        
        volume_ratio = stop_hunt_signals.get('volume_ratio', 1.0)
        if volume_ratio >= 1.5:
            confidence += 5
        
        # Entry timing factors
        if entry_timing['zone_stability']:
            confidence += 10
        
        if entry_timing['momentum_confirmation']:
            confidence += 10
        
        # Risk-reward bonus
        rr_ratio = entry_timing['risk_reward_ratio']
        if rr_ratio >= 3.0:
            confidence += 10
        elif rr_ratio >= 2.5:
            confidence += 5
        
        # Return duration factor (faster return is better)
        return_duration = false_breakout_validation['return_duration']
        if return_duration <= 3:
            confidence += 10
        elif return_duration <= 4:
            confidence += 5
        
        return min(100.0, max(0.0, confidence))