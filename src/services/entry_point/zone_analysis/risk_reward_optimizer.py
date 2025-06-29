from typing import Optional, List, Any
from src.domain.models.zone_multiplier import (
    RiskRewardAdjustment, ZoneMultiplierResult, PowerLevel, MultiplierContext
)


class RiskRewardOptimizer:
    """リスクリワード比最適化器"""
    
    def optimize_risk_reward(
        self,
        context: MultiplierContext,
        multiplier_result: ZoneMultiplierResult,
        trade_direction: str,  # "long" or "short"
        entry_price: float
    ) -> RiskRewardAdjustment:
        """パワーゾーンに基づいてリスクリワード比を最適化"""
        
        # 基本的なSL/TP距離（pipsで仮定）
        base_sl_pips = 20.0
        base_tp_pips = 30.0
        
        # パワーレベルに基づくSL縮小率
        sl_reduction_map = {
            PowerLevel.NONE: 0.0,
            PowerLevel.WEAK: 0.05,      # 5%縮小
            PowerLevel.MODERATE: 0.15,  # 15%縮小
            PowerLevel.STRONG: 0.25,    # 25%縮小
            PowerLevel.VERY_STRONG: 0.35, # 35%縮小
            PowerLevel.EXTREME: 0.40    # 40%縮小（最大）
        }
        
        # パワーレベルに基づくTP拡張率
        tp_extension_map = {
            PowerLevel.NONE: 0.0,
            PowerLevel.WEAK: 0.2,       # 20%拡張
            PowerLevel.MODERATE: 0.5,   # 50%拡張
            PowerLevel.STRONG: 1.0,     # 100%拡張
            PowerLevel.VERY_STRONG: 1.5, # 150%拡張
            PowerLevel.EXTREME: 2.0     # 200%拡張（最大）
        }
        
        sl_reduction_percent = sl_reduction_map.get(multiplier_result.power_level, 0.0)
        tp_extension_percent = tp_extension_map.get(multiplier_result.power_level, 0.0)
        
        # 最大制限を適用
        sl_reduction_percent = min(sl_reduction_percent, context.config.max_sl_reduction_percent / 100)
        tp_extension_percent = min(tp_extension_percent, context.config.max_tp_extension_percent / 100)
        
        # 最適化された距離を計算
        optimized_sl_pips = base_sl_pips * (1 - sl_reduction_percent)
        optimized_tp_pips = base_tp_pips * (1 + tp_extension_percent)
        
        # 次のメジャーゾーンを探索してTPを調整
        next_major_zone_price = self._find_next_major_zone(
            entry_price, trade_direction, context.nearby_zones, optimized_tp_pips
        )
        
        if next_major_zone_price:
            # 次のメジャーゾーンまでの距離を計算
            zone_distance_pips = abs(next_major_zone_price - entry_price) * 10000
            # メジャーゾーンが計算値より遠い場合、そこまでTPを延長
            if zone_distance_pips > optimized_tp_pips:
                optimized_tp_pips = zone_distance_pips
                # 実際の拡張率を再計算
                tp_extension_percent = (optimized_tp_pips - base_tp_pips) / base_tp_pips
        
        # 強化されたRR比を計算
        enhanced_rr_ratio = optimized_tp_pips / optimized_sl_pips
        
        # 信頼度レベルを計算
        confidence_level = self._calculate_optimization_confidence(
            multiplier_result, sl_reduction_percent, tp_extension_percent
        )
        
        return RiskRewardAdjustment(
            original_sl_distance=base_sl_pips,
            original_tp_distance=base_tp_pips,
            optimized_sl_distance=optimized_sl_pips,
            optimized_tp_distance=optimized_tp_pips,
            enhanced_rr_ratio=enhanced_rr_ratio,
            sl_reduction_percent=sl_reduction_percent * 100,  # パーセンテージ表示用
            tp_extension_percent=tp_extension_percent * 100,
            confidence_level=confidence_level,
            next_major_zone_price=next_major_zone_price
        )
    
    def _find_next_major_zone(
        self, 
        entry_price: float, 
        direction: str, 
        nearby_zones: List[Any], 
        max_distance_pips: float
    ) -> Optional[float]:
        """次のメジャーゾーンを探索"""
        
        max_distance_price = max_distance_pips / 10000  # price変換
        
        candidate_zones = []
        
        for zone in nearby_zones:
            # 取引方向に応じてゾーンをフィルタ
            if direction == "long" and zone.price > entry_price:
                distance = zone.price - entry_price
                if distance <= max_distance_price * 2:  # 最大距離の2倍まで探索
                    candidate_zones.append((zone.price, distance, zone))
            elif direction == "short" and zone.price < entry_price:
                distance = entry_price - zone.price
                if distance <= max_distance_price * 2:
                    candidate_zones.append((zone.price, distance, zone))
        
        if not candidate_zones:
            return None
        
        # 距離でソートして最も近いメジャーゾーンを選択
        candidate_zones.sort(key=lambda x: x[1])
        
        # メジャーゾーンの条件をチェック（仮の条件）
        for price, distance, zone in candidate_zones:
            # メジャーゾーンの判定基準（例：過去の反応回数、強度など）
            reactions = getattr(zone, 'reaction_count', 0)
            if reactions >= 3:  # 3回以上反応があるゾーンをメジャーとする
                return price
        
        # メジャーゾーンが見つからない場合、最も近いゾーンを返す
        return candidate_zones[0][0]
    
    def _calculate_optimization_confidence(
        self, 
        multiplier_result: ZoneMultiplierResult, 
        sl_reduction: float, 
        tp_extension: float
    ) -> float:
        """最適化に対する信頼度を計算"""
        
        # パワーレベルに基づく基本信頼度
        power_confidence_map = {
            PowerLevel.NONE: 0.60,
            PowerLevel.WEAK: 0.65,
            PowerLevel.MODERATE: 0.75,
            PowerLevel.STRONG: 0.85,
            PowerLevel.VERY_STRONG: 0.92,
            PowerLevel.EXTREME: 0.95
        }
        
        base_confidence = power_confidence_map.get(multiplier_result.power_level, 0.60)
        
        # 調整の極端さによる信頼度減少
        adjustment_factor = 1.0
        if sl_reduction > 0.3:  # 30%超のSL縮小は信頼度を下げる
            adjustment_factor -= (sl_reduction - 0.3) * 0.5
        if tp_extension > 1.5:  # 150%超のTP拡張は信頼度を下げる
            adjustment_factor -= (tp_extension - 1.5) * 0.3
        
        # 乗数の信頼度を加味
        multiplier_confidence = multiplier_result.confidence_score
        
        # 総合信頼度
        final_confidence = base_confidence * adjustment_factor * (0.8 + 0.2 * multiplier_confidence)
        
        return round(max(0.5, min(0.95, final_confidence)), 3)