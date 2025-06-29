import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from src.domain.models.entry_signal import EntrySignal
from src.domain.models.signal_validation import (
    ValidationCheck, ValidationCheckType, ValidationSeverity,
    ValidationResult, ValidationReport, ValidationDecision,
    CorrectiveAction, MarketConditions, AccountStatus, ValidationConfig
)
from .data_integrity_validator import DataIntegrityValidator
from .business_logic_validator import BusinessLogicValidator
from .market_conditions_validator import MarketConditionsValidator
from .position_management_validator import PositionManagementValidator


class SignalValidationService:
    """シグナル検証統合サービス"""
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        
        # 各検証器を初期化
        validator_config = self._create_validator_config()
        self.data_validator = DataIntegrityValidator(validator_config)
        self.business_validator = BusinessLogicValidator(validator_config)
        self.market_validator = MarketConditionsValidator(validator_config)
        self.position_validator = PositionManagementValidator(validator_config)
    
    def validate_signal(
        self,
        signal: EntrySignal,
        current_price: Decimal,
        current_spread: float,
        market_conditions: MarketConditions,
        account_status: AccountStatus,
        existing_positions: List[Dict[str, Any]],
        position_size_lots: float = 0.1
    ) -> ValidationReport:
        """シグナルを総合的に検証"""
        
        validation_start = datetime.now(timezone.utc)
        all_checks = []
        
        # 1. データ整合性チェック
        data_checks = self.data_validator.validate(signal)
        all_checks.extend(data_checks)
        
        # データ整合性で重大なエラーがある場合は早期終了
        critical_data_errors = [
            check for check in data_checks
            if not check.passed and check.severity == ValidationSeverity.CRITICAL
        ]
        if critical_data_errors and self.config.strict_mode:
            return self._create_early_rejection_report(
                signal, all_checks, validation_start,
                "データ整合性の重大なエラー"
            )
        
        # 2. ビジネスロジック検証
        business_checks = self.business_validator.validate(
            signal, current_price, current_spread
        )
        all_checks.extend(business_checks)
        
        # 3. 市場条件検証
        market_checks = self.market_validator.validate(signal, market_conditions)
        all_checks.extend(market_checks)
        
        # 4. ポジション管理検証
        # 必要証拠金を計算
        leverage = 100  # デフォルトレバレッジ
        required_margin = self.position_validator.calculate_required_margin(
            signal, position_size_lots, leverage
        )
        
        position_checks = self.position_validator.validate(
            signal, account_status, existing_positions, required_margin
        )
        all_checks.extend(position_checks)
        
        # 5. 検証結果の集計
        validation_result = self._aggregate_validation_result(
            signal, all_checks, validation_start
        )
        
        # 6. 修正アクションの生成
        corrective_actions = self._generate_corrective_actions(
            signal, all_checks, current_price
        )
        
        # 7. 最終判定
        final_decision, rejection_reason = self._make_final_decision(
            all_checks, corrective_actions
        )
        
        # 8. 警告の収集
        warnings = self._collect_warnings(all_checks)
        
        # 9. メタデータの追加
        metadata = {
            "position_size_lots": position_size_lots,
            "required_margin": required_margin,
            "leverage": leverage,
            "market_session": market_conditions.market_session,
            "volatility_level": market_conditions.volatility_level,
            "validation_duration_ms": (
                datetime.now(timezone.utc) - validation_start
            ).total_seconds() * 1000
        }
        
        return ValidationReport(
            validation_result=validation_result,
            validation_details=all_checks,
            corrective_actions=corrective_actions,
            final_decision=final_decision,
            rejection_reason=rejection_reason,
            warnings=warnings,
            metadata=metadata
        )
    
    def validate_batch(
        self,
        signals: List[EntrySignal],
        market_data: Dict[str, Any],
        account_status: AccountStatus,
        existing_positions: List[Dict[str, Any]]
    ) -> List[ValidationReport]:
        """複数のシグナルをバッチ検証"""
        
        reports = []
        
        for signal in signals:
            # 各シグナル用の市場データを取得
            symbol_data = market_data.get(signal.symbol, {})
            current_price = Decimal(str(symbol_data.get("price", signal.entry.price)))
            current_spread = symbol_data.get("spread", 2.0)
            
            market_conditions = MarketConditions(
                is_market_open=symbol_data.get("is_market_open", True),
                current_spread=current_spread,
                average_spread=symbol_data.get("average_spread", current_spread),
                liquidity_score=symbol_data.get("liquidity_score", 50.0),
                upcoming_news=symbol_data.get("upcoming_news", []),
                market_session=symbol_data.get("market_session", "unknown"),
                volatility_level=symbol_data.get("volatility_level", "normal")
            )
            
            report = self.validate_signal(
                signal=signal,
                current_price=current_price,
                current_spread=current_spread,
                market_conditions=market_conditions,
                account_status=account_status,
                existing_positions=existing_positions
            )
            
            reports.append(report)
        
        return reports
    
    def _create_validator_config(self) -> Dict[str, Any]:
        """検証器用の設定を作成"""
        return {
            # 価格範囲
            "max_entry_distance_pips": self.config.max_entry_distance_pips,
            "min_sl_pips": self.config.min_sl_pips,
            "max_sl_pips": self.config.max_sl_pips,
            "min_rr_ratio": self.config.min_rr_ratio,
            
            # スプレッド
            "max_spread_multiplier": self.config.max_spread_multiplier,
            "max_absolute_spread": self.config.max_absolute_spread,
            
            # 流動性
            "min_liquidity_score": self.config.min_liquidity_score,
            
            # ニュース
            "news_buffer_minutes": self.config.news_buffer_minutes,
            
            # ポジション管理
            "allow_hedging": self.config.allow_hedging,
            "max_positions_per_symbol": self.config.max_positions_per_symbol,
            "min_margin_level": self.config.min_margin_level
        }
    
    def _aggregate_validation_result(
        self,
        signal: EntrySignal,
        all_checks: List[ValidationCheck],
        validation_start: datetime
    ) -> ValidationResult:
        """検証結果を集計"""
        
        checks_performed = len(all_checks)
        checks_passed = sum(1 for check in all_checks if check.passed)
        checks_failed = checks_performed - checks_passed
        
        # 重大なエラーがあるかチェック
        has_critical_errors = any(
            not check.passed and check.severity == ValidationSeverity.CRITICAL
            for check in all_checks
        )
        
        return ValidationResult(
            is_valid=not has_critical_errors,
            validation_time=validation_start,
            checks_performed=checks_performed,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            validation_id=str(uuid.uuid4()),
            signal_id=signal.id
        )
    
    def _generate_corrective_actions(
        self,
        signal: EntrySignal,
        all_checks: List[ValidationCheck],
        current_price: Decimal
    ) -> List[CorrectiveAction]:
        """修正アクションを生成"""
        
        actions = []
        
        # RR比が不足している場合
        rr_check = next(
            (check for check in all_checks
             if check.check_name == ValidationCheckType.RISK_REWARD_RATIO
             and not check.passed),
            None
        )
        
        if rr_check and signal.stop_loss and signal.risk_reward:
            # SLを近づけることでRR比を改善
            current_rr = signal.risk_reward.weighted_rr_ratio
            required_rr = self.config.min_rr_ratio
            
            if current_rr > 0:
                adjustment_factor = required_rr / current_rr
                new_sl_distance = signal.stop_loss.distance_pips / adjustment_factor
                
                # 最小SL距離を維持
                if new_sl_distance >= self.config.min_sl_pips:
                    new_sl_price = self._calculate_adjusted_sl_price(
                        signal, new_sl_distance
                    )
                    
                    actions.append(CorrectiveAction(
                        issue=ValidationCheckType.RISK_REWARD_RATIO,
                        action=f"ストップロスを{new_sl_price}に調整",
                        original_value=signal.stop_loss.price,
                        suggested_value=new_sl_price,
                        impact=f"新しいRR比: {required_rr:.2f}"
                    ))
        
        # スプレッドが高い場合
        spread_check = next(
            (check for check in all_checks
             if check.check_name == ValidationCheckType.SPREAD_CHECK
             and not check.passed),
            None
        )
        
        if spread_check:
            actions.append(CorrectiveAction(
                issue=ValidationCheckType.SPREAD_CHECK,
                action="スプレッドが正常化するまで待機",
                original_value="即時実行",
                suggested_value="遅延実行",
                impact="約定価格の改善"
            ))
        
        return actions
    
    def _make_final_decision(
        self,
        all_checks: List[ValidationCheck],
        corrective_actions: List[CorrectiveAction]
    ) -> tuple[ValidationDecision, Optional[str]]:
        """最終的な検証判定を行う"""
        
        # 重大なエラーを収集
        critical_errors = [
            check for check in all_checks
            if not check.passed and check.severity == ValidationSeverity.CRITICAL
        ]
        
        # 警告を収集
        warnings = [
            check for check in all_checks
            if not check.passed and check.severity == ValidationSeverity.WARNING
        ]
        
        # 判定ロジック
        if critical_errors:
            # 修正可能なエラーかチェック
            correctable_errors = [
                error for error in critical_errors
                if any(action.issue == error.check_name for action in corrective_actions)
            ]
            
            if correctable_errors and len(correctable_errors) == len(critical_errors):
                return (
                    ValidationDecision.REQUIRES_ADJUSTMENT,
                    f"{len(corrective_actions)}個の修正が必要"
                )
            else:
                # 修正不可能なエラー
                error_messages = [error.message for error in critical_errors[:2]]
                return (
                    ValidationDecision.REJECT,
                    "; ".join(error_messages)
                )
        
        elif warnings:
            return (
                ValidationDecision.ACCEPT_WITH_WARNINGS,
                None
            )
        
        else:
            return (
                ValidationDecision.ACCEPT,
                None
            )
    
    def _collect_warnings(self, all_checks: List[ValidationCheck]) -> List[str]:
        """警告メッセージを収集"""
        
        warnings = []
        
        for check in all_checks:
            if not check.passed and check.severity == ValidationSeverity.WARNING:
                warnings.append(f"{check.check_name.value}: {check.message}")
            elif check.passed and check.severity == ValidationSeverity.WARNING:
                # 合格したが警告レベルの情報
                warnings.append(f"注意: {check.message}")
        
        return warnings
    
    def _create_early_rejection_report(
        self,
        signal: EntrySignal,
        checks_performed: List[ValidationCheck],
        validation_start: datetime,
        rejection_reason: str
    ) -> ValidationReport:
        """早期却下レポートを作成"""
        
        validation_result = ValidationResult(
            is_valid=False,
            validation_time=validation_start,
            checks_performed=len(checks_performed),
            checks_passed=sum(1 for check in checks_performed if check.passed),
            checks_failed=sum(1 for check in checks_performed if not check.passed),
            validation_id=str(uuid.uuid4()),
            signal_id=signal.id
        )
        
        return ValidationReport(
            validation_result=validation_result,
            validation_details=checks_performed,
            corrective_actions=[],
            final_decision=ValidationDecision.REJECT,
            rejection_reason=rejection_reason,
            warnings=[],
            metadata={"early_rejection": True}
        )
    
    def _calculate_adjusted_sl_price(
        self,
        signal: EntrySignal,
        new_sl_distance_pips: float
    ) -> Decimal:
        """調整後のSL価格を計算"""
        
        entry_price = signal.entry.price
        sl_adjustment = Decimal(str(new_sl_distance_pips / 10000))
        
        if signal.direction.value == "LONG":
            return entry_price - sl_adjustment
        else:
            return entry_price + sl_adjustment