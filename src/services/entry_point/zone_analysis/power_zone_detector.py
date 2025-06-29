from datetime import datetime
from typing import List, Dict, Any
from src.domain.models.zone_multiplier import (
    PowerZoneComponent, PowerZoneType, MultiplierContext, MultiplierConfig
)


class PowerZoneDetector:
    """パワーゾーンコンポーネント検出器"""
    
    def __init__(self, config: MultiplierConfig):
        self.config = config
    
    def detect_power_zone_components(self, context: MultiplierContext) -> List[PowerZoneComponent]:
        """パワーゾーンコンポーネントを検出"""
        components = []
        
        # EMA重なり検出
        ema_components = self._detect_ema_overlaps(context.target_zone, context.ema_values)
        components.extend(ema_components)
        
        # ゾーンクラスター検出
        cluster_components = self._detect_zone_clusters(context.target_zone, context.nearby_zones)
        components.extend(cluster_components)
        
        # 役割転換検出
        reversal_components = self._detect_role_reversals(context.target_zone)
        components.extend(reversal_components)
        
        # マルチタイムフレーム分析
        mtf_components = self._detect_multi_timeframe_overlap(context.target_zone, context.market_data)
        components.extend(mtf_components)
        
        return components
    
    def _detect_ema_overlaps(self, zone: Any, ema_values: List[Any]) -> List[PowerZoneComponent]:
        """EMAとの重なりを検出"""
        components = []
        
        for ema in ema_values:
            if ema.period in [75, 200]:  # 重要なEMA期間
                distance = abs(zone.price - ema.value)
                distance_pips = distance * 10000  # pips変換（仮定）
                
                if distance_pips <= self.config.ema_overlap_distance_pips:
                    # 距離に基づく強度計算（近いほど強い）
                    strength = max(0.0, 1.0 - (distance_pips / self.config.ema_overlap_distance_pips))
                    
                    # 期間による調整（200EMAの方が重要）
                    period_factor = 1.2 if ema.period == 200 else 1.0
                    
                    multiplier_contribution = self.config.ema_overlap_base_multiplier * strength * period_factor
                    
                    component = PowerZoneComponent(
                        component_type=PowerZoneType.EMA_OVERLAP,
                        strength=strength,
                        multiplier_contribution=multiplier_contribution,
                        detected_at=datetime.now(),
                        details={
                            "ema_period": ema.period,
                            "ema_value": ema.value,
                            "zone_price": zone.price,
                            "distance_pips": distance_pips,
                            "period_factor": period_factor
                        }
                    )
                    components.append(component)
        
        return components
    
    def _detect_zone_clusters(self, zone: Any, nearby_zones: List[Any]) -> List[PowerZoneComponent]:
        """ゾーンクラスターを検出"""
        components = []
        
        # 設定距離内のゾーンを検索
        cluster_zones = []
        for nearby_zone in nearby_zones:
            distance = abs(zone.price - nearby_zone.price)
            distance_pips = distance * 10000
            
            if distance_pips <= self.config.cluster_distance_pips:
                cluster_zones.append(nearby_zone)
        
        # 最小ゾーン数を満たすか確認
        if len(cluster_zones) >= self.config.cluster_min_zones:
            # クラスター強度計算（ゾーン数に基づく）
            zone_count = len(cluster_zones)
            strength = min(1.0, zone_count / 5.0)  # 5個で最大強度
            
            # ゾーン数による乗数ボーナス
            zone_bonus = min(0.4, (zone_count - 3) * 0.1)  # 3個超で0.1ずつボーナス
            multiplier_contribution = (self.config.cluster_base_multiplier + zone_bonus) * strength
            
            component = PowerZoneComponent(
                component_type=PowerZoneType.ZONE_CLUSTER,
                strength=strength,
                multiplier_contribution=multiplier_contribution,
                detected_at=datetime.now(),
                details={
                    "zone_count": zone_count,
                    "cluster_zones": [z.price for z in cluster_zones],
                    "zone_bonus": zone_bonus,
                    "max_distance_pips": max([abs(zone.price - z.price) * 10000 for z in cluster_zones])
                }
            )
            components.append(component)
        
        return components
    
    def _detect_role_reversals(self, zone: Any) -> List[PowerZoneComponent]:
        """役割転換を検出"""
        components = []
        
        # ゾーンの役割履歴を確認
        role_history = getattr(zone, 'role_history', [])
        
        if len(role_history) >= self.config.role_reversal_min_changes:
            # 役割変更回数を計算
            changes = 0
            for i in range(1, len(role_history)):
                if role_history[i] != role_history[i-1]:
                    changes += 1
            
            if changes >= self.config.role_reversal_min_changes:
                # 変更回数に基づく強度計算
                strength = min(1.0, changes / 5.0)  # 5回変更で最大強度
                
                # 変更回数による乗数ボーナス
                change_bonus = min(0.26, (changes - 2) * 0.13)  # 2回超で0.13ずつボーナス
                multiplier_contribution = (self.config.role_reversal_base_multiplier + change_bonus) * strength
                
                component = PowerZoneComponent(
                    component_type=PowerZoneType.ROLE_REVERSAL,
                    strength=strength,
                    multiplier_contribution=multiplier_contribution,
                    detected_at=datetime.now(),
                    details={
                        "role_changes": changes,
                        "role_history": role_history,
                        "change_bonus": change_bonus,
                        "historical_reliability": min(0.95, 0.6 + changes * 0.1)
                    }
                )
                components.append(component)
        
        return components
    
    def _detect_multi_timeframe_overlap(self, zone: Any, market_data: Dict[str, Any]) -> List[PowerZoneComponent]:
        """マルチタイムフレーム重複を検出"""
        components = []
        
        # 複数タイムフレームのゾーンデータを確認
        mtf_zones = market_data.get('multi_timeframe_zones', {})
        
        if not mtf_zones:
            return components
        
        overlapping_timeframes = []
        for timeframe, zones in mtf_zones.items():
            for mtf_zone in zones:
                distance = abs(zone.price - mtf_zone.price)
                distance_pips = distance * 10000
                
                if distance_pips <= 20.0:  # 20pips以内で重複と判定
                    overlapping_timeframes.append({
                        'timeframe': timeframe,
                        'zone': mtf_zone,
                        'distance_pips': distance_pips
                    })
        
        # 2つ以上のタイムフレームで重複している場合
        if len(overlapping_timeframes) >= 2:
            tf_count = len(overlapping_timeframes)
            strength = min(1.0, tf_count / 4.0)  # 4タイムフレームで最大強度
            
            # タイムフレーム数による乗数
            base_multiplier = 1.2
            tf_bonus = (tf_count - 2) * 0.15
            multiplier_contribution = (base_multiplier + tf_bonus) * strength
            
            component = PowerZoneComponent(
                component_type=PowerZoneType.MULTI_TIMEFRAME,
                strength=strength,
                multiplier_contribution=multiplier_contribution,
                detected_at=datetime.now(),
                details={
                    "timeframe_count": tf_count,
                    "overlapping_timeframes": [tf['timeframe'] for tf in overlapping_timeframes],
                    "tf_bonus": tf_bonus,
                    "avg_distance_pips": sum([tf['distance_pips'] for tf in overlapping_timeframes]) / tf_count
                }
            )
            components.append(component)
        
        return components