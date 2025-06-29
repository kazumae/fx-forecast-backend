from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
from src.domain.models.entry_signal import EntrySignal, SignalDirection, OrderType
from src.domain.models.signal_validation import (
    ValidationCheck, ValidationCheckType, ValidationSeverity
)


class DataIntegrityValidator:
    """データ整合性検証器"""
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.max_future_minutes = self.config.get("max_future_minutes", 5)
        self.max_past_minutes = self.config.get("max_past_minutes", 60)
        self.max_price = self.config.get("max_price", Decimal("100000"))
        self.min_price = self.config.get("min_price", Decimal("0.00001"))
    
    def validate(self, signal: EntrySignal) -> List[ValidationCheck]:
        """データ整合性を検証"""
        checks = []
        
        # 必須フィールドチェック
        checks.append(self._check_required_fields(signal))
        
        # データ型チェック
        checks.append(self._check_data_types(signal))
        
        # 価格の妥当性チェック
        checks.append(self._check_price_sanity(signal))
        
        # タイムスタンプの妥当性チェック
        checks.append(self._check_timestamp_validity(signal))
        
        return checks
    
    def _check_required_fields(self, signal: EntrySignal) -> ValidationCheck:
        """必須フィールドの存在を確認"""
        required_fields = [
            ("id", signal.id),
            ("symbol", signal.symbol),
            ("timestamp", signal.timestamp),
            ("direction", signal.direction),
            ("entry", signal.entry),
            ("stop_loss", signal.stop_loss),
            ("take_profits", signal.take_profits),
            ("risk_reward", signal.risk_reward),
            ("metadata", signal.metadata),
            ("execution", signal.execution)
        ]
        
        missing_fields = []
        for field_name, field_value in required_fields:
            if field_value is None:
                missing_fields.append(field_name)
        
        # エントリー情報の詳細チェック
        if signal.entry:
            entry_fields = [
                ("price", signal.entry.price),
                ("order_type", signal.entry.order_type),
                ("valid_until", signal.entry.valid_until)
            ]
            for field_name, field_value in entry_fields:
                if field_value is None:
                    missing_fields.append(f"entry.{field_name}")
        
        # ストップロス情報の詳細チェック
        if signal.stop_loss:
            sl_fields = [
                ("price", signal.stop_loss.price),
                ("distance_pips", signal.stop_loss.distance_pips)
            ]
            for field_name, field_value in sl_fields:
                if field_value is None:
                    missing_fields.append(f"stop_loss.{field_name}")
        
        # テイクプロフィット情報のチェック
        if signal.take_profits and len(signal.take_profits) > 0:
            for i, tp in enumerate(signal.take_profits):
                if tp.price is None:
                    missing_fields.append(f"take_profits[{i}].price")
                if tp.percentage is None:
                    missing_fields.append(f"take_profits[{i}].percentage")
        else:
            missing_fields.append("take_profits (empty)")
        
        if missing_fields:
            return ValidationCheck(
                check_name=ValidationCheckType.REQUIRED_FIELDS,
                passed=False,
                message=f"必須フィールドが欠落: {', '.join(missing_fields)}",
                severity=ValidationSeverity.CRITICAL
            )
        
        return ValidationCheck(
            check_name=ValidationCheckType.REQUIRED_FIELDS,
            passed=True,
            message="すべての必須フィールドが存在"
        )
    
    def _check_data_types(self, signal: EntrySignal) -> ValidationCheck:
        """データ型の正確性を検証"""
        type_errors = []
        
        # 基本型チェック
        if not isinstance(signal.id, str):
            type_errors.append("id must be string")
        
        if not isinstance(signal.symbol, str):
            type_errors.append("symbol must be string")
        
        if not isinstance(signal.timestamp, datetime):
            type_errors.append("timestamp must be datetime")
        
        if not isinstance(signal.direction, SignalDirection):
            type_errors.append("direction must be SignalDirection enum")
        
        # 価格型チェック
        if signal.entry and signal.entry.price:
            if not isinstance(signal.entry.price, (Decimal, int, float)):
                type_errors.append("entry.price must be numeric")
        
        if signal.stop_loss and signal.stop_loss.price:
            if not isinstance(signal.stop_loss.price, (Decimal, int, float)):
                type_errors.append("stop_loss.price must be numeric")
        
        # TP価格チェック
        if signal.take_profits:
            for i, tp in enumerate(signal.take_profits):
                if tp.price and not isinstance(tp.price, (Decimal, int, float)):
                    type_errors.append(f"take_profits[{i}].price must be numeric")
        
        if type_errors:
            return ValidationCheck(
                check_name=ValidationCheckType.DATA_TYPES,
                passed=False,
                message=f"データ型エラー: {'; '.join(type_errors)}",
                severity=ValidationSeverity.CRITICAL
            )
        
        return ValidationCheck(
            check_name=ValidationCheckType.DATA_TYPES,
            passed=True,
            message="すべてのデータ型が正しい"
        )
    
    def _check_price_sanity(self, signal: EntrySignal) -> ValidationCheck:
        """価格の妥当性を確認"""
        price_issues = []
        
        # エントリー価格チェック
        if signal.entry and signal.entry.price:
            entry_price = Decimal(str(signal.entry.price))
            if entry_price <= self.min_price:
                price_issues.append(f"エントリー価格が低すぎる: {entry_price}")
            elif entry_price >= self.max_price:
                price_issues.append(f"エントリー価格が高すぎる: {entry_price}")
        
        # SL価格チェック
        if signal.stop_loss and signal.stop_loss.price:
            sl_price = Decimal(str(signal.stop_loss.price))
            if sl_price <= self.min_price:
                price_issues.append(f"SL価格が低すぎる: {sl_price}")
            elif sl_price >= self.max_price:
                price_issues.append(f"SL価格が高すぎる: {sl_price}")
        
        # TP価格チェック
        if signal.take_profits:
            for i, tp in enumerate(signal.take_profits):
                if tp.price:
                    tp_price = Decimal(str(tp.price))
                    if tp_price <= self.min_price:
                        price_issues.append(f"TP{i+1}価格が低すぎる: {tp_price}")
                    elif tp_price >= self.max_price:
                        price_issues.append(f"TP{i+1}価格が高すぎる: {tp_price}")
        
        # 価格の相対関係チェック
        if signal.entry and signal.stop_loss and signal.entry.price and signal.stop_loss.price:
            entry_price = Decimal(str(signal.entry.price))
            sl_price = Decimal(str(signal.stop_loss.price))
            
            # ロング/ショートで価格関係が逆転していないか
            if signal.direction == SignalDirection.LONG:
                if sl_price >= entry_price:
                    price_issues.append("ロングポジションでSLがエントリー以上")
            else:  # SHORT
                if sl_price <= entry_price:
                    price_issues.append("ショートポジションでSLがエントリー以下")
        
        if price_issues:
            return ValidationCheck(
                check_name=ValidationCheckType.PRICE_SANITY,
                passed=False,
                message=f"価格の妥当性エラー: {'; '.join(price_issues)}",
                severity=ValidationSeverity.CRITICAL
            )
        
        return ValidationCheck(
            check_name=ValidationCheckType.PRICE_SANITY,
            passed=True,
            message="価格は妥当な範囲内"
        )
    
    def _check_timestamp_validity(self, signal: EntrySignal) -> ValidationCheck:
        """タイムスタンプの妥当性を検証"""
        current_time = datetime.now(timezone.utc)
        
        # タイムスタンプがタイムゾーン情報を持っているか確認
        if signal.timestamp.tzinfo is None:
            return ValidationCheck(
                check_name=ValidationCheckType.TIMESTAMP_VALIDITY,
                passed=False,
                message="タイムスタンプにタイムゾーン情報がありません",
                severity=ValidationSeverity.WARNING
            )
        
        # 未来の時刻チェック
        max_future = current_time + timedelta(minutes=self.max_future_minutes)
        if signal.timestamp > max_future:
            time_diff = (signal.timestamp - current_time).total_seconds() / 60
            return ValidationCheck(
                check_name=ValidationCheckType.TIMESTAMP_VALIDITY,
                passed=False,
                message=f"タイムスタンプが未来すぎる: {time_diff:.1f}分後",
                severity=ValidationSeverity.CRITICAL
            )
        
        # 過去の時刻チェック
        max_past = current_time - timedelta(minutes=self.max_past_minutes)
        if signal.timestamp < max_past:
            time_diff = (current_time - signal.timestamp).total_seconds() / 60
            return ValidationCheck(
                check_name=ValidationCheckType.TIMESTAMP_VALIDITY,
                passed=False,
                message=f"タイムスタンプが古すぎる: {time_diff:.1f}分前",
                severity=ValidationSeverity.WARNING
            )
        
        # 有効期限チェック
        if signal.entry and signal.entry.valid_until:
            if signal.entry.valid_until < signal.timestamp:
                return ValidationCheck(
                    check_name=ValidationCheckType.TIMESTAMP_VALIDITY,
                    passed=False,
                    message="有効期限がシグナル生成時刻より前",
                    severity=ValidationSeverity.CRITICAL
                )
            
            # 有効期限が近すぎないか
            min_validity_minutes = 5
            min_valid_until = signal.timestamp + timedelta(minutes=min_validity_minutes)
            if signal.entry.valid_until < min_valid_until:
                return ValidationCheck(
                    check_name=ValidationCheckType.TIMESTAMP_VALIDITY,
                    passed=False,
                    message=f"有効期限が短すぎる: {min_validity_minutes}分未満",
                    severity=ValidationSeverity.WARNING
                )
        
        return ValidationCheck(
            check_name=ValidationCheckType.TIMESTAMP_VALIDITY,
            passed=True,
            message="タイムスタンプは妥当"
        )