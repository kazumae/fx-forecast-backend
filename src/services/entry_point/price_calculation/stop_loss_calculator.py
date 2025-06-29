from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, List, Tuple
from src.domain.models.price_calculation import (
    StopLossCalculation, CalculationMethod, PriceCalculationInput
)
from src.domain.models.entry_signal import SignalDirection


class StopLossCalculator:
    """ストップロス計算器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # デフォルト設定
        self.min_sl_pips = self.config.get("min_sl_pips", 10.0)
        self.max_sl_pips = self.config.get("max_sl_pips", 50.0)
        self.atr_multiplier = self.config.get("atr_multiplier", 1.5)
        self.zone_buffer_pips = self.config.get("zone_buffer_pips", 2.0)
        
        # パターン別のデフォルトSL設定
        self.pattern_sl_config = {
            "V_SHAPE_REVERSAL": {"method": CalculationMethod.SWING_BASED, "buffer": 3.0},
            "EMA_SQUEEZE": {"method": CalculationMethod.ZONE_BASED, "buffer": 2.0},
            "TREND_CONTINUATION": {"method": CalculationMethod.ATR_BASED, "buffer": 1.5},
            "FALSE_BREAKOUT": {"method": CalculationMethod.HYBRID, "buffer": 2.5}
        }
    
    def calculate_stop_loss(
        self,
        input_data: PriceCalculationInput,
        direction: SignalDirection,
        swing_points: Optional[List[Dict[str, Any]]] = None
    ) -> StopLossCalculation:
        """ストップロス価格を計算"""
        
        # パターンに基づく計算方法を決定
        pattern_config = self.pattern_sl_config.get(
            input_data.pattern_type,
            {"method": CalculationMethod.ATR_BASED, "buffer": 2.0}
        )
        
        calculation_method = pattern_config["method"]
        
        # 各方法で計算
        if calculation_method == CalculationMethod.ZONE_BASED:
            sl_calc = self._calculate_zone_based_sl(input_data, direction)
        elif calculation_method == CalculationMethod.SWING_BASED:
            sl_calc = self._calculate_swing_based_sl(input_data, direction, swing_points)
        elif calculation_method == CalculationMethod.ATR_BASED:
            sl_calc = self._calculate_atr_based_sl(input_data, direction)
        else:  # HYBRID
            sl_calc = self._calculate_hybrid_sl(input_data, direction, swing_points)
        
        # ATRによる動的調整
        sl_calc = self._apply_atr_adjustment(sl_calc, input_data.current_atr)
        
        # 最小/最大制限を適用
        sl_calc = self._apply_limits(sl_calc, input_data.entry_price)
        
        return sl_calc
    
    def _calculate_zone_based_sl(
        self,
        input_data: PriceCalculationInput,
        direction: SignalDirection
    ) -> StopLossCalculation:
        """ゾーンベースのSL計算"""
        
        zone_info = input_data.zone_info
        zone_price = Decimal(str(zone_info.get("price", input_data.entry_price)))
        zone_type = zone_info.get("type", "resistance")
        
        # ゾーンの外側にSLを設定
        buffer_price = Decimal(str(self.zone_buffer_pips / 10000))
        
        if direction == SignalDirection.LONG:
            # ロングの場合、サポートゾーンの下
            if zone_type == "support":
                sl_price = zone_price - buffer_price
            else:
                # レジスタンスゾーンからのロングは少し離す
                sl_price = input_data.entry_price - Decimal(str(20.0 / 10000))
        else:
            # ショートの場合、レジスタンスゾーンの上
            if zone_type == "resistance":
                sl_price = zone_price + buffer_price
            else:
                # サポートゾーンからのショートは少し離す
                sl_price = input_data.entry_price + Decimal(str(20.0 / 10000))
        
        distance_pips = abs(float(input_data.entry_price - sl_price)) * 10000
        
        return StopLossCalculation(
            price=self._round_price(sl_price),
            distance_pips=round(distance_pips, 1),
            calculation_method=CalculationMethod.ZONE_BASED,
            details=f"{zone_info.get('class', 'A')}級ゾーン{'下限' if direction == SignalDirection.LONG else '上限'} - {self.zone_buffer_pips}pips",
            zone_reference=zone_info.get("id")
        )
    
    def _calculate_swing_based_sl(
        self,
        input_data: PriceCalculationInput,
        direction: SignalDirection,
        swing_points: Optional[List[Dict[str, Any]]] = None
    ) -> StopLossCalculation:
        """スイングハイ/ローベースのSL計算"""
        
        if not swing_points:
            # スイングポイントがない場合はATRベースにフォールバック
            return self._calculate_atr_based_sl(input_data, direction)
        
        # 最も近い有効なスイングポイントを探す
        valid_swing = None
        min_distance = float('inf')
        
        for swing in swing_points:
            swing_price = Decimal(str(swing["price"]))
            
            if direction == SignalDirection.LONG:
                # ロングの場合、エントリーより下のスイングローを探す
                if swing["type"] == "low" and swing_price < input_data.entry_price:
                    distance = float(input_data.entry_price - swing_price)
                    if distance < min_distance:
                        min_distance = distance
                        valid_swing = swing
            else:
                # ショートの場合、エントリーより上のスイングハイを探す
                if swing["type"] == "high" and swing_price > input_data.entry_price:
                    distance = float(swing_price - input_data.entry_price)
                    if distance < min_distance:
                        min_distance = distance
                        valid_swing = swing
        
        if valid_swing:
            swing_price = Decimal(str(valid_swing["price"]))
            buffer_price = Decimal(str(3.0 / 10000))  # 3pipsバッファー
            
            if direction == SignalDirection.LONG:
                sl_price = swing_price - buffer_price
            else:
                sl_price = swing_price + buffer_price
            
            distance_pips = abs(float(input_data.entry_price - sl_price)) * 10000
            
            return StopLossCalculation(
                price=self._round_price(sl_price),
                distance_pips=round(distance_pips, 1),
                calculation_method=CalculationMethod.SWING_BASED,
                details=f"スイング{'ロー' if direction == SignalDirection.LONG else 'ハイ'} - 3pips",
                swing_reference=f"Swing at {valid_swing['price']}"
            )
        else:
            # 有効なスイングがない場合はATRベース
            return self._calculate_atr_based_sl(input_data, direction)
    
    def _calculate_atr_based_sl(
        self,
        input_data: PriceCalculationInput,
        direction: SignalDirection
    ) -> StopLossCalculation:
        """ATRベースのSL計算"""
        
        # ATRに基づくSL距離
        sl_distance_price = Decimal(str(input_data.current_atr * self.atr_multiplier / 10000))
        
        if direction == SignalDirection.LONG:
            sl_price = input_data.entry_price - sl_distance_price
        else:
            sl_price = input_data.entry_price + sl_distance_price
        
        distance_pips = input_data.current_atr * self.atr_multiplier
        
        return StopLossCalculation(
            price=self._round_price(sl_price),
            distance_pips=round(distance_pips, 1),
            calculation_method=CalculationMethod.ATR_BASED,
            details=f"{self.atr_multiplier}×ATR({input_data.current_atr:.1f}pips)",
            atr_factor=self.atr_multiplier
        )
    
    def _calculate_hybrid_sl(
        self,
        input_data: PriceCalculationInput,
        direction: SignalDirection,
        swing_points: Optional[List[Dict[str, Any]]] = None
    ) -> StopLossCalculation:
        """ハイブリッドSL計算（複数の方法を組み合わせ）"""
        
        # 各方法で計算
        zone_sl = self._calculate_zone_based_sl(input_data, direction)
        swing_sl = self._calculate_swing_based_sl(input_data, direction, swing_points)
        atr_sl = self._calculate_atr_based_sl(input_data, direction)
        
        # 最も保守的な（遠い）SLを選択
        candidates = [
            (zone_sl.distance_pips, zone_sl),
            (swing_sl.distance_pips, swing_sl),
            (atr_sl.distance_pips, atr_sl)
        ]
        
        # 最小距離と最大距離の間で選択
        valid_candidates = [
            (dist, sl) for dist, sl in candidates 
            if self.min_sl_pips <= dist <= self.max_sl_pips
        ]
        
        if valid_candidates:
            # 有効な候補の中で中間値を選択
            valid_candidates.sort(key=lambda x: x[0])
            selected_sl = valid_candidates[len(valid_candidates) // 2][1]
        else:
            # 全て範囲外の場合はATRベースを使用
            selected_sl = atr_sl
        
        selected_sl.calculation_method = CalculationMethod.HYBRID
        selected_sl.details = f"ハイブリッド計算 - {selected_sl.details}"
        
        return selected_sl
    
    def _apply_atr_adjustment(
        self,
        sl_calc: StopLossCalculation,
        current_atr: float
    ) -> StopLossCalculation:
        """ATRによる動的調整を適用"""
        
        # ATRが通常より高い場合は拡大
        normal_atr = 15.0  # 通常のATR（仮定）
        
        if current_atr > normal_atr * 1.5:
            # 高ボラティリティ
            adjustment_factor = 1.2
            sl_calc.distance_pips *= adjustment_factor
            sl_calc.details += f" (高ボラ調整×{adjustment_factor})"
        elif current_atr < normal_atr * 0.7:
            # 低ボラティリティ
            adjustment_factor = 0.9
            sl_calc.distance_pips *= adjustment_factor
            sl_calc.details += f" (低ボラ調整×{adjustment_factor})"
        
        return sl_calc
    
    def _apply_limits(
        self,
        sl_calc: StopLossCalculation,
        entry_price: Decimal
    ) -> StopLossCalculation:
        """最小/最大制限を適用"""
        
        # 距離を制限内に収める
        original_distance = sl_calc.distance_pips
        sl_calc.distance_pips = max(self.min_sl_pips, min(self.max_sl_pips, sl_calc.distance_pips))
        
        # 価格を再計算
        if sl_calc.distance_pips != original_distance:
            # 調整が必要な場合
            adjusted_distance_price = Decimal(str(sl_calc.distance_pips / 10000))
            
            # 元の価格との差分から方向を判定
            if sl_calc.price < entry_price:
                # ロング方向
                sl_calc.price = entry_price - adjusted_distance_price
            else:
                # ショート方向
                sl_calc.price = entry_price + adjusted_distance_price
            
            sl_calc.price = self._round_price(sl_calc.price)
            sl_calc.details += f" (制限適用: {original_distance:.1f}→{sl_calc.distance_pips:.1f}pips)"
        
        return sl_calc
    
    def _round_price(self, price: Decimal) -> Decimal:
        """価格を0.1pip単位に丸める（XAUUSDの場合）"""
        return price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)