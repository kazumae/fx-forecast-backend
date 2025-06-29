from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, List, Tuple
import math
from src.domain.models.price_calculation import (
    TakeProfitLevel, PriceCalculationInput
)
from src.domain.models.entry_signal import SignalDirection


class TakeProfitCalculator:
    """テイクプロフィット計算器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # デフォルト設定
        self.default_tp_ratios = self.config.get("default_tp_ratios", [1.0, 1.5, 2.5])
        self.tp_percentages = self.config.get("tp_percentages", [50, 30, 20])
        self.psychological_levels = self.config.get("psychological_levels", [50, 100])  # 00, 50レベル
        self.fibonacci_extensions = self.config.get("fibonacci_extensions", [1.618, 2.618, 4.236])
        self.min_tp_distance_pips = self.config.get("min_tp_distance_pips", 5.0)
    
    def calculate_take_profits(
        self,
        input_data: PriceCalculationInput,
        direction: SignalDirection,
        sl_distance_pips: float,
        nearby_zones: Optional[List[Dict[str, Any]]] = None
    ) -> List[TakeProfitLevel]:
        """テイクプロフィット価格を計算"""
        
        take_profits = []
        
        # 1. 次のゾーンまでのTPを計算
        zone_based_tps = self._calculate_zone_based_tps(
            input_data, direction, nearby_zones
        )
        
        # 2. 心理的価格レベルのTPを計算
        psychological_tps = self._calculate_psychological_tps(
            input_data, direction, sl_distance_pips
        )
        
        # 3. フィボナッチ拡張レベルのTPを計算
        fibonacci_tps = self._calculate_fibonacci_tps(
            input_data, direction, sl_distance_pips
        )
        
        # 4. デフォルトのRR比ベースのTPを計算
        default_tps = self._calculate_default_tps(
            input_data, direction, sl_distance_pips
        )
        
        # 5. 最適なTPを選択して統合
        take_profits = self._merge_and_select_tps(
            zone_based_tps, psychological_tps, fibonacci_tps, default_tps,
            input_data.entry_price, direction
        )
        
        # 6. 各TPの決済割合を設定
        take_profits = self._assign_percentages(take_profits)
        
        return take_profits[:3]  # 最大3つまで
    
    def _calculate_zone_based_tps(
        self,
        input_data: PriceCalculationInput,
        direction: SignalDirection,
        nearby_zones: Optional[List[Dict[str, Any]]] = None
    ) -> List[TakeProfitLevel]:
        """ゾーンベースのTP計算"""
        
        if not nearby_zones:
            return []
        
        zone_tps = []
        
        for zone in nearby_zones:
            zone_price = Decimal(str(zone["price"]))
            
            # 取引方向に応じてゾーンをフィルタ
            if direction == SignalDirection.LONG:
                # ロングの場合、エントリーより上のレジスタンスゾーン
                if zone_price > input_data.entry_price and zone.get("type") == "resistance":
                    distance_pips = float(zone_price - input_data.entry_price) * 10000
                    
                    if distance_pips >= self.min_tp_distance_pips:
                        tp = TakeProfitLevel(
                            level=len(zone_tps) + 1,
                            price=self._round_price(zone_price - Decimal("0.005")),  # 0.5pip手前
                            distance_pips=round(distance_pips, 1),
                            percentage=0,  # 後で設定
                            reason=f"次の{zone.get('class', 'A')}級レジスタンスゾーン",
                            zone_reference=zone.get("id")
                        )
                        zone_tps.append(tp)
            else:
                # ショートの場合、エントリーより下のサポートゾーン
                if zone_price < input_data.entry_price and zone.get("type") == "support":
                    distance_pips = float(input_data.entry_price - zone_price) * 10000
                    
                    if distance_pips >= self.min_tp_distance_pips:
                        tp = TakeProfitLevel(
                            level=len(zone_tps) + 1,
                            price=self._round_price(zone_price + Decimal("0.005")),  # 0.5pip手前
                            distance_pips=round(distance_pips, 1),
                            percentage=0,
                            reason=f"次の{zone.get('class', 'A')}級サポートゾーン",
                            zone_reference=zone.get("id")
                        )
                        zone_tps.append(tp)
        
        # 距離順にソート
        zone_tps.sort(key=lambda x: x.distance_pips)
        
        return zone_tps
    
    def _calculate_psychological_tps(
        self,
        input_data: PriceCalculationInput,
        direction: SignalDirection,
        sl_distance_pips: float
    ) -> List[TakeProfitLevel]:
        """心理的価格レベルのTP計算"""
        
        psychological_tps = []
        entry_price_float = float(input_data.entry_price)
        
        # 価格の整数部分を取得
        price_integer = int(entry_price_float)
        
        # 心理的レベルを探索
        for level in self.psychological_levels:
            if level == 100:  # 00レベル
                # 上下の00レベルを探す
                if direction == SignalDirection.LONG:
                    target_price = float(price_integer + 1)
                else:
                    target_price = float(price_integer)
            else:  # 50レベル
                if direction == SignalDirection.LONG:
                    target_price = float(price_integer) + 0.50
                    if target_price <= entry_price_float:
                        target_price += 1.0
                else:
                    target_price = float(price_integer) + 0.50
                    if target_price >= entry_price_float:
                        target_price -= 1.0
            
            distance = abs(target_price - entry_price_float)
            distance_pips = distance * 10000
            
            # 最小距離とRR比をチェック
            if distance_pips >= self.min_tp_distance_pips and distance_pips >= sl_distance_pips:
                tp = TakeProfitLevel(
                    level=len(psychological_tps) + 1,
                    price=self._round_price(Decimal(str(target_price))),
                    distance_pips=round(distance_pips, 1),
                    percentage=0,
                    reason=f"心理的価格（{target_price:.2f}）",
                    psychological_level=Decimal(str(target_price))
                )
                psychological_tps.append(tp)
        
        return psychological_tps
    
    def _calculate_fibonacci_tps(
        self,
        input_data: PriceCalculationInput,
        direction: SignalDirection,
        sl_distance_pips: float
    ) -> List[TakeProfitLevel]:
        """フィボナッチ拡張レベルのTP計算"""
        
        fibonacci_tps = []
        
        # スイングの高値・安値が必要（仮定）
        swing_range = input_data.zone_info.get("swing_range", sl_distance_pips)
        
        for fib_level in self.fibonacci_extensions:
            extension_pips = swing_range * fib_level
            
            if extension_pips < self.min_tp_distance_pips:
                continue
            
            extension_price = Decimal(str(extension_pips / 10000))
            
            if direction == SignalDirection.LONG:
                tp_price = input_data.entry_price + extension_price
            else:
                tp_price = input_data.entry_price - extension_price
            
            tp = TakeProfitLevel(
                level=len(fibonacci_tps) + 1,
                price=self._round_price(tp_price),
                distance_pips=round(extension_pips, 1),
                percentage=0,
                reason=f"フィボナッチ{fib_level * 100:.1f}%拡張",
                fibonacci_level=fib_level
            )
            fibonacci_tps.append(tp)
        
        return fibonacci_tps
    
    def _calculate_default_tps(
        self,
        input_data: PriceCalculationInput,
        direction: SignalDirection,
        sl_distance_pips: float
    ) -> List[TakeProfitLevel]:
        """デフォルトのRR比ベースのTP計算"""
        
        default_tps = []
        
        for i, ratio in enumerate(self.default_tp_ratios):
            tp_distance_pips = sl_distance_pips * ratio
            tp_distance_price = Decimal(str(tp_distance_pips / 10000))
            
            if direction == SignalDirection.LONG:
                tp_price = input_data.entry_price + tp_distance_price
            else:
                tp_price = input_data.entry_price - tp_distance_price
            
            tp = TakeProfitLevel(
                level=i + 1,
                price=self._round_price(tp_price),
                distance_pips=round(tp_distance_pips, 1),
                percentage=0,
                reason=f"RR比 1:{ratio}"
            )
            default_tps.append(tp)
        
        return default_tps
    
    def _merge_and_select_tps(
        self,
        zone_tps: List[TakeProfitLevel],
        psychological_tps: List[TakeProfitLevel],
        fibonacci_tps: List[TakeProfitLevel],
        default_tps: List[TakeProfitLevel],
        entry_price: Decimal,
        direction: SignalDirection
    ) -> List[TakeProfitLevel]:
        """異なる方法で計算されたTPを統合して最適なものを選択"""
        
        all_tps = []
        
        # 優先順位: ゾーン > 心理的価格 > フィボナッチ > デフォルト
        
        # TP1: 最初のゾーンまたは心理的価格
        if zone_tps:
            all_tps.append(zone_tps[0])
        elif psychological_tps:
            all_tps.append(psychological_tps[0])
        elif default_tps:
            all_tps.append(default_tps[0])
        
        # TP2: 次のメジャーレベル
        remaining_zones = zone_tps[1:] if len(zone_tps) > 1 else []
        remaining_psych = psychological_tps[1:] if len(psychological_tps) > 1 else []
        
        if remaining_zones:
            all_tps.append(remaining_zones[0])
        elif remaining_psych:
            all_tps.append(remaining_psych[0])
        elif fibonacci_tps:
            all_tps.append(fibonacci_tps[0])
        elif len(default_tps) > 1:
            all_tps.append(default_tps[1])
        
        # TP3: 遠いターゲット
        if len(fibonacci_tps) > 1:
            all_tps.append(fibonacci_tps[1])
        elif len(default_tps) > 2:
            all_tps.append(default_tps[2])
        
        # レベルを再割り当て
        for i, tp in enumerate(all_tps):
            tp.level = i + 1
        
        return all_tps
    
    def _assign_percentages(self, take_profits: List[TakeProfitLevel]) -> List[TakeProfitLevel]:
        """各TPに決済割合を割り当て"""
        
        tp_count = len(take_profits)
        
        if tp_count == 0:
            return take_profits
        elif tp_count == 1:
            take_profits[0].percentage = 100.0
        elif tp_count == 2:
            take_profits[0].percentage = 60.0
            take_profits[1].percentage = 40.0
        else:  # 3つ以上
            # デフォルトの割合を使用
            for i, tp in enumerate(take_profits[:3]):
                if i < len(self.tp_percentages):
                    tp.percentage = self.tp_percentages[i]
                else:
                    tp.percentage = 100.0 / tp_count
        
        # 合計が100%になるよう調整
        total_percentage = sum(tp.percentage for tp in take_profits)
        if total_percentage != 100.0 and total_percentage > 0:
            factor = 100.0 / total_percentage
            for tp in take_profits:
                tp.percentage *= factor
        
        return take_profits
    
    def _round_price(self, price: Decimal) -> Decimal:
        """価格を0.1pip単位に丸める（XAUUSDの場合）"""
        return price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)