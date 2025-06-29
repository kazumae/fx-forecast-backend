from decimal import Decimal
from typing import List, Optional, Dict, Any
from src.domain.models.price_calculation import (
    StopLossCalculation, TakeProfitLevel, RiskRewardAnalysis, PriceCalculationInput
)
from src.domain.models.entry_signal import SignalDirection


class RiskRewardValidator:
    """リスクリワード比検証器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # デフォルト設定
        self.min_rr_ratio = self.config.get("min_rr_ratio", 1.5)
        self.target_rr_ratio = self.config.get("target_rr_ratio", 2.0)
        self.max_sl_adjustment = self.config.get("max_sl_adjustment", 0.8)  # 最大20%縮小
        self.max_tp_adjustment = self.config.get("max_tp_adjustment", 1.5)  # 最大50%拡大
    
    def validate_and_analyze(
        self,
        stop_loss: StopLossCalculation,
        take_profits: List[TakeProfitLevel],
        entry_price: Decimal,
        direction: SignalDirection
    ) -> RiskRewardAnalysis:
        """リスクリワード比を検証・分析"""
        
        # リスク量（SLまでの距離）
        risk_amount = stop_loss.distance_pips
        
        # 各TPまでのリワード量を計算
        rewards = []
        for tp in take_profits:
            rewards.append(tp.distance_pips)
        
        # RR比を計算
        rr_ratios = [reward / risk_amount for reward in rewards] if risk_amount > 0 else [0.0]
        
        # 加重平均RR比を計算（決済割合で加重）
        weighted_rr = 0.0
        total_percentage = 0.0
        
        for i, tp in enumerate(take_profits):
            if i < len(rr_ratios):
                weighted_rr += rr_ratios[i] * (tp.percentage / 100.0)
                total_percentage += tp.percentage / 100.0
        
        if total_percentage > 0:
            weighted_rr /= total_percentage
        
        # 最小RR比を満たしているか確認
        meets_minimum = weighted_rr >= self.min_rr_ratio
        
        # 推奨調整を生成
        recommended_adjustment = None
        if not meets_minimum:
            recommended_adjustment = self._generate_adjustment_recommendation(
                risk_amount, rewards, weighted_rr
            )
        
        return RiskRewardAnalysis(
            risk_amount=risk_amount,
            reward_tp1=rewards[0] if rewards else 0.0,
            reward_tp2=rewards[1] if len(rewards) > 1 else None,
            reward_tp3=rewards[2] if len(rewards) > 2 else None,
            rr_ratio_tp1=rr_ratios[0] if rr_ratios else 0.0,
            rr_ratio_weighted=weighted_rr,
            meets_minimum=meets_minimum,
            recommended_adjustment=recommended_adjustment
        )
    
    def adjust_for_minimum_rr(
        self,
        stop_loss: StopLossCalculation,
        take_profits: List[TakeProfitLevel],
        entry_price: Decimal,
        direction: SignalDirection,
        input_data: PriceCalculationInput
    ) -> tuple[StopLossCalculation, List[TakeProfitLevel]]:
        """最小RR比を満たすように調整"""
        
        # 現在のRR分析
        analysis = self.validate_and_analyze(stop_loss, take_profits, entry_price, direction)
        
        if analysis.meets_minimum:
            return stop_loss, take_profits
        
        # 調整戦略を試行
        adjusted_sl, adjusted_tps = self._try_sl_reduction(
            stop_loss, take_profits, entry_price, direction, input_data
        )
        
        # 再度検証
        new_analysis = self.validate_and_analyze(adjusted_sl, adjusted_tps, entry_price, direction)
        
        if new_analysis.meets_minimum:
            return adjusted_sl, adjusted_tps
        
        # SL調整で不十分な場合、TPを拡大
        adjusted_sl, adjusted_tps = self._try_tp_expansion(
            adjusted_sl, adjusted_tps, entry_price, direction, input_data
        )
        
        return adjusted_sl, adjusted_tps
    
    def _generate_adjustment_recommendation(
        self,
        risk_amount: float,
        rewards: List[float],
        current_rr: float
    ) -> str:
        """調整推奨事項を生成"""
        
        needed_rr = self.min_rr_ratio
        rr_deficit = needed_rr - current_rr
        
        # 必要なリワード増加率
        reward_increase = (needed_rr / current_rr - 1) * 100 if current_rr > 0 else 100
        
        # 必要なリスク削減率
        risk_reduction = (1 - current_rr / needed_rr) * 100 if needed_rr > 0 else 0
        
        recommendations = []
        
        if risk_reduction <= 20:  # SL調整で対応可能
            recommendations.append(f"SLを{risk_reduction:.1f}%近づける")
        
        if reward_increase <= 50:  # TP調整で対応可能
            recommendations.append(f"TPを{reward_increase:.1f}%遠ざける")
        
        if not recommendations:
            recommendations.append("エントリーを見送ることを推奨")
        
        return " または ".join(recommendations)
    
    def _try_sl_reduction(
        self,
        stop_loss: StopLossCalculation,
        take_profits: List[TakeProfitLevel],
        entry_price: Decimal,
        direction: SignalDirection,
        input_data: PriceCalculationInput
    ) -> tuple[StopLossCalculation, List[TakeProfitLevel]]:
        """SLを近づけて調整を試みる"""
        
        # 最大調整量を計算
        max_reduction = stop_loss.distance_pips * (1 - self.max_sl_adjustment)
        new_sl_distance = stop_loss.distance_pips - max_reduction
        
        # 最小SL距離を維持
        min_sl_pips = 10.0
        if new_sl_distance < min_sl_pips:
            new_sl_distance = min_sl_pips
        
        # 新しいSL価格を計算
        sl_adjustment = Decimal(str((stop_loss.distance_pips - new_sl_distance) / 10000))
        
        if direction == SignalDirection.LONG:
            new_sl_price = stop_loss.price + sl_adjustment
        else:
            new_sl_price = stop_loss.price - sl_adjustment
        
        # 新しいSLオブジェクトを作成
        adjusted_sl = StopLossCalculation(
            price=new_sl_price,
            distance_pips=new_sl_distance,
            calculation_method=stop_loss.calculation_method,
            details=stop_loss.details + f" (RR調整: {stop_loss.distance_pips:.1f}→{new_sl_distance:.1f}pips)",
            zone_reference=stop_loss.zone_reference,
            swing_reference=stop_loss.swing_reference,
            atr_factor=stop_loss.atr_factor
        )
        
        return adjusted_sl, take_profits
    
    def _try_tp_expansion(
        self,
        stop_loss: StopLossCalculation,
        take_profits: List[TakeProfitLevel],
        entry_price: Decimal,
        direction: SignalDirection,
        input_data: PriceCalculationInput
    ) -> tuple[StopLossCalculation, List[TakeProfitLevel]]:
        """TPを遠ざけて調整を試みる"""
        
        adjusted_tps = []
        
        for tp in take_profits:
            # 最大調整量を計算
            new_distance = tp.distance_pips * self.max_tp_adjustment
            
            # 新しいTP価格を計算
            tp_adjustment = Decimal(str((new_distance - tp.distance_pips) / 10000))
            
            if direction == SignalDirection.LONG:
                new_tp_price = tp.price + tp_adjustment
            else:
                new_tp_price = tp.price - tp_adjustment
            
            # 新しいTPオブジェクトを作成
            adjusted_tp = TakeProfitLevel(
                level=tp.level,
                price=new_tp_price,
                distance_pips=new_distance,
                percentage=tp.percentage,
                reason=tp.reason + f" (RR調整: {tp.distance_pips:.1f}→{new_distance:.1f}pips)",
                zone_reference=tp.zone_reference,
                psychological_level=tp.psychological_level,
                fibonacci_level=tp.fibonacci_level
            )
            
            adjusted_tps.append(adjusted_tp)
        
        return stop_loss, adjusted_tps
    
    def calculate_position_size(
        self,
        risk_amount_pips: float,
        account_risk_percentage: float = 1.0,
        account_balance: float = 10000.0,
        pip_value: float = 1.0
    ) -> Dict[str, float]:
        """ポジションサイズを計算"""
        
        # リスク金額を計算
        risk_amount_money = account_balance * (account_risk_percentage / 100.0)
        
        # ポジションサイズを計算（ロット数）
        position_size = risk_amount_money / (risk_amount_pips * pip_value)
        
        # 最小/最大ロット制限
        min_lot = 0.01
        max_lot = 10.0
        position_size = max(min_lot, min(max_lot, position_size))
        
        return {
            "position_size_lots": round(position_size, 2),
            "risk_amount_money": round(risk_amount_money, 2),
            "risk_amount_pips": round(risk_amount_pips, 1),
            "pip_value": pip_value,
            "account_risk_percentage": account_risk_percentage
        }