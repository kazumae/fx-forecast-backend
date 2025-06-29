"""
Priority Boost System for US-014

Dramatically increases execution priority for power zone signals,
providing special privileges and immediate execution flags.
"""
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

from src.domain.models.zone_multiplier import (
    ZoneMultiplierResult, PowerLevel, MultiplierContext
)
# Note: EntrySignal and CorrelationInfo imports will be available when integrated
# with the entry evaluation system. For now, using type hints for documentation.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models.entry_evaluation import EntrySignal, CorrelationInfo


logger = logging.getLogger(__name__)


class PriorityClass(Enum):
    """Priority classification levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 15
    EMERGENCY = 20


class ExecutionPrivilege(Enum):
    """Special execution privileges for power zones"""
    NONE = "none"
    BYPASS_CORRELATION = "bypass_correlation"  # Ignore correlation with other signals
    IMMEDIATE_EXECUTION = "immediate_execution"  # Execute without delay
    OVERRIDE_POSITION_LIMIT = "override_position_limit"  # Exceed normal position limits
    PRIORITY_QUEUE = "priority_queue"  # Jump to front of execution queue


class PriorityBoostSystem:
    """Manages priority boosts and special privileges for power zones"""
    
    def __init__(self):
        """Initialize priority boost system"""
        self.base_priority = 5
        self.max_priority = 20
        
        # Priority boost mapping by power level
        self.power_level_boosts = {
            PowerLevel.EXTREME: 15,      # Emergency priority
            PowerLevel.VERY_STRONG: 12,  # Critical priority  
            PowerLevel.STRONG: 8,        # High priority
            PowerLevel.MODERATE: 5,      # Above normal
            PowerLevel.WEAK: 2           # Slight boost
        }
    
    def calculate_priority_boost(
        self, 
        multiplier_result: ZoneMultiplierResult,
        context: MultiplierContext
    ) -> Dict[str, Any]:
        """
        Calculate priority boost and special privileges
        
        Returns complete priority enhancement package
        """
        if not multiplier_result.is_power_zone:
            return self._create_standard_priority()
        
        # Calculate base priority boost
        power_boost = self.power_level_boosts.get(
            multiplier_result.power_level, 0
        )
        
        # Component-based additional boosts
        component_boost = self._calculate_component_boost(multiplier_result)
        
        # Market condition boosts
        market_boost = self._calculate_market_condition_boost(context)
        
        # Total boost with cap
        total_boost = min(
            power_boost + component_boost + market_boost,
            self.max_priority - self.base_priority
        )
        
        final_priority = self.base_priority + total_boost
        priority_class = self._determine_priority_class(final_priority)
        
        # Determine special privileges
        privileges = self._determine_execution_privileges(
            multiplier_result, final_priority
        )
        
        # Create priority result
        priority_result = {
            'base_priority': self.base_priority,
            'power_level_boost': power_boost,
            'component_boost': component_boost,
            'market_condition_boost': market_boost,
            'total_boost': total_boost,
            'final_priority': final_priority,
            'priority_class': priority_class,
            'execution_privileges': privileges,
            'immediate_execution': ExecutionPrivilege.IMMEDIATE_EXECUTION in privileges,
            'bypass_correlation': ExecutionPrivilege.BYPASS_CORRELATION in privileges,
            'weight_multiplier': self._calculate_weight_multiplier(final_priority),
            'queue_position': self._calculate_queue_position(priority_class)
        }
        
        logger.info(f"Priority boost calculated: {final_priority} "
                   f"(class: {priority_class.name}, "
                   f"privileges: {len(privileges)})")
        
        return priority_result
    
    def _calculate_component_boost(self, multiplier_result: ZoneMultiplierResult) -> int:
        """Calculate additional boost based on power zone components"""
        component_boosts = {
            'zone_ema_overlap': 3,      # +3 for EMA overlap
            'multi_zone_cluster': 4,    # +4 for zone clusters
            'role_reversal': 2,         # +2 for role reversal
            'multi_timeframe': 2,       # +2 for multi-timeframe
            'psychological_level': 1    # +1 for psychological levels
        }
        
        total_boost = 0
        for component in multiplier_result.components:
            boost = component_boosts.get(component.component_type.value, 0)
            total_boost += boost
            
        # Cap component boost
        return min(total_boost, 8)
    
    def _calculate_market_condition_boost(self, context: MultiplierContext) -> int:
        """Calculate boost based on favorable market conditions"""
        boost = 0
        
        # Market session boost
        session_boosts = {
            'london': 2,
            'ny': 2,
            'london_ny_overlap': 3,  # Best session
            'sydney': 0,
            'tokyo': 1
        }
        
        boost += session_boosts.get(context.market_session, 0)
        
        # Timeframe boost (higher timeframes get more priority)
        timeframe_boosts = {
            '1D': 3,
            '4H': 2,
            '1H': 1,
            '15M': 0,
            '5M': 0
        }
        
        boost += timeframe_boosts.get(context.timeframe, 0)
        
        return min(boost, 5)  # Cap market boost
    
    def _determine_priority_class(self, final_priority: int) -> PriorityClass:
        """Determine priority class based on final priority score"""
        if final_priority >= 18:
            return PriorityClass.EMERGENCY
        elif final_priority >= 15:
            return PriorityClass.CRITICAL
        elif final_priority >= 10:
            return PriorityClass.HIGH
        elif final_priority >= 7:
            return PriorityClass.NORMAL
        else:
            return PriorityClass.LOW
    
    def _determine_execution_privileges(
        self, 
        multiplier_result: ZoneMultiplierResult,
        final_priority: int
    ) -> List[ExecutionPrivilege]:
        """Determine special execution privileges"""
        privileges = []
        
        # Immediate execution for extreme power zones
        if (multiplier_result.power_level in [PowerLevel.EXTREME, PowerLevel.VERY_STRONG] or
            final_priority >= 15):
            privileges.append(ExecutionPrivilege.IMMEDIATE_EXECUTION)
        
        # Bypass correlation for strong power zones
        if (multiplier_result.power_level in [PowerLevel.EXTREME, PowerLevel.VERY_STRONG, PowerLevel.STRONG] or
            final_priority >= 12):
            privileges.append(ExecutionPrivilege.BYPASS_CORRELATION)
        
        # Priority queue access for high priority signals
        if final_priority >= 10:
            privileges.append(ExecutionPrivilege.PRIORITY_QUEUE)
        
        # Position limit override for extreme cases
        if (multiplier_result.power_level == PowerLevel.EXTREME and
            final_priority >= 18):
            privileges.append(ExecutionPrivilege.OVERRIDE_POSITION_LIMIT)
        
        return privileges
    
    def _calculate_weight_multiplier(self, final_priority: int) -> float:
        """Calculate weight multiplier for signal ranking"""
        # Normal signals have weight 1.0
        # Power zones get 2x weight as specified in requirements
        if final_priority >= 10:  # High priority and above
            return 2.0
        elif final_priority >= 7:   # Above normal
            return 1.5
        else:
            return 1.0
    
    def _calculate_queue_position(self, priority_class: PriorityClass) -> int:
        """Calculate position in execution queue (lower = earlier)"""
        queue_positions = {
            PriorityClass.EMERGENCY: 1,
            PriorityClass.CRITICAL: 2,
            PriorityClass.HIGH: 3,
            PriorityClass.NORMAL: 4,
            PriorityClass.LOW: 5
        }
        
        return queue_positions.get(priority_class, 5)
    
    def _create_standard_priority(self) -> Dict[str, Any]:
        """Create standard priority result for non-power zones"""
        return {
            'base_priority': self.base_priority,
            'power_level_boost': 0,
            'component_boost': 0,
            'market_condition_boost': 0,
            'total_boost': 0,
            'final_priority': self.base_priority,
            'priority_class': PriorityClass.NORMAL,
            'execution_privileges': [],
            'immediate_execution': False,
            'bypass_correlation': False,
            'weight_multiplier': 1.0,
            'queue_position': 4
        }
    
    def should_override_correlation_check(
        self, 
        priority_result: Dict[str, Any],
        conflicting_signals: List[Any]  # List[EntrySignal] when available
    ) -> bool:
        """
        Determine if power zone should override correlation restrictions
        
        This gives power zones special privilege to ignore correlation
        with other signals as specified in AC-4.
        """
        if not priority_result.get('bypass_correlation', False):
            return False
        
        # Even with bypass privilege, don't override if there are
        # multiple other power zones in conflict
        power_zone_conflicts = sum(
            1 for signal in conflicting_signals 
            if getattr(signal, 'is_power_zone', False)
        )
        
        # Allow override only if conflicting with regular zones
        if power_zone_conflicts == 0:
            logger.info("Power zone overriding correlation check with regular signals")
            return True
        
        # If conflicting with other power zones, use normal correlation logic
        logger.debug(f"Power zone correlation override blocked: "
                    f"{power_zone_conflicts} other power zones in conflict")
        return False
    
    def should_execute_immediately(self, priority_result: Dict[str, Any]) -> bool:
        """
        Determine if signal should be executed immediately
        without waiting for normal scheduling
        """
        return priority_result.get('immediate_execution', False)
    
    def get_position_size_override(
        self, 
        priority_result: Dict[str, Any],
        normal_position_limit: int
    ) -> Optional[int]:
        """
        Get position size override for power zones
        
        Returns new limit if override is granted, None otherwise
        """
        if ExecutionPrivilege.OVERRIDE_POSITION_LIMIT not in priority_result.get('execution_privileges', []):
            return None
        
        # Conservative override: allow 1.5x normal limit for extreme power zones
        override_limit = int(normal_position_limit * 1.5)
        
        logger.warning(f"Position limit override granted: {normal_position_limit} -> {override_limit}")
        return override_limit
    
    def create_priority_summary(self, priority_result: Dict[str, Any]) -> str:
        """Create human-readable priority summary"""
        priority_class = priority_result['priority_class']
        privileges = priority_result['execution_privileges']
        
        summary_parts = [
            f"Priority: {priority_result['final_priority']} ({priority_class.name})",
            f"Weight: {priority_result['weight_multiplier']}x",
            f"Queue: #{priority_result['queue_position']}"
        ]
        
        if privileges:
            privilege_names = [p.value.replace('_', ' ').title() for p in privileges]
            summary_parts.append(f"Privileges: {', '.join(privilege_names)}")
        
        return " | ".join(summary_parts)