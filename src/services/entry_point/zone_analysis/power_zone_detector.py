"""
Power Zone Detection Service for US-014

Detects when zones overlap with EMAs, cluster together,
or show strong role reversal patterns to identify
high-probability "power zones".
"""
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import logging

from src.domain.models.zone_multiplier import (
    ZoneInfo, EMAInfo, PowerZoneComponent, PowerZoneType,
    ZoneCluster, MultiplierContext, MultiplierConfig,
    PowerLevel, PipDistance
)


logger = logging.getLogger(__name__)


class PowerZoneDetector:
    """Detects power zones and their components"""
    
    def __init__(self, config: MultiplierConfig = None):
        """Initialize with configuration"""
        self.config = config or MultiplierConfig()
    
    def detect_power_zone_components(
        self, 
        context: MultiplierContext
    ) -> List[PowerZoneComponent]:
        """
        Detect all power zone components for a given zone
        
        Returns list of components that contribute to power zone status
        """
        components = []
        
        # Check EMA overlaps
        ema_components = self._detect_ema_overlaps(
            context.target_zone, 
            context.ema_values
        )
        components.extend(ema_components)
        
        # Check multi-zone clusters
        cluster_component = self._detect_zone_cluster(
            context.target_zone,
            context.nearby_zones
        )
        if cluster_component:
            components.append(cluster_component)
        
        # Check role reversal history
        reversal_component = self._detect_role_reversal(
            context.target_zone
        )
        if reversal_component:
            components.append(reversal_component)
        
        # Check multi-timeframe zones
        mtf_component = self._detect_multi_timeframe_zones(
            context.target_zone,
            context.nearby_zones
        )
        if mtf_component:
            components.append(mtf_component)
        
        # Check psychological level proximity
        psych_component = self._detect_psychological_level(
            context.target_zone,
            context.psychological_levels
        )
        if psych_component:
            components.append(psych_component)
        
        logger.info(f"Detected {len(components)} power zone components for zone {context.target_zone.zone_id}")
        return components
    
    def _detect_ema_overlaps(
        self, 
        zone: ZoneInfo, 
        ema_values: List[EMAInfo]
    ) -> List[PowerZoneComponent]:
        """Detect overlaps between zone and EMA lines"""
        components = []
        
        for ema in ema_values:
            # Only check major EMAs (200, 75)
            if ema.period not in [200, 75]:
                continue
            
            distance = abs(zone.price_level - ema.value)
            
            # Check if within overlap threshold
            if distance <= self.config.ema_overlap_distance_pips:
                component = PowerZoneComponent(
                    component_type=PowerZoneType.ZONE_EMA_OVERLAP,
                    zone_id=zone.zone_id,
                    ema_period=ema.period,
                    distance=distance,
                    multiplier_contribution=self._calculate_ema_multiplier(ema.period, distance)
                )
                components.append(component)
                
                logger.debug(f"EMA{ema.period} overlap detected: distance={distance} pips")
        
        return components
    
    def _detect_zone_cluster(
        self, 
        target_zone: ZoneInfo, 
        nearby_zones: List[ZoneInfo]
    ) -> Optional[PowerZoneComponent]:
        """Detect clusters of multiple zones"""
        cluster_zones = [target_zone]
        
        # Find zones within cluster distance
        for zone in nearby_zones:
            if zone.zone_id == target_zone.zone_id:
                continue
            
            distance = abs(zone.price_level - target_zone.price_level)
            if distance <= self.config.cluster_distance_pips:
                cluster_zones.append(zone)
        
        # Check if we have enough zones for a cluster
        if len(cluster_zones) >= self.config.min_cluster_zones:
            zone_ids = [z.zone_id for z in cluster_zones]
            span = self._calculate_cluster_span(cluster_zones)
            
            component = PowerZoneComponent(
                component_type=PowerZoneType.MULTI_ZONE_CLUSTER,
                zones=zone_ids,
                span=span,
                multiplier_contribution=self._calculate_cluster_multiplier(len(cluster_zones))
            )
            
            logger.debug(f"Zone cluster detected: {len(cluster_zones)} zones, span={span} pips")
            return component
        
        return None
    
    def _detect_role_reversal(self, zone: ZoneInfo) -> Optional[PowerZoneComponent]:
        """Detect zones with strong role reversal history"""
        if len(zone.role_history) < self.config.min_role_reversals:
            return None
        
        # Count role changes
        role_changes = 0
        for i in range(1, len(zone.role_history)):
            if zone.role_history[i] != zone.role_history[i-1]:
                role_changes += 1
        
        # Strong reversal requires multiple role changes
        if role_changes >= self.config.min_role_reversals:
            component = PowerZoneComponent(
                component_type=PowerZoneType.ROLE_REVERSAL,
                zone_id=zone.zone_id,
                history=zone.role_history.copy(),
                multiplier_contribution=self._calculate_reversal_multiplier(role_changes)
            )
            
            logger.debug(f"Role reversal detected: {role_changes} changes in {zone.zone_id}")
            return component
        
        return None
    
    def _detect_multi_timeframe_zones(
        self, 
        target_zone: ZoneInfo, 
        nearby_zones: List[ZoneInfo]
    ) -> Optional[PowerZoneComponent]:
        """Detect zones that appear across multiple timeframes"""
        timeframes = {target_zone.timeframe}
        matching_zones = [target_zone.zone_id]
        
        # Find zones at similar price levels from different timeframes
        for zone in nearby_zones:
            if zone.timeframe != target_zone.timeframe:
                distance = abs(zone.price_level - target_zone.price_level)
                if distance <= self.config.ema_overlap_distance_pips:  # tight tolerance for MTF
                    timeframes.add(zone.timeframe)
                    matching_zones.append(zone.zone_id)
        
        # Multi-timeframe requires at least 2 different timeframes
        if len(timeframes) >= 2:
            component = PowerZoneComponent(
                component_type=PowerZoneType.MULTI_TIMEFRAME,
                zones=matching_zones,
                multiplier_contribution=self.config.multi_timeframe_multiplier
            )
            
            logger.debug(f"Multi-timeframe zone detected: {timeframes}")
            return component
        
        return None
    
    def _detect_psychological_level(
        self, 
        zone: ZoneInfo, 
        psychological_levels: List[Decimal]
    ) -> Optional[PowerZoneComponent]:
        """Detect zones near psychological price levels"""
        for level in psychological_levels:
            distance = abs(zone.price_level - level)
            
            # Very tight tolerance for psychological levels
            if distance <= Decimal("5.0"):  # 5 pips
                component = PowerZoneComponent(
                    component_type=PowerZoneType.PSYCHOLOGICAL_LEVEL,
                    zone_id=zone.zone_id,
                    distance=distance,
                    multiplier_contribution=self.config.psychological_level_multiplier
                )
                
                logger.debug(f"Psychological level detected: {level}, distance={distance}")
                return component
        
        return None
    
    def _calculate_ema_multiplier(self, ema_period: int, distance: Decimal) -> float:
        """Calculate EMA overlap multiplier based on period and distance"""
        base_multiplier = self.config.ema_overlap_multiplier
        
        # 200 EMA gets higher multiplier than 75 EMA
        if ema_period == 200:
            period_bonus = 0.2
        elif ema_period == 75:
            period_bonus = 0.1
        else:
            period_bonus = 0.0
        
        # Closer distance gets higher multiplier
        distance_factor = max(0.0, 1.0 - float(distance) / 10.0)  # reduces as distance increases
        
        return base_multiplier + period_bonus + (distance_factor * 0.1)
    
    def _calculate_cluster_multiplier(self, zone_count: int) -> float:
        """Calculate cluster multiplier based on number of zones"""
        if zone_count >= 5:
            return self.config.multi_zone_multiplier * 1.2  # 2.4x for 5+ zones
        elif zone_count >= 4:
            return self.config.multi_zone_multiplier * 1.1  # 2.2x for 4 zones
        elif zone_count >= 3:
            return self.config.multi_zone_multiplier  # 2.0x for 3 zones
        else:
            return 1.0  # no cluster bonus
    
    def _calculate_reversal_multiplier(self, role_changes: int) -> float:
        """Calculate role reversal multiplier based on change frequency"""
        base = self.config.role_reversal_multiplier
        
        # More role changes = stronger zone
        if role_changes >= 4:
            return base * 1.2  # 1.56x for frequent reversals
        elif role_changes >= 3:
            return base * 1.1  # 1.43x for moderate reversals
        else:
            return base  # 1.3x for basic reversals
    
    def _calculate_cluster_span(self, zones: List[ZoneInfo]) -> Decimal:
        """Calculate the price span of a zone cluster"""
        if not zones:
            return Decimal("0")
        
        prices = [zone.price_level for zone in zones]
        return max(prices) - min(prices)
    
    def determine_power_level(self, final_multiplier: float) -> PowerLevel:
        """Determine power level based on final multiplier"""
        for threshold, level in sorted(self.config.power_level_thresholds.items(), reverse=True):
            if final_multiplier >= threshold:
                return level
        return PowerLevel.WEAK
    
    def is_power_zone(self, components: List[PowerZoneComponent]) -> bool:
        """Determine if zone qualifies as a power zone"""
        if not components:
            return False
        
        # Power zone requires at least one significant component
        significant_components = [
            PowerZoneType.ZONE_EMA_OVERLAP,
            PowerZoneType.MULTI_ZONE_CLUSTER,
            PowerZoneType.ROLE_REVERSAL
        ]
        
        return any(comp.component_type in significant_components for comp in components)