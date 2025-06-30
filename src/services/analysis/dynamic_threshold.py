"""
Dynamic Threshold Adjustment System

Adjusts detection thresholds based on market volatility using ATR.
"""
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

from src.models.candlestick import CandlestickData


class DynamicThresholdCalculator:
    """Calculate dynamic thresholds based on market conditions"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Base thresholds (in pips)
        self.base_thresholds = {
            'drop_pips': Decimal('30'),
            'reversal_pips': Decimal('5'),
            'zone_width': Decimal('15'),
            'ema_distance': Decimal('3'),
            'breakout_depth': Decimal('10'),
            'spike_size': Decimal('20'),
            'pin_bar_wick': Decimal('15'),
            'squeeze_deviation': Decimal('3'),
            'trend_pullback': Decimal('20')
        }
        
        # Volatility adjustment limits
        self.min_multiplier = Decimal('0.5')
        self.max_multiplier = Decimal('2.0')
        
    def calculate_dynamic_threshold(
        self,
        threshold_type: str,
        candles: List[CandlestickData],
        atr_period: int = 14
    ) -> Decimal:
        """
        Calculate dynamic threshold based on ATR
        
        Args:
            threshold_type: Type of threshold to calculate
            candles: Recent candlestick data
            atr_period: Period for ATR calculation
            
        Returns:
            Adjusted threshold value
        """
        if threshold_type not in self.base_thresholds:
            self.logger.warning(f"Unknown threshold type: {threshold_type}")
            return self.base_thresholds.get('drop_pips', Decimal('10'))
        
        # Calculate current ATR
        current_atr = self._calculate_atr(candles, atr_period)
        if not current_atr:
            return self.base_thresholds[threshold_type]
        
        # Calculate long-term average ATR
        avg_atr = self._calculate_average_atr(candles, atr_period)
        if not avg_atr or avg_atr == 0:
            return self.base_thresholds[threshold_type]
        
        # Calculate volatility ratio
        volatility_ratio = current_atr / avg_atr
        
        # Apply adjustment with limits
        multiplier = max(self.min_multiplier, min(volatility_ratio, self.max_multiplier))
        
        # Calculate adjusted threshold
        base_value = self.base_thresholds[threshold_type]
        adjusted_value = base_value * multiplier
        
        # Apply specific rules for different threshold types
        adjusted_value = self._apply_threshold_rules(
            threshold_type, 
            adjusted_value, 
            base_value,
            current_atr
        )
        
        self.logger.debug(
            f"Dynamic threshold for {threshold_type}: "
            f"base={base_value}, multiplier={multiplier:.2f}, "
            f"adjusted={adjusted_value:.2f}"
        )
        
        return adjusted_value
    
    def calculate_all_thresholds(
        self,
        candles: List[CandlestickData]
    ) -> Dict[str, Decimal]:
        """Calculate all dynamic thresholds at once"""
        
        thresholds = {}
        for threshold_type in self.base_thresholds:
            thresholds[threshold_type] = self.calculate_dynamic_threshold(
                threshold_type, 
                candles
            )
        
        return thresholds
    
    def get_volatility_state(
        self,
        candles: List[CandlestickData]
    ) -> Dict[str, any]:
        """Get current volatility state and metrics"""
        
        current_atr = self._calculate_atr(candles, 14)
        avg_atr = self._calculate_average_atr(candles, 14)
        
        if not current_atr or not avg_atr or avg_atr == 0:
            return {
                'state': 'unknown',
                'current_atr': Decimal('0'),
                'average_atr': Decimal('0'),
                'ratio': Decimal('1'),
                'description': 'Unable to calculate volatility'
            }
        
        ratio = current_atr / avg_atr
        
        # Determine volatility state
        if ratio < Decimal('0.7'):
            state = 'low'
            description = 'Low volatility - tighter thresholds'
        elif ratio < Decimal('1.3'):
            state = 'normal'
            description = 'Normal volatility'
        elif ratio < Decimal('1.7'):
            state = 'high'
            description = 'High volatility - wider thresholds'
        else:
            state = 'extreme'
            description = 'Extreme volatility - maximum thresholds'
        
        return {
            'state': state,
            'current_atr': current_atr,
            'average_atr': avg_atr,
            'ratio': ratio,
            'description': description
        }
    
    def _calculate_atr(
        self,
        candles: List[CandlestickData],
        period: int = 14
    ) -> Optional[Decimal]:
        """Calculate Average True Range"""
        
        if len(candles) < period + 1:
            return None
        
        true_ranges = []
        
        for i in range(1, len(candles)):
            current = candles[i]
            previous = candles[i - 1]
            
            # True Range = max of:
            # 1. Current High - Current Low
            # 2. |Current High - Previous Close|
            # 3. |Current Low - Previous Close|
            high_low = current.high_price - current.low_price
            high_close = abs(current.high_price - previous.close_price)
            low_close = abs(current.low_price - previous.close_price)
            
            true_range = max(high_low, high_close, low_close)
            true_ranges.append(true_range)
        
        if len(true_ranges) < period:
            return None
        
        # Simple moving average of true ranges
        recent_ranges = true_ranges[-period:]
        atr = sum(recent_ranges) / len(recent_ranges)
        
        return atr
    
    def _calculate_average_atr(
        self,
        candles: List[CandlestickData],
        period: int = 14,
        lookback_periods: int = 7
    ) -> Optional[Decimal]:
        """Calculate average ATR over multiple periods"""
        
        if len(candles) < period * lookback_periods:
            # If not enough data, use current ATR
            return self._calculate_atr(candles, period)
        
        atr_values = []
        
        # Calculate ATR for each lookback period
        for i in range(lookback_periods):
            start_idx = -(period * (i + 1))
            end_idx = -(period * i) if i > 0 else None
            
            period_candles = candles[start_idx:end_idx]
            if len(period_candles) >= period + 1:
                atr = self._calculate_atr(period_candles, period)
                if atr:
                    atr_values.append(atr)
        
        if not atr_values:
            return None
        
        return sum(atr_values) / len(atr_values)
    
    def _apply_threshold_rules(
        self,
        threshold_type: str,
        adjusted_value: Decimal,
        base_value: Decimal,
        current_atr: Decimal
    ) -> Decimal:
        """Apply specific rules for different threshold types"""
        
        # Minimum values to prevent too tight thresholds
        min_values = {
            'drop_pips': Decimal('15'),
            'reversal_pips': Decimal('3'),
            'zone_width': Decimal('8'),
            'ema_distance': Decimal('2'),
            'breakout_depth': Decimal('5'),
            'spike_size': Decimal('10'),
            'pin_bar_wick': Decimal('8'),
            'squeeze_deviation': Decimal('2'),
            'trend_pullback': Decimal('10')
        }
        
        # Maximum values to prevent too loose thresholds
        max_values = {
            'drop_pips': Decimal('60'),
            'reversal_pips': Decimal('10'),
            'zone_width': Decimal('30'),
            'ema_distance': Decimal('6'),
            'breakout_depth': Decimal('20'),
            'spike_size': Decimal('40'),
            'pin_bar_wick': Decimal('30'),
            'squeeze_deviation': Decimal('6'),
            'trend_pullback': Decimal('40')
        }
        
        # Apply min/max limits
        min_val = min_values.get(threshold_type, base_value * self.min_multiplier)
        max_val = max_values.get(threshold_type, base_value * self.max_multiplier)
        
        adjusted_value = max(min_val, min(adjusted_value, max_val))
        
        # Special rules for certain thresholds
        if threshold_type == 'ema_distance':
            # EMA distance should be proportional to ATR but more conservative
            adjusted_value = min(adjusted_value, current_atr * Decimal('0.3'))
        
        elif threshold_type == 'squeeze_deviation':
            # Squeeze deviation should be very tight even in high volatility
            adjusted_value = min(adjusted_value, current_atr * Decimal('0.2'))
        
        elif threshold_type == 'zone_width':
            # Zone width should be at least 0.5 * ATR
            adjusted_value = max(adjusted_value, current_atr * Decimal('0.5'))
        
        return adjusted_value
    
    def adjust_confidence_by_volatility(
        self,
        base_confidence: float,
        candles: List[CandlestickData]
    ) -> float:
        """Adjust pattern confidence based on volatility state"""
        
        vol_state = self.get_volatility_state(candles)
        
        # Adjust confidence based on volatility
        if vol_state['state'] == 'extreme':
            # Lower confidence in extreme volatility
            return base_confidence * 0.8
        elif vol_state['state'] == 'low':
            # Slightly lower confidence in very low volatility (potential breakout)
            return base_confidence * 0.9
        else:
            # Normal or high volatility is ideal
            return base_confidence
    
    def get_threshold_explanation(
        self,
        threshold_type: str,
        candles: List[CandlestickData]
    ) -> str:
        """Get human-readable explanation of threshold adjustment"""
        
        base = self.base_thresholds.get(threshold_type, Decimal('10'))
        adjusted = self.calculate_dynamic_threshold(threshold_type, candles)
        vol_state = self.get_volatility_state(candles)
        
        ratio = adjusted / base if base > 0 else Decimal('1')
        
        if ratio > Decimal('1.5'):
            adjustment = "significantly increased"
        elif ratio > Decimal('1.2'):
            adjustment = "increased"
        elif ratio < Decimal('0.5'):
            adjustment = "significantly decreased"
        elif ratio < Decimal('0.8'):
            adjustment = "decreased"
        else:
            adjustment = "normal"
        
        return (
            f"{threshold_type}: {adjusted:.1f} pips "
            f"({adjustment} from base {base:.1f} due to {vol_state['state']} volatility)"
        )