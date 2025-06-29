from datetime import datetime
from typing import Dict, Any, List, Optional
from src.domain.models.zone_multiplier import (
    MultiplierContext, MultiplierConfig, ZoneMultiplierResult
)
from src.services.entry_point.zone_analysis.zone_multiplier_engine import ZoneMultiplierEngine
from src.services.entry_point.zone_analysis.risk_reward_optimizer import RiskRewardOptimizer
from src.services.entry_point.zone_analysis.priority_boost_system import PriorityBoostSystem


class ZoneMultiplierService:
    """ゾーン掛け算サービス - 全コンポーネントを統合"""
    
    def __init__(self, config: Optional[MultiplierConfig] = None):
        self.config = config or MultiplierConfig()
        self.multiplier_engine = ZoneMultiplierEngine()
        self.rr_optimizer = RiskRewardOptimizer()
        self.priority_system = PriorityBoostSystem()
    
    def analyze_zone_multiplier_effects(
        self,
        target_zone: Any,
        nearby_zones: List[Any],
        ema_values: List[Any],
        market_data: Dict[str, Any],
        timeframe: str = "H1",
        original_zone_score: float = 20.0,
        trade_direction: str = "long",
        entry_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """ゾーン掛け算の包括的分析を実行"""
        
        # コンテキストを構築
        context = MultiplierContext(
            target_zone=target_zone,
            nearby_zones=nearby_zones,
            ema_values=ema_values,
            market_data=market_data,
            timeframe=timeframe,
            analysis_timestamp=datetime.now(),
            config=self.config
        )
        
        # ゾーン掛け算分析を実行
        multiplier_result = self.multiplier_engine.calculate_zone_multiplier(
            context, original_zone_score
        )
        
        # リスクリワード最適化
        rr_adjustment = None
        if entry_price:
            rr_adjustment = self.rr_optimizer.optimize_risk_reward(
                context, multiplier_result, trade_direction, entry_price
            )
        
        # 優先順位ブースト計算
        priority_boost = self.priority_system.calculate_priority_boost(
            multiplier_result, context
        )
        
        # 包括的な結果を構築
        return self._build_comprehensive_result(
            multiplier_result, rr_adjustment, priority_boost, 
            original_zone_score, context
        )
    
    def quick_power_zone_check(self, target_zone: Any, ema_values: List[Any]) -> bool:
        """軽量なパワーゾーン判定（高速スクリーニング用）"""
        
        # 200EMAとの重なりをクイックチェック
        for ema in ema_values:
            if ema.period == 200:
                distance_pips = abs(target_zone.price - ema.value) * 10000
                if distance_pips <= self.config.ema_overlap_distance_pips:
                    return True
        
        # 複数の役割転換履歴をチェック
        role_history = getattr(target_zone, 'role_history', [])
        if len(role_history) >= 3:
            changes = sum(1 for i in range(1, len(role_history)) 
                         if role_history[i] != role_history[i-1])
            if changes >= 2:
                return True
        
        return False
    
    def get_execution_parameters(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """実行用パラメータを抽出"""
        
        zone_analysis = analysis_result.get("zone_analysis", {})
        execution_priority = analysis_result.get("execution_priority", {})
        rr_enhancement = analysis_result.get("risk_reward_enhancement", {})
        
        return {
            "should_execute": zone_analysis.get("is_power_zone", False),
            "execution_priority": execution_priority.get("final_priority", 5),
            "immediate_execution": execution_priority.get("immediate_execution", False),
            "weight_multiplier": execution_priority.get("weight_multiplier", 1.0),
            "enhanced_sl_distance": rr_enhancement.get("optimized_sl_distance"),
            "enhanced_tp_distance": rr_enhancement.get("optimized_tp_distance"),
            "confidence_level": analysis_result.get("overall_confidence", 0.6),
            "bypass_correlation": "bypass_correlation" in execution_priority.get("execution_privileges", {}),
            "position_size_multiplier": self._calculate_position_size_multiplier(analysis_result)
        }
    
    def generate_summary_report(self, analysis_result: Dict[str, Any]) -> str:
        """人間可読形式のサマリーレポートを生成"""
        
        zone_analysis = analysis_result.get("zone_analysis", {})
        score_multipliers = analysis_result.get("score_multipliers", {})
        execution_priority = analysis_result.get("execution_priority", {})
        
        is_power_zone = zone_analysis.get("is_power_zone", False)
        power_level = zone_analysis.get("power_level", 0)
        final_multiplier = score_multipliers.get("final_multiplier", 1.0)
        
        if not is_power_zone:
            return "レギュラーゾーン: 標準的なエントリー条件を適用"
        
        summary_parts = []
        summary_parts.append(f"パワーゾーン検出 (レベル {power_level})")
        summary_parts.append(f"{final_multiplier:.2f}x乗数適用")
        
        if execution_priority.get("immediate_execution"):
            summary_parts.append("即時実行フラグ")
        
        if execution_priority.get("weight_multiplier", 1.0) >= 2.0:
            summary_parts.append("2倍重み付け")
        
        # RR改善情報
        rr_enhancement = analysis_result.get("risk_reward_enhancement")
        if rr_enhancement:
            enhanced_rr = rr_enhancement.get("enhanced_rr")
            if enhanced_rr:
                summary_parts.append(f"RR比 {enhanced_rr:.1f}")
        
        return " | ".join(summary_parts)
    
    def _build_comprehensive_result(
        self,
        multiplier_result: ZoneMultiplierResult,
        rr_adjustment: Optional[Any],
        priority_boost: Dict[str, Any],
        original_zone_score: float,
        context: MultiplierContext
    ) -> Dict[str, Any]:
        """包括的な分析結果を構築"""
        
        result = {
            "analysis_metadata": {
                "timestamp": context.analysis_timestamp.isoformat(),
                "timeframe": context.timeframe,
                "analysis_version": "1.0"
            },
            "zone_analysis": {
                "is_power_zone": multiplier_result.is_power_zone,
                "power_level": multiplier_result.power_level.value,
                "power_level_name": multiplier_result.power_level.name,
                "components_detected": len(multiplier_result.components),
                "components": [
                    {
                        "type": comp.component_type.value,
                        "strength": comp.strength,
                        "multiplier_contribution": comp.multiplier_contribution,
                        "details": comp.details
                    }
                    for comp in multiplier_result.components
                ]
            },
            "score_multipliers": {
                "original_multiplier": 1.0,
                "component_multipliers": {
                    comp.component_type.value: comp.multiplier_contribution
                    for comp in multiplier_result.components
                },
                "final_multiplier": multiplier_result.final_multiplier,
                "capped_at_maximum": multiplier_result.final_multiplier >= self.config.max_total_multiplier
            },
            "enhanced_scores": {
                "original_zone_score": original_zone_score,
                "multiplied_zone_score": original_zone_score * multiplier_result.final_multiplier,
                "score_improvement": (multiplier_result.final_multiplier - 1.0) * 100  # パーセンテージ
            },
            "execution_priority": {
                "base_priority": priority_boost["base_priority"],
                "final_priority": priority_boost["final_priority"],
                "priority_boost": priority_boost["priority_boost"],
                "weight_multiplier": priority_boost["weight_multiplier"],
                "immediate_execution": multiplier_result.immediate_execution,
                "execution_privileges": priority_boost["execution_privileges"],
                "urgency_level": priority_boost["urgency_level"]
            },
            "overall_confidence": multiplier_result.confidence_score
        }
        
        # リスクリワード強化情報を追加
        if rr_adjustment:
            result["risk_reward_enhancement"] = {
                "original_rr": rr_adjustment.original_tp_distance / rr_adjustment.original_sl_distance,
                "enhanced_rr": rr_adjustment.enhanced_rr_ratio,
                "sl_reduction": f"{rr_adjustment.sl_reduction_percent:.0f}%",
                "tp_extension": f"{rr_adjustment.tp_extension_percent:.0f}%",
                "optimized_sl_distance": rr_adjustment.optimized_sl_distance,
                "optimized_tp_distance": rr_adjustment.optimized_tp_distance,
                "confidence_level": rr_adjustment.confidence_level,
                "next_major_zone": rr_adjustment.next_major_zone_price
            }
        
        return result
    
    def _calculate_position_size_multiplier(self, analysis_result: Dict[str, Any]) -> float:
        """ポジションサイズ乗数を計算"""
        
        zone_analysis = analysis_result.get("zone_analysis", {})
        power_level = zone_analysis.get("power_level", 0)
        confidence = analysis_result.get("overall_confidence", 0.6)
        
        # パワーレベルに基づく基本乗数
        base_multipliers = {
            0: 1.0,    # NONE
            1: 1.1,    # WEAK
            2: 1.3,    # MODERATE
            3: 1.5,    # STRONG
            4: 1.7,    # VERY_STRONG
            5: 2.0     # EXTREME
        }
        
        base_multiplier = base_multipliers.get(power_level, 1.0)
        
        # 信頼度による調整
        confidence_adjustment = 0.8 + (confidence * 0.4)  # 0.8 - 1.2の範囲
        
        final_multiplier = base_multiplier * confidence_adjustment
        
        # 最大2.0倍に制限
        return min(2.0, final_multiplier)