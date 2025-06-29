from typing import Dict, Any, List
from src.domain.models.zone_multiplier import (
    ZoneMultiplierResult, PowerLevel, ExecutionPrivilege, MultiplierContext
)


class PriorityBoostSystem:
    """優先順位ブーストシステム"""
    
    def calculate_priority_boost(
        self, 
        multiplier_result: ZoneMultiplierResult, 
        context: MultiplierContext
    ) -> Dict[str, Any]:
        """パワーゾーンに基づいて優先順位ブーストを計算"""
        
        # 基本優先度（通常のシグナル）
        base_priority = 5
        
        # パワーレベル別の優先度マッピング
        priority_map = {
            PowerLevel.NONE: 5,         # 通常
            PowerLevel.WEAK: 8,         # 軽微な向上
            PowerLevel.MODERATE: 12,    # 中程度の向上
            PowerLevel.STRONG: 15,      # 高い優先度
            PowerLevel.VERY_STRONG: 18, # 非常に高い優先度
            PowerLevel.EXTREME: 20      # 緊急レベル
        }
        
        final_priority = priority_map.get(multiplier_result.power_level, base_priority)
        
        # 重み乗数の計算（仕様：通常シグナルの2倍の重み付け）
        weight_multiplier = self._calculate_weight_multiplier(multiplier_result.power_level)
        
        # 実行キューでの位置決定
        queue_position = self._determine_queue_position(multiplier_result.power_level, final_priority)
        
        # 特別実行権限の詳細
        execution_privileges_detail = self._get_execution_privileges_detail(
            multiplier_result.execution_privileges
        )
        
        # 緊急度レベル
        urgency_level = self._calculate_urgency_level(multiplier_result.power_level)
        
        return {
            "base_priority": base_priority,
            "final_priority": final_priority,
            "priority_boost": final_priority - base_priority,
            "weight_multiplier": weight_multiplier,
            "queue_position": queue_position,
            "urgency_level": urgency_level,
            "immediate_execution": multiplier_result.immediate_execution,
            "execution_privileges": execution_privileges_detail,
            "bypass_conditions": self._get_bypass_conditions(multiplier_result),
            "escalation_path": self._get_escalation_path(multiplier_result.power_level)
        }
    
    def _calculate_weight_multiplier(self, power_level: PowerLevel) -> float:
        """重み乗数を計算（仕様：パワーゾーンで2倍の重み付け）"""
        
        weight_map = {
            PowerLevel.NONE: 1.0,       # 通常重み
            PowerLevel.WEAK: 1.2,       # 軽微な重み増加
            PowerLevel.MODERATE: 1.5,   # 中程度の重み増加
            PowerLevel.STRONG: 1.8,     # 高い重み
            PowerLevel.VERY_STRONG: 2.0, # 仕様通り2倍
            PowerLevel.EXTREME: 2.0     # 最大2倍（仕様制限）
        }
        
        return weight_map.get(power_level, 1.0)
    
    def _determine_queue_position(self, power_level: PowerLevel, priority: int) -> str:
        """実行キューでの位置を決定"""
        
        if power_level == PowerLevel.EXTREME:
            return "EMERGENCY_FIRST"
        elif power_level == PowerLevel.VERY_STRONG:
            return "HIGH_PRIORITY"
        elif power_level in [PowerLevel.STRONG, PowerLevel.MODERATE]:
            return "ELEVATED"
        elif power_level == PowerLevel.WEAK:
            return "SLIGHTLY_ELEVATED"
        else:
            return "NORMAL"
    
    def _get_execution_privileges_detail(self, privileges: List[ExecutionPrivilege]) -> Dict[str, Any]:
        """実行特権の詳細情報を取得"""
        
        privilege_details = {
            "immediate_execution": ExecutionPrivilege.IMMEDIATE_EXECUTION in privileges,
            "bypass_correlation": ExecutionPrivilege.BYPASS_CORRELATION in privileges,
            "queue_priority": ExecutionPrivilege.QUEUE_PRIORITY in privileges,
            "privilege_count": len(privileges),
            "special_handling": len(privileges) >= 2
        }
        
        # 特権レベルの総合評価
        if privilege_details["immediate_execution"]:
            privilege_details["privilege_level"] = "MAXIMUM"
        elif privilege_details["bypass_correlation"]:
            privilege_details["privilege_level"] = "HIGH"
        elif privilege_details["queue_priority"]:
            privilege_details["privilege_level"] = "MODERATE"
        else:
            privilege_details["privilege_level"] = "STANDARD"
        
        return privilege_details
    
    def _calculate_urgency_level(self, power_level: PowerLevel) -> str:
        """緊急度レベルを計算"""
        
        urgency_map = {
            PowerLevel.NONE: "ROUTINE",
            PowerLevel.WEAK: "LOW",
            PowerLevel.MODERATE: "MODERATE",
            PowerLevel.STRONG: "HIGH",
            PowerLevel.VERY_STRONG: "URGENT",
            PowerLevel.EXTREME: "CRITICAL"
        }
        
        return urgency_map.get(power_level, "ROUTINE")
    
    def _get_bypass_conditions(self, multiplier_result: ZoneMultiplierResult) -> Dict[str, bool]:
        """バイパス条件を取得"""
        
        return {
            "correlation_check": ExecutionPrivilege.BYPASS_CORRELATION in multiplier_result.execution_privileges,
            "risk_validation": multiplier_result.power_level.value >= PowerLevel.STRONG.value,
            "position_size_limit": multiplier_result.power_level == PowerLevel.EXTREME,
            "market_hours_restriction": multiplier_result.immediate_execution,
            "confirmation_requirement": multiplier_result.power_level.value < PowerLevel.MODERATE.value
        }
    
    def _get_escalation_path(self, power_level: PowerLevel) -> List[str]:
        """エスカレーションパスを取得"""
        
        escalation_paths = {
            PowerLevel.NONE: ["standard_validation", "normal_execution"],
            PowerLevel.WEAK: ["quick_validation", "normal_execution"],
            PowerLevel.MODERATE: ["priority_validation", "elevated_execution"],
            PowerLevel.STRONG: ["expedited_validation", "high_priority_execution"],
            PowerLevel.VERY_STRONG: ["minimal_validation", "urgent_execution"],
            PowerLevel.EXTREME: ["bypass_validation", "immediate_execution", "emergency_protocol"]
        }
        
        return escalation_paths.get(power_level, ["standard_validation", "normal_execution"])