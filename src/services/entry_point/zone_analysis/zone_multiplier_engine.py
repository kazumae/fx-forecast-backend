from typing import List
from src.domain.models.zone_multiplier import (
    ZoneMultiplierResult, PowerLevel, PowerZoneComponent, 
    MultiplierContext, ExecutionPrivilege
)


class ZoneMultiplierEngine:
    """ゾーン掛け算エンジン - 最終乗数とパワーレベルを計算"""
    
    def calculate_zone_multiplier(
        self, 
        context: MultiplierContext, 
        original_zone_score: float
    ) -> ZoneMultiplierResult:
        """ゾーン掛け算の最終結果を計算"""
        
        # パワーゾーンコンポーネントの検出は既に完了している前提
        from .power_zone_detector import PowerZoneDetector
        detector = PowerZoneDetector(context.config)
        components = detector.detect_power_zone_components(context)
        
        # 個別乗数を計算
        total_multiplier = 1.0
        for component in components:
            total_multiplier *= component.multiplier_contribution
        
        # 最大3.0倍に制限
        final_multiplier = min(total_multiplier, context.config.max_total_multiplier)
        
        # パワーゾーンかどうかを判定
        is_power_zone = len(components) > 0
        
        # パワーレベルを決定
        power_level = self._determine_power_level(final_multiplier, components)
        
        # リスクリワード比の強化値を計算
        enhanced_rr = self._calculate_enhanced_rr(final_multiplier, power_level)
        
        # 即時実行フラグを決定
        immediate_execution = final_multiplier >= context.config.immediate_execution_threshold
        
        # 実行特権を決定
        execution_privileges = self._determine_execution_privileges(final_multiplier, power_level)
        
        # 信頼度スコアを計算
        confidence_score = self._calculate_confidence_score(components, final_multiplier)
        
        return ZoneMultiplierResult(
            is_power_zone=is_power_zone,
            power_level=power_level,
            components=components,
            final_multiplier=final_multiplier,
            enhanced_rr=enhanced_rr,
            immediate_execution=immediate_execution,
            execution_privileges=execution_privileges,
            confidence_score=confidence_score
        )
    
    def _determine_power_level(self, multiplier: float, components: List[PowerZoneComponent]) -> PowerLevel:
        """乗数とコンポーネントに基づいてパワーレベルを決定"""
        
        if multiplier < 1.1:
            return PowerLevel.NONE
        elif multiplier < 1.5:
            return PowerLevel.WEAK
        elif multiplier < 2.0:
            return PowerLevel.MODERATE
        elif multiplier < 2.5:
            return PowerLevel.STRONG
        elif multiplier < 3.0:
            return PowerLevel.VERY_STRONG
        else:
            return PowerLevel.EXTREME
    
    def _calculate_enhanced_rr(self, multiplier: float, power_level: PowerLevel) -> float:
        """強化されたリスクリワード比を計算"""
        
        # 基本RR比（仮定値）
        base_rr = 1.5
        
        # パワーレベルに基づくRR強化
        rr_enhancement_map = {
            PowerLevel.NONE: 1.0,
            PowerLevel.WEAK: 1.2,
            PowerLevel.MODERATE: 1.6,
            PowerLevel.STRONG: 2.1,
            PowerLevel.VERY_STRONG: 2.7,
            PowerLevel.EXTREME: 3.5
        }
        
        enhancement_factor = rr_enhancement_map.get(power_level, 1.0)
        enhanced_rr = base_rr * enhancement_factor
        
        return round(enhanced_rr, 2)
    
    def _determine_execution_privileges(self, multiplier: float, power_level: PowerLevel) -> List[ExecutionPrivilege]:
        """実行特権を決定"""
        privileges = []
        
        # 即時実行特権
        if multiplier >= 2.5:
            privileges.append(ExecutionPrivilege.IMMEDIATE_EXECUTION)
        
        # 相関チェック回避特権
        if power_level.value >= PowerLevel.STRONG.value:
            privileges.append(ExecutionPrivilege.BYPASS_CORRELATION)
        
        # キュー優先特権
        if power_level.value >= PowerLevel.MODERATE.value:
            privileges.append(ExecutionPrivilege.QUEUE_PRIORITY)
        
        return privileges
    
    def _calculate_confidence_score(self, components: List[PowerZoneComponent], multiplier: float) -> float:
        """信頼度スコアを計算"""
        
        if not components:
            return 0.6  # 基本的な信頼度
        
        # コンポーネントの多様性スコア
        unique_types = len(set([c.component_type for c in components]))
        diversity_score = min(1.0, unique_types / 4.0)  # 4種類すべてで最高
        
        # 平均強度
        avg_strength = sum([c.strength for c in components]) / len(components)
        
        # 乗数による信頼度
        multiplier_confidence = min(1.0, multiplier / 3.0)
        
        # 総合信頼度
        confidence = (diversity_score * 0.3 + avg_strength * 0.4 + multiplier_confidence * 0.3)
        
        return round(confidence, 3)