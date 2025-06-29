"""
Zone Multiplier Scoring Engine for US-014

Calculates score multipliers based on power zone components
and applies them to enhance zone scoring with caps and limits.
"""
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import logging

from src.domain.models.zone_multiplier import (
    ZoneInfo, PowerZoneComponent, ZoneMultiplierResult,
    MultiplierContext, MultiplierConfig, PowerLevel,
    RiskRewardAdjustment
)
from src.services.entry_point.zone_analysis.power_zone_detector import PowerZoneDetector


logger = logging.getLogger(__name__)


class ZoneMultiplierEngine:
    """Main engine for calculating zone multipliers and enhanced scoring"""
    
    def __init__(self, config: MultiplierConfig = None):
        """Initialize with configuration"""
        self.config = config or MultiplierConfig()
        self.power_zone_detector = PowerZoneDetector(self.config)
    
    def calculate_zone_multiplier(
        self, 
        context: MultiplierContext,
        original_zone_score: float
    ) -> ZoneMultiplierResult:
        """
        Calculate complete zone multiplier result
        
        Args:
            context: Zone and market context
            original_zone_score: Base zone score before multiplication
            
        Returns:
            Complete multiplier result with all enhancements
        """
        logger.info(f"Calculating zone multiplier for {context.target_zone.zone_id}")
        
        # Step 1: Detect power zone components
        components = self.power_zone_detector.detect_power_zone_components(context)
        
        # Step 2: Calculate individual multipliers
        multipliers = self._calculate_individual_multipliers(components)
        
        # Step 3: Calculate final multiplier (with cap)
        final_multiplier = self._calculate_final_multiplier(multipliers)
        
        # Step 4: Determine if this is a power zone
        is_power_zone = self.power_zone_detector.is_power_zone(components)
        power_level = self.power_zone_detector.determine_power_level(final_multiplier)
        
        # Step 5: Calculate enhanced scores
        enhanced_scores = self._calculate_enhanced_scores(original_zone_score, final_multiplier)
        
        # Step 6: Calculate risk-reward enhancements
        rr_enhancement = self._calculate_risk_reward_enhancement(
            context, final_multiplier, is_power_zone
        )
        
        # Step 7: Calculate execution priority
        priority_info = self._calculate_execution_priority(
            context, final_multiplier, is_power_zone
        )
        
        # Create comprehensive result
        result = ZoneMultiplierResult(
            # Zone analysis
            is_power_zone=is_power_zone,
            power_level=power_level,
            components=components,
            
            # Score multipliers
            base_multiplier=1.0,
            ema_overlap_multiplier=multipliers.get('ema_overlap', 1.0),
            multi_zone_multiplier=multipliers.get('multi_zone', 1.0),
            role_reversal_multiplier=multipliers.get('role_reversal', 1.0),
            multi_timeframe_multiplier=multipliers.get('multi_timeframe', 1.0),
            final_multiplier=final_multiplier,
            
            # Enhanced scores
            original_zone_score=original_zone_score,
            multiplied_zone_score=enhanced_scores['multiplied_score'],
            total_score_boost=enhanced_scores['score_boost'],
            
            # Risk reward enhancement
            original_rr=rr_enhancement['original_rr'],
            enhanced_rr=rr_enhancement['enhanced_rr'],
            sl_reduction_percent=rr_enhancement['sl_reduction_percent'],
            tp_extension_percent=rr_enhancement['tp_extension_percent'],
            recommended_size_multiplier=rr_enhancement['size_multiplier'],
            
            # Execution priority
            base_priority=priority_info['base_priority'],
            power_zone_boost=priority_info['power_zone_boost'],
            final_priority=priority_info['final_priority'],
            immediate_execution=priority_info['immediate_execution']
        )
        
        logger.info(f"Zone multiplier calculated: {final_multiplier:.2f}x, "
                   f"Power Zone: {is_power_zone}, Level: {power_level.name}")
        
        return result
    
    def _calculate_individual_multipliers(
        self, 
        components: List[PowerZoneComponent]
    ) -> Dict[str, float]:
        """Calculate individual multiplier values for each component type"""
        multipliers = {}
        
        for component in components:
            if component.component_type.value == "zone_ema_overlap":
                multipliers['ema_overlap'] = max(
                    multipliers.get('ema_overlap', 1.0),
                    component.multiplier_contribution
                )
            
            elif component.component_type.value == "multi_zone_cluster":
                multipliers['multi_zone'] = max(
                    multipliers.get('multi_zone', 1.0),
                    component.multiplier_contribution
                )
            
            elif component.component_type.value == "role_reversal":
                multipliers['role_reversal'] = max(
                    multipliers.get('role_reversal', 1.0),
                    component.multiplier_contribution
                )
            
            elif component.component_type.value == "multi_timeframe":
                multipliers['multi_timeframe'] = max(
                    multipliers.get('multi_timeframe', 1.0),
                    component.multiplier_contribution
                )
        
        logger.debug(f"Individual multipliers: {multipliers}")
        return multipliers
    
    def _calculate_final_multiplier(self, multipliers: Dict[str, float]) -> float:
        """Calculate final multiplier with cap applied"""
        # Start with base multiplier
        final_multiplier = 1.0
        
        # Apply each multiplier
        for multiplier_type, value in multipliers.items():
            final_multiplier *= value
        
        # Apply cap
        capped_multiplier = min(final_multiplier, self.config.max_multiplier)
        
        if capped_multiplier < final_multiplier:
            logger.debug(f"Multiplier capped: {final_multiplier:.2f} -> {capped_multiplier:.2f}")
        
        return capped_multiplier
    
    def _calculate_enhanced_scores(
        self, 
        original_score: float, 
        multiplier: float
    ) -> Dict[str, float]:
        """Calculate enhanced scores after multiplier application"""
        multiplied_score = original_score * multiplier
        score_boost = multiplied_score - original_score
        
        return {
            'multiplied_score': multiplied_score,
            'score_boost': score_boost
        }
    
    def _calculate_risk_reward_enhancement(
        self, 
        context: MultiplierContext, 
        multiplier: float,
        is_power_zone: bool
    ) -> Dict[str, float]:
        """Calculate risk-reward ratio enhancements for power zones"""
        # Base risk-reward assumptions
        original_rr = 1.5  # Default 1:1.5 RR
        
        if not is_power_zone:
            return {
                'original_rr': original_rr,
                'enhanced_rr': original_rr,
                'sl_reduction_percent': 0.0,
                'tp_extension_percent': 0.0,
                'size_multiplier': 1.0
            }
        
        # Power zones allow tighter SL and extended TP
        # SL reduction based on multiplier strength
        sl_reduction_percent = min(30.0, (multiplier - 1.0) * 15.0)  # Max 30% reduction
        
        # TP extension for better RR
        tp_extension_percent = min(150.0, (multiplier - 1.0) * 75.0)  # Max 150% extension
        
        # Calculate enhanced RR
        # If SL reduces by 30% and TP extends by 150%, RR improves significantly
        sl_factor = 1.0 - (sl_reduction_percent / 100.0)
        tp_factor = 1.0 + (tp_extension_percent / 100.0)
        enhanced_rr = original_rr * tp_factor / sl_factor
        
        # Position size multiplier (conservative)
        size_multiplier = min(2.0, 1.0 + (multiplier - 1.0) * 0.5)
        
        return {
            'original_rr': original_rr,
            'enhanced_rr': enhanced_rr,
            'sl_reduction_percent': sl_reduction_percent,
            'tp_extension_percent': tp_extension_percent,
            'size_multiplier': size_multiplier
        }
    
    def _calculate_execution_priority(
        self, 
        context: MultiplierContext, 
        multiplier: float,
        is_power_zone: bool
    ) -> Dict[str, any]:
        """Calculate execution priority adjustments"""
        base_priority = 5  # Default priority
        
        if not is_power_zone:
            return {
                'base_priority': base_priority,
                'power_zone_boost': 0,
                'final_priority': base_priority,
                'immediate_execution': False
            }
        
        # Power zone boost based on multiplier strength
        power_zone_boost = int((multiplier - 1.0) * 5)  # 0-10 boost
        final_priority = base_priority + power_zone_boost
        
        # Immediate execution for very strong power zones
        immediate_execution = multiplier >= 2.5
        
        return {
            'base_priority': base_priority,
            'power_zone_boost': power_zone_boost,
            'final_priority': final_priority,
            'immediate_execution': immediate_execution
        }
    
    def create_detailed_analysis_report(
        self, 
        result: ZoneMultiplierResult
    ) -> Dict[str, any]:
        """Create detailed analysis report for logging/debugging"""
        return {
            'power_zone_analysis': {
                'is_power_zone': result.is_power_zone,
                'power_level': result.power_level.name,
                'components_count': len(result.components),
                'component_types': [comp.component_type.value for comp in result.components]
            },
            'multiplier_breakdown': {
                'ema_overlap': result.ema_overlap_multiplier,
                'multi_zone': result.multi_zone_multiplier,
                'role_reversal': result.role_reversal_multiplier,
                'multi_timeframe': result.multi_timeframe_multiplier,
                'final_multiplier': result.final_multiplier,
                'capped': result.final_multiplier >= self.config.max_multiplier
            },
            'score_enhancement': {
                'original_score': result.original_zone_score,
                'enhanced_score': result.multiplied_zone_score,
                'improvement_percent': (result.total_score_boost / result.original_zone_score) * 100
            },
            'risk_reward_improvement': {
                'rr_improvement': result.enhanced_rr - result.original_rr,
                'sl_reduction': f"{result.sl_reduction_percent}%",
                'tp_extension': f"{result.tp_extension_percent}%",
                'size_boost': f"{(result.recommended_size_multiplier - 1.0) * 100:.1f}%"
            },
            'execution_benefits': {
                'priority_boost': result.power_zone_boost,
                'immediate_execution': result.immediate_execution,
                'final_priority': result.final_priority
            }
        }