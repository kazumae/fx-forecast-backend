from decimal import Decimal
from typing import List, Optional, Dict, Any
from src.domain.models.entry_signal import EntrySignal, SignalDirection, OrderType
from src.domain.models.signal_validation import (
    ValidationCheck, ValidationCheckType, ValidationSeverity
)


class BusinessLogicValidator:
    """ビジネスロジック検証器"""
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.max_entry_distance_pips = self.config.get("max_entry_distance_pips", 5.0)
        self.min_sl_pips = self.config.get("min_sl_pips", 10.0)
        self.max_sl_pips = self.config.get("max_sl_pips", 50.0)
        self.min_rr_ratio = self.config.get("min_rr_ratio", 1.5)
        self.max_slippage_pips = self.config.get("max_slippage_pips", 2.0)
    
    def validate(
        self,
        signal: EntrySignal,
        current_price: Decimal,
        current_spread: float
    ) -> List[ValidationCheck]:
        """ビジネスロジックを検証"""
        checks = []
        
        # エントリー価格の妥当性チェック
        checks.append(self._check_entry_price_range(signal, current_price, current_spread))
        
        # ストップロスの位置チェック
        checks.append(self._check_stop_loss_position(signal))
        
        # テイクプロフィットの順序チェック
        checks.append(self._check_take_profit_order(signal))
        
        # リスクリワード比チェック
        checks.append(self._check_risk_reward_ratio(signal))
        
        return checks
    
    def _check_entry_price_range(
        self,
        signal: EntrySignal,
        current_price: Decimal,
        current_spread: float
    ) -> ValidationCheck:
        """エントリー価格が現在価格から妥当な範囲内か確認"""
        
        if not signal.entry or not signal.entry.price:
            return ValidationCheck(
                check_name=ValidationCheckType.ENTRY_PRICE_RANGE,
                passed=False,
                message="エントリー価格が設定されていません",
                severity=ValidationSeverity.CRITICAL
            )
        
        entry_price = Decimal(str(signal.entry.price))
        
        # スプレッドを考慮した実効価格
        if signal.direction == SignalDirection.LONG:
            effective_price = current_price + Decimal(str(current_spread / 10000))
        else:
            effective_price = current_price
        
        # 価格差を計算
        price_diff = abs(float(entry_price - effective_price))
        price_diff_pips = price_diff * 10000
        
        # 注文タイプ別の検証
        if signal.entry.order_type == OrderType.MARKET:
            # 成行注文の場合、スリッページ許容範囲内か
            if price_diff_pips > self.max_slippage_pips:
                return ValidationCheck(
                    check_name=ValidationCheckType.ENTRY_PRICE_RANGE,
                    passed=False,
                    message=f"成行注文の価格差が大きすぎる: {price_diff_pips:.1f}pips",
                    severity=ValidationSeverity.WARNING,
                    details={
                        "entry_price": float(entry_price),
                        "current_price": float(current_price),
                        "price_diff_pips": price_diff_pips
                    }
                )
        else:
            # 指値/逆指値注文の場合
            if price_diff_pips > self.max_entry_distance_pips:
                return ValidationCheck(
                    check_name=ValidationCheckType.ENTRY_PRICE_RANGE,
                    passed=False,
                    message=f"エントリー価格が現在価格から離れすぎている: {price_diff_pips:.1f}pips",
                    severity=ValidationSeverity.WARNING,
                    details={
                        "entry_price": float(entry_price),
                        "current_price": float(current_price),
                        "max_allowed": self.max_entry_distance_pips
                    }
                )
            
            # 指値/逆指値の方向チェック
            if signal.entry.order_type == OrderType.LIMIT:
                if signal.direction == SignalDirection.LONG and entry_price >= current_price:
                    return ValidationCheck(
                        check_name=ValidationCheckType.ENTRY_PRICE_RANGE,
                        passed=False,
                        message="ロングの指値注文は現在価格より低い必要があります",
                        severity=ValidationSeverity.CRITICAL
                    )
                elif signal.direction == SignalDirection.SHORT and entry_price <= current_price:
                    return ValidationCheck(
                        check_name=ValidationCheckType.ENTRY_PRICE_RANGE,
                        passed=False,
                        message="ショートの指値注文は現在価格より高い必要があります",
                        severity=ValidationSeverity.CRITICAL
                    )
        
        return ValidationCheck(
            check_name=ValidationCheckType.ENTRY_PRICE_RANGE,
            passed=True,
            message=f"エントリー価格は妥当な範囲内 ({price_diff_pips:.1f}pips)"
        )
    
    def _check_stop_loss_position(self, signal: EntrySignal) -> ValidationCheck:
        """ストップロスがエントリー価格の適切な側にあるか検証"""
        
        if not signal.stop_loss or not signal.stop_loss.price:
            return ValidationCheck(
                check_name=ValidationCheckType.STOP_LOSS_POSITION,
                passed=False,
                message="ストップロスが設定されていません",
                severity=ValidationSeverity.CRITICAL
            )
        
        if not signal.entry or not signal.entry.price:
            return ValidationCheck(
                check_name=ValidationCheckType.STOP_LOSS_POSITION,
                passed=False,
                message="エントリー価格が設定されていません",
                severity=ValidationSeverity.CRITICAL
            )
        
        entry_price = Decimal(str(signal.entry.price))
        sl_price = Decimal(str(signal.stop_loss.price))
        sl_distance_pips = signal.stop_loss.distance_pips
        
        # 方向に応じた位置チェック
        if signal.direction == SignalDirection.LONG:
            if sl_price >= entry_price:
                return ValidationCheck(
                    check_name=ValidationCheckType.STOP_LOSS_POSITION,
                    passed=False,
                    message=f"ロングポジションのSLがエントリー価格以上: SL={sl_price}, Entry={entry_price}",
                    severity=ValidationSeverity.CRITICAL
                )
        else:  # SHORT
            if sl_price <= entry_price:
                return ValidationCheck(
                    check_name=ValidationCheckType.STOP_LOSS_POSITION,
                    passed=False,
                    message=f"ショートポジションのSLがエントリー価格以下: SL={sl_price}, Entry={entry_price}",
                    severity=ValidationSeverity.CRITICAL
                )
        
        # SL距離のチェック
        if sl_distance_pips < self.min_sl_pips:
            return ValidationCheck(
                check_name=ValidationCheckType.STOP_LOSS_POSITION,
                passed=False,
                message=f"SL距離が最小値未満: {sl_distance_pips:.1f}pips < {self.min_sl_pips}pips",
                severity=ValidationSeverity.WARNING
            )
        elif sl_distance_pips > self.max_sl_pips:
            return ValidationCheck(
                check_name=ValidationCheckType.STOP_LOSS_POSITION,
                passed=False,
                message=f"SL距離が最大値超過: {sl_distance_pips:.1f}pips > {self.max_sl_pips}pips",
                severity=ValidationSeverity.WARNING
            )
        
        return ValidationCheck(
            check_name=ValidationCheckType.STOP_LOSS_POSITION,
            passed=True,
            message=f"SLは適切な位置（{signal.direction.value.lower()}でエントリー{'下' if signal.direction == SignalDirection.LONG else '上'}）"
        )
    
    def _check_take_profit_order(self, signal: EntrySignal) -> ValidationCheck:
        """テイクプロフィットが順序通りに並んでいるか確認"""
        
        if not signal.take_profits or len(signal.take_profits) == 0:
            return ValidationCheck(
                check_name=ValidationCheckType.TAKE_PROFIT_ORDER,
                passed=False,
                message="テイクプロフィットが設定されていません",
                severity=ValidationSeverity.WARNING
            )
        
        if not signal.entry or not signal.entry.price:
            return ValidationCheck(
                check_name=ValidationCheckType.TAKE_PROFIT_ORDER,
                passed=False,
                message="エントリー価格が設定されていません",
                severity=ValidationSeverity.CRITICAL
            )
        
        entry_price = Decimal(str(signal.entry.price))
        
        # TPの順序チェック
        previous_tp = None
        for i, tp in enumerate(signal.take_profits):
            if not tp.price:
                return ValidationCheck(
                    check_name=ValidationCheckType.TAKE_PROFIT_ORDER,
                    passed=False,
                    message=f"TP{i+1}の価格が設定されていません",
                    severity=ValidationSeverity.CRITICAL
                )
            
            tp_price = Decimal(str(tp.price))
            
            # エントリーからの方向チェック
            if signal.direction == SignalDirection.LONG:
                if tp_price <= entry_price:
                    return ValidationCheck(
                        check_name=ValidationCheckType.TAKE_PROFIT_ORDER,
                        passed=False,
                        message=f"ロングのTP{i+1}がエントリー価格以下",
                        severity=ValidationSeverity.CRITICAL
                    )
            else:  # SHORT
                if tp_price >= entry_price:
                    return ValidationCheck(
                        check_name=ValidationCheckType.TAKE_PROFIT_ORDER,
                        passed=False,
                        message=f"ショートのTP{i+1}がエントリー価格以上",
                        severity=ValidationSeverity.CRITICAL
                    )
            
            # 前のTPとの順序チェック
            if previous_tp is not None:
                if signal.direction == SignalDirection.LONG:
                    if tp_price <= previous_tp:
                        return ValidationCheck(
                            check_name=ValidationCheckType.TAKE_PROFIT_ORDER,
                            passed=False,
                            message=f"TP{i+1}がTP{i}より手前にある",
                            severity=ValidationSeverity.CRITICAL
                        )
                else:  # SHORT
                    if tp_price >= previous_tp:
                        return ValidationCheck(
                            check_name=ValidationCheckType.TAKE_PROFIT_ORDER,
                            passed=False,
                            message=f"TP{i+1}がTP{i}より手前にある",
                            severity=ValidationSeverity.CRITICAL
                        )
            
            previous_tp = tp_price
        
        # 決済割合の合計チェック
        total_percentage = sum(tp.percentage for tp in signal.take_profits if tp.percentage)
        if abs(total_percentage - 100.0) > 0.01:
            return ValidationCheck(
                check_name=ValidationCheckType.TAKE_PROFIT_ORDER,
                passed=False,
                message=f"TP決済割合の合計が100%ではない: {total_percentage:.1f}%",
                severity=ValidationSeverity.WARNING
            )
        
        return ValidationCheck(
            check_name=ValidationCheckType.TAKE_PROFIT_ORDER,
            passed=True,
            message="テイクプロフィットは順序通りに並んでいる"
        )
    
    def _check_risk_reward_ratio(self, signal: EntrySignal) -> ValidationCheck:
        """リスクリワード比が最小要件を満たすか検証"""
        
        if not signal.risk_reward:
            return ValidationCheck(
                check_name=ValidationCheckType.RISK_REWARD_RATIO,
                passed=False,
                message="リスクリワード情報が設定されていません",
                severity=ValidationSeverity.CRITICAL
            )
        
        # 加重平均RR比をチェック
        rr_ratio = signal.risk_reward.weighted_rr_ratio
        
        if rr_ratio < self.min_rr_ratio:
            # 個別のTPのRR比も確認
            tp_details = []
            if signal.risk_reward.tp1_rr_ratio:
                tp_details.append(f"TP1: {signal.risk_reward.tp1_rr_ratio:.2f}")
            if signal.risk_reward.tp2_rr_ratio:
                tp_details.append(f"TP2: {signal.risk_reward.tp2_rr_ratio:.2f}")
            if signal.risk_reward.tp3_rr_ratio:
                tp_details.append(f"TP3: {signal.risk_reward.tp3_rr_ratio:.2f}")
            
            return ValidationCheck(
                check_name=ValidationCheckType.RISK_REWARD_RATIO,
                passed=False,
                message=f"RR比が最小要件未満（{rr_ratio:.2f} < {self.min_rr_ratio}）",
                severity=ValidationSeverity.CRITICAL,
                details={
                    "weighted_rr": rr_ratio,
                    "required_rr": self.min_rr_ratio,
                    "individual_rr": tp_details
                }
            )
        
        # 警告レベルのチェック（推奨値）
        recommended_rr = 2.0
        if rr_ratio < recommended_rr:
            return ValidationCheck(
                check_name=ValidationCheckType.RISK_REWARD_RATIO,
                passed=True,
                message=f"RR比は最小要件を満たすが推奨値未満（{rr_ratio:.2f} < {recommended_rr}）",
                severity=ValidationSeverity.WARNING
            )
        
        return ValidationCheck(
            check_name=ValidationCheckType.RISK_REWARD_RATIO,
            passed=True,
            message=f"RR比は適切（{rr_ratio:.2f} >= {self.min_rr_ratio}）"
        )