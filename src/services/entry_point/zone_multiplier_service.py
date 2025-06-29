"""
Zone Multiplier Service for US-014

Main orchestrator service that integrates all zone multiplier
components to provide complete power zone analysis and enhancement.
"""
from typing import Dict, List, Optional, Any
from decimal import Decimal
import logging

from src.domain.models.zone_multiplier import (
    ZoneInfo, EMAInfo, MultiplierContext, MultiplierConfig,
    ZoneMultiplierResult, RiskRewardAdjustment
)
from src.services.entry_point.zone_analysis.power_zone_detector import PowerZoneDetector
from src.services.entry_point.zone_analysis.zone_multiplier_engine import ZoneMultiplierEngine
from src.services.entry_point.zone_analysis.risk_reward_optimizer import (
    RiskRewardOptimizer, TradeDirection
)
from src.services.entry_point.zone_analysis.priority_boost_system import PriorityBoostSystem


logger = logging.getLogger(__name__)


class ZoneMultiplierService:
    """
    Complete zone multiplier service orchestrator
    
    Provides unified interface for all US-014 zone multiplication
    functionality including power zone detection, scoring enhancement,
    risk-reward optimization, and priority boosting.
    """
    
    def __init__(self, config: MultiplierConfig = None):
        """Initialize with configuration"""
        self.config = config or MultiplierConfig()
        
        # Initialize all subsystems
        self.power_zone_detector = PowerZoneDetector(self.config)
        self.multiplier_engine = ZoneMultiplierEngine(self.config)
        self.risk_reward_optimizer = RiskRewardOptimizer()
        self.priority_boost_system = PriorityBoostSystem()
        
        logger.info("Zone Multiplier Service initialized with all subsystems")
    
    def analyze_zone_multiplier_effects(
        self,
        target_zone: ZoneInfo,
        nearby_zones: List[ZoneInfo],
        ema_values: List[EMAInfo],
        current_price: Decimal,
        timeframe: str,
        market_session: str,
        original_zone_score: float,
        psychological_levels: List[Decimal] = None,
        trade_direction: Optional[TradeDirection] = None,
        entry_price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Complete zone multiplier analysis
        
        Args:
            target_zone: The primary zone being analyzed
            nearby_zones: Other zones within range for clustering analysis
            ema_values: EMA values for overlap detection
            current_price: Current market price
            timeframe: Current timeframe (1H, 4H, 1D, etc.)
            market_session: Current market session
            original_zone_score: Base zone score before multiplication
            psychological_levels: Round number levels (.00, .50)
            trade_direction: Optional trade direction for RR optimization
            entry_price: Optional entry price for RR optimization
            
        Returns:
            Complete analysis result with all enhancements
        """
        logger.info(f"Starting complete zone multiplier analysis for {target_zone.zone_id}")
        
        # Create analysis context
        context = MultiplierContext(
            target_zone=target_zone,
            nearby_zones=nearby_zones,
            ema_values=ema_values,
            current_price=current_price,
            timeframe=timeframe,
            psychological_levels=psychological_levels or [],
            market_session=market_session
        )
        
        # Step 1: Calculate zone multiplier effects
        multiplier_result = self.multiplier_engine.calculate_zone_multiplier(
            context, original_zone_score
        )
        
        # Step 2: Calculate priority boost
        priority_result = self.priority_boost_system.calculate_priority_boost(
            multiplier_result, context
        )
        
        # Step 3: Optimize risk-reward (if trade direction provided)
        risk_reward_result = None
        if trade_direction and entry_price:
            risk_reward_result = self.risk_reward_optimizer.optimize_risk_reward(
                context, multiplier_result, trade_direction, entry_price
            )
        
        # Step 4: Create comprehensive result
        comprehensive_result = self._create_comprehensive_result(
            context, multiplier_result, priority_result, risk_reward_result
        )
        
        logger.info(f"Zone multiplier analysis complete: "
                   f"Power Zone: {multiplier_result.is_power_zone}, "
                   f"Multiplier: {multiplier_result.final_multiplier:.2f}x, "
                   f"Priority: {priority_result['final_priority']}")
        
        return comprehensive_result
    
    def quick_power_zone_check(
        self,
        target_zone: ZoneInfo,
        nearby_zones: List[ZoneInfo],
        ema_values: List[EMAInfo],
        current_price: Decimal,
        timeframe: str,
        market_session: str
    ) -> Dict[str, Any]:
        """
        Quick check to determine if zone is a power zone
        
        Lighter version of full analysis for screening purposes
        """
        context = MultiplierContext(
            target_zone=target_zone,
            nearby_zones=nearby_zones,
            ema_values=ema_values,
            current_price=current_price,
            timeframe=timeframe,
            psychological_levels=[],
            market_session=market_session
        )
        
        # Detect power zone components
        components = self.power_zone_detector.detect_power_zone_components(context)
        is_power_zone = self.power_zone_detector.is_power_zone(components)
        
        if not is_power_zone:
            return {
                'is_power_zone': False,
                'component_count': 0,
                'estimated_multiplier': 1.0,
                'recommendation': 'standard_analysis'
            }
        
        # Estimate multiplier without full calculation
        estimated_multiplier = self._estimate_multiplier_from_components(components)
        
        return {
            'is_power_zone': True,
            'component_count': len(components),
            'component_types': [comp.component_type.value for comp in components],
            'estimated_multiplier': estimated_multiplier,
            'recommendation': 'full_analysis' if estimated_multiplier >= 2.0 else 'enhanced_analysis'
        }
    
    def get_enhanced_signal_parameters(
        self,
        multiplier_result: ZoneMultiplierResult,
        priority_result: Dict[str, Any],
        risk_reward_result: Optional[RiskRewardAdjustment] = None
    ) -> Dict[str, Any]:
        """
        Get enhanced parameters for signal execution
        
        Returns parameters that can be used by trading system
        """
        enhanced_params = {
            # Score enhancements
            'enhanced_zone_score': multiplier_result.multiplied_zone_score,
            'score_multiplier': multiplier_result.final_multiplier,
            'score_boost': multiplier_result.total_score_boost,
            
            # Priority enhancements
            'execution_priority': priority_result['final_priority'],
            'priority_weight': priority_result['weight_multiplier'],
            'immediate_execution': priority_result['immediate_execution'],
            'bypass_correlation': priority_result['bypass_correlation'],
            'queue_position': priority_result['queue_position'],
            
            # Risk management
            'confidence_level': 0.6,  # Default
            'position_size_multiplier': multiplier_result.recommended_size_multiplier,
        }
        
        # Add risk-reward optimizations if available
        if risk_reward_result:
            enhanced_params.update({
                'optimized_sl_pips': float(risk_reward_result.adjusted_sl_distance),
                'optimized_tp_pips': float(risk_reward_result.adjusted_tp_distance),
                'enhanced_rr_ratio': risk_reward_result.enhanced_rr_ratio,
                'confidence_level': risk_reward_result.confidence_boost,
                'sl_reduction_pips': float(risk_reward_result.sl_reduction_pips),
                'tp_extension_pips': float(risk_reward_result.tp_extension_pips)
            })
        
        return enhanced_params
    
    def _create_comprehensive_result(
        self,
        context: MultiplierContext,
        multiplier_result: ZoneMultiplierResult,
        priority_result: Dict[str, Any],
        risk_reward_result: Optional[RiskRewardAdjustment]
    ) -> Dict[str, Any]:
        """Create comprehensive analysis result matching US-014 specification"""
        
        # Build components details
        components_details = []
        for component in multiplier_result.components:
            component_detail = {
                'type': component.component_type.value,
                'multiplier_contribution': component.multiplier_contribution
            }
            
            # Add type-specific details
            if component.zone_id:
                component_detail['zone_id'] = component.zone_id
            if component.zones:
                component_detail['zones'] = component.zones
            if component.ema_period:
                component_detail['ema'] = component.ema_period
            if component.distance is not None:
                component_detail['distance'] = float(component.distance)
            if component.span is not None:
                component_detail['span'] = float(component.span)
            if component.history:
                component_detail['history'] = component.history
                
            components_details.append(component_detail)
        
        # Create result matching specification format
        comprehensive_result = {
            'zone_analysis': {
                'is_power_zone': multiplier_result.is_power_zone,
                'power_level': multiplier_result.power_level.value,
                'components': components_details
            },
            'score_multipliers': {
                'base_multiplier': multiplier_result.base_multiplier,
                'ema_overlap': multiplier_result.ema_overlap_multiplier,
                'multi_zone': multiplier_result.multi_zone_multiplier,
                'role_reversal': multiplier_result.role_reversal_multiplier,
                'multi_timeframe': multiplier_result.multi_timeframe_multiplier,
                'final_multiplier': multiplier_result.final_multiplier
            },
            'enhanced_scores': {
                'original_zone_score': multiplier_result.original_zone_score,
                'multiplied_zone_score': multiplier_result.multiplied_zone_score,
                'total_score_boost': multiplier_result.total_score_boost
            },
            'risk_reward_enhancement': {
                'original_rr': multiplier_result.original_rr,
                'enhanced_rr': multiplier_result.enhanced_rr,
                'sl_reduction': f"{multiplier_result.sl_reduction_percent:.1f}%",
                'tp_extension': f"{multiplier_result.tp_extension_percent:.1f}%",
                'recommended_size_multiplier': multiplier_result.recommended_size_multiplier
            },
            'execution_priority': {
                'base_priority': priority_result['base_priority'],
                'power_zone_boost': priority_result['total_boost'],
                'final_priority': priority_result['final_priority'],
                'immediate_execution': priority_result['immediate_execution'],
                'weight_multiplier': priority_result['weight_multiplier'],
                'execution_privileges': [p.value for p in priority_result['execution_privileges']]
            }
        }
        
        # Add detailed risk-reward if optimization was performed
        if risk_reward_result:
            comprehensive_result['detailed_risk_reward'] = {
                'original_sl_distance': float(risk_reward_result.original_sl_distance),
                'original_tp_distance': float(risk_reward_result.original_tp_distance),
                'optimized_sl_distance': float(risk_reward_result.adjusted_sl_distance),
                'optimized_tp_distance': float(risk_reward_result.adjusted_tp_distance),
                'sl_reduction_pips': float(risk_reward_result.sl_reduction_pips),
                'tp_extension_pips': float(risk_reward_result.tp_extension_pips),
                'confidence_boost': risk_reward_result.confidence_boost
            }
        
        return comprehensive_result
    
    def _estimate_multiplier_from_components(
        self, 
        components: List[Any]
    ) -> float:
        """Estimate multiplier without full calculation"""
        if not components:
            return 1.0
        
        # Quick estimation based on component contributions
        total_multiplier = 1.0
        for component in components:
            total_multiplier *= getattr(component, 'multiplier_contribution', 1.0)
        
        # Apply cap
        return min(total_multiplier, self.config.max_multiplier)
    
    def create_execution_summary(self, analysis_result: Dict[str, Any]) -> str:
        """Create human-readable execution summary"""
        zone_analysis = analysis_result['zone_analysis']
        multipliers = analysis_result['score_multipliers']
        priority = analysis_result['execution_priority']
        
        if not zone_analysis['is_power_zone']:
            return "Regular zone - standard execution parameters"
        
        summary_parts = [
            f"POWER ZONE (Level {zone_analysis['power_level']})",
            f"Score: {multipliers['final_multiplier']:.2f}x multiplier",
            f"Priority: {priority['final_priority']} (Weight: {priority['weight_multiplier']:.1f}x)",
        ]
        
        if priority['immediate_execution']:
            summary_parts.append("IMMEDIATE EXECUTION")
        
        if analysis_result.get('detailed_risk_reward'):
            rr_detail = analysis_result['detailed_risk_reward']
            summary_parts.append(
                f"Enhanced RR: {rr_detail['optimized_sl_distance']:.0f}/"
                f"{rr_detail['optimized_tp_distance']:.0f} pips"
            )
        
        return " | ".join(summary_parts)