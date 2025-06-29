"""
Risk Reward Optimizer for US-014

Dynamically adjusts stop loss and take profit levels
based on power zone strength to maximize risk-reward ratios.
"""
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from enum import Enum
import logging

from src.domain.models.zone_multiplier import (
    ZoneInfo, MultiplierContext, RiskRewardAdjustment,
    ZoneMultiplierResult, PowerLevel, PipDistance
)


logger = logging.getLogger(__name__)


class TradeDirection(Enum):
    """Trade direction for SL/TP calculation"""
    LONG = "long"
    SHORT = "short"


class RiskRewardOptimizer:
    """Optimizes SL/TP placement for power zones"""
    
    def __init__(self):
        """Initialize optimizer"""
        pass
    
    def optimize_risk_reward(
        self, 
        context: MultiplierContext,
        multiplier_result: ZoneMultiplierResult,
        trade_direction: TradeDirection,
        entry_price: Decimal,
        default_sl_pips: int = 20,
        default_tp_pips: int = 30
    ) -> RiskRewardAdjustment:
        """
        Optimize SL/TP placement based on power zone analysis
        
        Args:
            context: Market context
            multiplier_result: Zone multiplier analysis
            trade_direction: Long or short trade
            entry_price: Planned entry price
            default_sl_pips: Default stop loss distance
            default_tp_pips: Default take profit distance
            
        Returns:
            Optimized SL/TP adjustment with enhanced RR ratio
        """
        logger.info(f"Optimizing risk-reward for {context.target_zone.zone_id}, "
                   f"Direction: {trade_direction.value}")
        
        # Calculate original distances
        original_sl_distance = Decimal(str(default_sl_pips))
        original_tp_distance = Decimal(str(default_tp_pips))
        original_rr = float(original_tp_distance / original_sl_distance)
        
        if not multiplier_result.is_power_zone:
            # No optimization for regular zones
            return self._create_no_adjustment_result(
                original_sl_distance, original_tp_distance, original_rr
            )
        
        # Calculate optimized distances based on power zone strength
        optimized_distances = self._calculate_optimized_distances(
            context, multiplier_result, trade_direction,
            original_sl_distance, original_tp_distance
        )
        
        # Validate optimized distances
        validated_distances = self._validate_optimization(
            context, optimized_distances, trade_direction, entry_price
        )
        
        # Calculate final metrics
        enhanced_rr = float(validated_distances['tp_distance'] / validated_distances['sl_distance'])
        confidence_boost = self._calculate_confidence_boost(multiplier_result)
        
        adjustment = RiskRewardAdjustment(
            original_sl_distance=original_sl_distance,
            original_tp_distance=original_tp_distance,
            original_rr_ratio=original_rr,
            
            adjusted_sl_distance=validated_distances['sl_distance'],
            adjusted_tp_distance=validated_distances['tp_distance'],
            enhanced_rr_ratio=enhanced_rr,
            
            sl_reduction_pips=original_sl_distance - validated_distances['sl_distance'],
            tp_extension_pips=validated_distances['tp_distance'] - original_tp_distance,
            confidence_boost=confidence_boost
        )
        
        logger.info(f"Risk-reward optimized: {original_rr:.2f} -> {enhanced_rr:.2f}, "
                   f"SL: {original_sl_distance} -> {validated_distances['sl_distance']}, "
                   f"TP: {original_tp_distance} -> {validated_distances['tp_distance']}")
        
        return adjustment
    
    def _calculate_optimized_distances(
        self,
        context: MultiplierContext,
        multiplier_result: ZoneMultiplierResult,
        trade_direction: TradeDirection,
        original_sl: Decimal,
        original_tp: Decimal
    ) -> Dict[str, Decimal]:
        """Calculate optimized SL/TP distances based on power zone strength"""
        
        # SL optimization: Tighter stops for power zones
        sl_reduction_factor = self._calculate_sl_reduction_factor(multiplier_result)
        optimized_sl = original_sl * Decimal(str(1.0 - sl_reduction_factor))
        
        # Minimum SL to prevent over-optimization
        min_sl = Decimal("8.0")  # Never less than 8 pips
        optimized_sl = max(optimized_sl, min_sl)
        
        # TP optimization: Extended targets for power zones
        tp_extension_factor = self._calculate_tp_extension_factor(
            context, multiplier_result, trade_direction
        )
        optimized_tp = original_tp * Decimal(str(1.0 + tp_extension_factor))
        
        # Find next major zone for TP extension
        next_zone_tp = self._find_next_major_zone_target(
            context, trade_direction, optimized_tp
        )
        
        # Use the better of calculated TP or next zone TP
        final_tp = max(optimized_tp, next_zone_tp) if next_zone_tp else optimized_tp
        
        return {
            'sl_distance': optimized_sl,
            'tp_distance': final_tp
        }
    
    def _calculate_sl_reduction_factor(self, multiplier_result: ZoneMultiplierResult) -> float:
        """Calculate how much to reduce SL based on power zone strength"""
        power_level_reductions = {
            PowerLevel.EXTREME: 0.35,    # 35% reduction for extreme zones
            PowerLevel.VERY_STRONG: 0.30, # 30% reduction
            PowerLevel.STRONG: 0.25,     # 25% reduction
            PowerLevel.MODERATE: 0.15,   # 15% reduction
            PowerLevel.WEAK: 0.05        # 5% reduction
        }
        
        base_reduction = power_level_reductions.get(multiplier_result.power_level, 0.0)
        
        # Additional reduction for specific components
        component_bonus = 0.0
        for component in multiplier_result.components:
            if component.component_type.value == "zone_ema_overlap":
                component_bonus += 0.05  # 5% more for EMA overlap
            elif component.component_type.value == "multi_zone_cluster":
                component_bonus += 0.10  # 10% more for zone clusters
        
        total_reduction = min(base_reduction + component_bonus, 0.40)  # Max 40% reduction
        
        logger.debug(f"SL reduction factor: {total_reduction:.2f} "
                    f"(base: {base_reduction}, bonus: {component_bonus})")
        
        return total_reduction
    
    def _calculate_tp_extension_factor(
        self,
        context: MultiplierContext,
        multiplier_result: ZoneMultiplierResult,
        trade_direction: TradeDirection
    ) -> float:
        """Calculate how much to extend TP based on power zone strength"""
        power_level_extensions = {
            PowerLevel.EXTREME: 2.0,     # 200% extension (3x original)
            PowerLevel.VERY_STRONG: 1.5, # 150% extension (2.5x original)
            PowerLevel.STRONG: 1.0,      # 100% extension (2x original)
            PowerLevel.MODERATE: 0.5,    # 50% extension (1.5x original)
            PowerLevel.WEAK: 0.2         # 20% extension (1.2x original)
        }
        
        base_extension = power_level_extensions.get(multiplier_result.power_level, 0.0)
        
        # Market session bonus (London/NY overlap has better follow-through)
        session_bonus = 0.0
        if context.market_session in ["london_ny_overlap", "london", "ny"]:
            session_bonus = 0.2
        
        total_extension = base_extension + session_bonus
        
        logger.debug(f"TP extension factor: {total_extension:.2f} "
                    f"(base: {base_extension}, session: {session_bonus})")
        
        return total_extension
    
    def _find_next_major_zone_target(
        self,
        context: MultiplierContext,
        trade_direction: TradeDirection,
        calculated_tp: Decimal
    ) -> Optional[Decimal]:
        """Find next major zone for TP placement"""
        target_zones = []
        current_price = context.current_price
        
        for zone in context.nearby_zones:
            # Skip zones too close (within calculated TP)
            distance = abs(zone.price_level - current_price)
            if distance <= calculated_tp:
                continue
            
            # For long trades, look for resistance zones above
            # For short trades, look for support zones below
            if trade_direction == TradeDirection.LONG:
                if (zone.zone_type == "resistance" and 
                    zone.price_level > current_price):
                    target_zones.append((zone, distance))
            else:  # SHORT
                if (zone.zone_type == "support" and 
                    zone.price_level < current_price):
                    target_zones.append((zone, distance))
        
        if not target_zones:
            return None
        
        # Find closest major zone (strength > 0.7)
        major_zones = [(zone, dist) for zone, dist in target_zones if zone.strength > 0.7]
        
        if major_zones:
            # Return distance to closest major zone
            closest_zone, distance = min(major_zones, key=lambda x: x[1])
            logger.debug(f"Next major zone target: {closest_zone.zone_id} at {distance} pips")
            return distance
        
        return None
    
    def _validate_optimization(
        self,
        context: MultiplierContext,
        optimized_distances: Dict[str, Decimal],
        trade_direction: TradeDirection,
        entry_price: Decimal
    ) -> Dict[str, Decimal]:
        """Validate and adjust optimized distances for safety"""
        sl_distance = optimized_distances['sl_distance']
        tp_distance = optimized_distances['tp_distance']
        
        # Ensure minimum RR ratio of 1:1.5 even after optimization
        min_rr = 1.5
        if tp_distance / sl_distance < Decimal(str(min_rr)):
            adjusted_tp = sl_distance * Decimal(str(min_rr))
            logger.debug(f"TP adjusted to maintain minimum RR: {tp_distance} -> {adjusted_tp}")
            tp_distance = adjusted_tp
        
        # Ensure maximum RR ratio to prevent over-optimization
        max_rr = 5.0
        if tp_distance / sl_distance > Decimal(str(max_rr)):
            adjusted_tp = sl_distance * Decimal(str(max_rr))
            logger.debug(f"TP capped to prevent over-optimization: {tp_distance} -> {adjusted_tp}")
            tp_distance = adjusted_tp
        
        # Validate SL doesn't hit target zone boundary
        validated_sl = self._validate_sl_placement(
            context, sl_distance, trade_direction, entry_price
        )
        
        return {
            'sl_distance': validated_sl,
            'tp_distance': tp_distance
        }
    
    def _validate_sl_placement(
        self,
        context: MultiplierContext,
        sl_distance: Decimal,
        trade_direction: TradeDirection,
        entry_price: Decimal
    ) -> Decimal:
        """Ensure SL placement doesn't conflict with zone boundaries"""
        # Calculate actual SL price
        if trade_direction == TradeDirection.LONG:
            sl_price = entry_price - sl_distance / Decimal("10000")  # Convert pips to price
        else:
            sl_price = entry_price + sl_distance / Decimal("10000")
        
        # Check if SL would hit the target zone itself
        target_zone = context.target_zone
        zone_boundary_buffer = Decimal("5.0")  # 5 pip buffer
        
        if trade_direction == TradeDirection.LONG:
            # For long trades, ensure SL is below the support zone
            if sl_price > (target_zone.price_level - zone_boundary_buffer / Decimal("10000")):
                # Adjust SL to be safely below zone
                safe_sl_price = target_zone.price_level - zone_boundary_buffer / Decimal("10000")
                adjusted_sl_distance = (entry_price - safe_sl_price) * Decimal("10000")
                logger.debug(f"SL adjusted to avoid zone conflict: {sl_distance} -> {adjusted_sl_distance}")
                return adjusted_sl_distance
        else:
            # For short trades, ensure SL is above the resistance zone
            if sl_price < (target_zone.price_level + zone_boundary_buffer / Decimal("10000")):
                # Adjust SL to be safely above zone
                safe_sl_price = target_zone.price_level + zone_boundary_buffer / Decimal("10000")
                adjusted_sl_distance = (safe_sl_price - entry_price) * Decimal("10000")
                logger.debug(f"SL adjusted to avoid zone conflict: {sl_distance} -> {adjusted_sl_distance}")
                return adjusted_sl_distance
        
        return sl_distance
    
    def _calculate_confidence_boost(self, multiplier_result: ZoneMultiplierResult) -> float:
        """Calculate confidence boost from power zone strength"""
        base_confidence = 0.6  # 60% base confidence
        
        # Power level boost
        power_boost = {
            PowerLevel.EXTREME: 0.35,
            PowerLevel.VERY_STRONG: 0.25,
            PowerLevel.STRONG: 0.20,
            PowerLevel.MODERATE: 0.15,
            PowerLevel.WEAK: 0.05
        }.get(multiplier_result.power_level, 0.0)
        
        # Component boost
        component_boost = len(multiplier_result.components) * 0.05  # 5% per component
        
        total_confidence = min(base_confidence + power_boost + component_boost, 0.95)  # Max 95%
        
        return total_confidence
    
    def _create_no_adjustment_result(
        self, 
        sl_distance: Decimal, 
        tp_distance: Decimal, 
        rr_ratio: float
    ) -> RiskRewardAdjustment:
        """Create result for zones that don't require optimization"""
        return RiskRewardAdjustment(
            original_sl_distance=sl_distance,
            original_tp_distance=tp_distance,
            original_rr_ratio=rr_ratio,
            
            adjusted_sl_distance=sl_distance,
            adjusted_tp_distance=tp_distance,
            enhanced_rr_ratio=rr_ratio,
            
            sl_reduction_pips=Decimal("0"),
            tp_extension_pips=Decimal("0"),
            confidence_boost=0.6  # Standard confidence
        )