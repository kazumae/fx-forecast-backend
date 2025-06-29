from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from src.domain.models.entry_signal import EntrySignal, SignalValidationResult


class SignalValidator:
    """シグナル検証器"""
    
    def __init__(self, config: Optional[Dict[str, any]] = None):
        self.config = config or {}
        # 検証ルールの設定
        self.min_rr_ratio = self.config.get("min_rr_ratio", 1.0)
        self.max_risk_pips = self.config.get("max_risk_pips", 50.0)
        self.min_reward_pips = self.config.get("min_reward_pips", 5.0)
        self.max_spread_pips = self.config.get("max_spread_pips", 5.0)
    
    def validate_signal(
        self, 
        signal: EntrySignal,
        market_data: Optional[Dict[str, any]] = None
    ) -> SignalValidationResult:
        """シグナルの完全性と妥当性を検証"""
        
        errors = []
        warnings = []
        checks_passed = {}
        
        # 必須項目チェック
        mandatory_check = self._check_mandatory_fields(signal)
        checks_passed["mandatory_fields"] = mandatory_check["passed"]
        errors.extend(mandatory_check["errors"])
        
        # 価格の妥当性チェック
        price_check = self._check_price_validity(signal, market_data)
        checks_passed["price_validity"] = price_check["passed"]
        errors.extend(price_check["errors"])
        warnings.extend(price_check["warnings"])
        
        # リスクリワード比チェック
        rr_check = self._check_risk_reward(signal)
        checks_passed["risk_reward"] = rr_check["passed"]
        errors.extend(rr_check["errors"])
        warnings.extend(rr_check["warnings"])
        
        # 時間的整合性チェック
        time_check = self._check_time_consistency(signal)
        checks_passed["time_consistency"] = time_check["passed"]
        errors.extend(time_check["errors"])
        warnings.extend(time_check["warnings"])
        
        # 実行可能性チェック
        execution_check = self._check_execution_feasibility(signal, market_data)
        checks_passed["execution_feasibility"] = execution_check["passed"]
        errors.extend(execution_check["errors"])
        warnings.extend(execution_check["warnings"])
        
        # 全体の妥当性
        is_valid = len(errors) == 0
        
        return SignalValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            checks_passed=checks_passed
        )
    
    def _check_mandatory_fields(self, signal: EntrySignal) -> Dict[str, any]:
        """必須項目の存在チェック"""
        
        errors = []
        
        # 基本情報
        if not signal.id:
            errors.append("Signal ID is missing")
        if not signal.symbol:
            errors.append("Symbol is missing")
        if not signal.timestamp:
            errors.append("Timestamp is missing")
        
        # エントリー情報
        if not signal.entry or not signal.entry.price:
            errors.append("Entry price is missing")
        if not signal.direction:
            errors.append("Direction is missing")
        
        # ストップロス
        if not signal.stop_loss or not signal.stop_loss.price:
            errors.append("Stop loss is missing")
        
        # テイクプロフィット
        if not signal.take_profits or len(signal.take_profits) == 0:
            errors.append("Take profit levels are missing")
        
        # メタデータ
        if not signal.metadata:
            errors.append("Metadata is missing")
        elif not signal.metadata.pattern_type:
            errors.append("Pattern type is missing")
        
        return {
            "passed": len(errors) == 0,
            "errors": errors
        }
    
    def _check_price_validity(
        self, 
        signal: EntrySignal,
        market_data: Optional[Dict[str, any]] = None
    ) -> Dict[str, any]:
        """価格の妥当性チェック"""
        
        errors = []
        warnings = []
        
        # エントリー価格が正の値か
        if signal.entry.price <= 0:
            errors.append("Entry price must be positive")
        
        # ストップロスが正の値か
        if signal.stop_loss.price <= 0:
            errors.append("Stop loss price must be positive")
        
        # テイクプロフィットが正の値か
        for i, tp in enumerate(signal.take_profits):
            if tp.price <= 0:
                errors.append(f"Take profit {i+1} price must be positive")
        
        # 方向に対する価格の整合性
        if signal.direction.value == "long":
            # ロングの場合: エントリー > ストップロス、エントリー < TP
            if signal.stop_loss.price >= signal.entry.price:
                errors.append("For long position, stop loss must be below entry price")
            
            for i, tp in enumerate(signal.take_profits):
                if tp.price <= signal.entry.price:
                    errors.append(f"For long position, TP{i+1} must be above entry price")
        else:
            # ショートの場合: エントリー < ストップロス、エントリー > TP
            if signal.stop_loss.price <= signal.entry.price:
                errors.append("For short position, stop loss must be above entry price")
            
            for i, tp in enumerate(signal.take_profits):
                if tp.price >= signal.entry.price:
                    errors.append(f"For short position, TP{i+1} must be below entry price")
        
        # 市場価格との乖離チェック
        if market_data and "current_price" in market_data:
            current_price = Decimal(str(market_data["current_price"]))
            price_diff_pips = abs(float(signal.entry.price - current_price)) * 10000
            
            if price_diff_pips > 50:
                warnings.append(f"Entry price is {price_diff_pips:.1f} pips away from current market price")
        
        # TP間の距離チェック
        if len(signal.take_profits) > 1:
            for i in range(1, len(signal.take_profits)):
                if signal.direction.value == "long":
                    if signal.take_profits[i].price <= signal.take_profits[i-1].price:
                        warnings.append(f"TP{i+1} should be higher than TP{i}")
                else:
                    if signal.take_profits[i].price >= signal.take_profits[i-1].price:
                        warnings.append(f"TP{i+1} should be lower than TP{i}")
        
        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _check_risk_reward(self, signal: EntrySignal) -> Dict[str, any]:
        """リスクリワード比のチェック"""
        
        errors = []
        warnings = []
        
        # RR比の最小値チェック
        if signal.risk_reward.ratio < self.min_rr_ratio:
            errors.append(f"Risk/Reward ratio {signal.risk_reward.ratio} is below minimum {self.min_rr_ratio}")
        
        # リスクの最大値チェック
        if signal.risk_reward.risk_pips > self.max_risk_pips:
            errors.append(f"Risk {signal.risk_reward.risk_pips} pips exceeds maximum {self.max_risk_pips} pips")
        
        # リワードの最小値チェック
        if signal.risk_reward.reward_pips < self.min_reward_pips:
            warnings.append(f"Reward {signal.risk_reward.reward_pips} pips is below recommended minimum {self.min_reward_pips} pips")
        
        # TP割合の合計チェック
        total_percentage = sum(tp.percentage for tp in signal.take_profits)
        if abs(total_percentage - 100) > 0.01:
            warnings.append(f"Total TP percentage {total_percentage}% should equal 100%")
        
        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _check_time_consistency(self, signal: EntrySignal) -> Dict[str, any]:
        """時間的整合性のチェック"""
        
        errors = []
        warnings = []
        now = datetime.now()
        
        # タイムスタンプが未来でないか
        if signal.timestamp > now:
            errors.append("Signal timestamp cannot be in the future")
        
        # 作成時刻の妥当性
        if signal.created_at and signal.created_at > now:
            errors.append("Created timestamp cannot be in the future")
        
        # 有効期限の妥当性
        if signal.entry.valid_until:
            if signal.entry.valid_until < now:
                errors.append("Order has already expired")
            elif signal.entry.valid_until < signal.timestamp:
                errors.append("Valid until time cannot be before signal timestamp")
            
            # 有効期限が長すぎないか
            validity_duration = (signal.entry.valid_until - now).total_seconds() / 60
            if validity_duration > 60:
                warnings.append(f"Order validity of {validity_duration:.0f} minutes seems too long")
        
        # 期限切れ時刻の妥当性
        if signal.expires_at:
            if signal.expires_at < signal.timestamp:
                errors.append("Expiration time cannot be before signal timestamp")
            if signal.expires_at < now:
                warnings.append("Signal has already expired")
        
        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _check_execution_feasibility(
        self, 
        signal: EntrySignal,
        market_data: Optional[Dict[str, any]] = None
    ) -> Dict[str, any]:
        """実行可能性のチェック"""
        
        errors = []
        warnings = []
        
        # 推奨ロットサイズの妥当性
        if signal.execution.recommended_size <= 0:
            errors.append("Recommended size must be positive")
        elif signal.execution.recommended_size > 10:
            warnings.append(f"Recommended size {signal.execution.recommended_size} lots seems too large")
        
        # 最大リスク金額の妥当性
        if signal.execution.max_risk_amount <= 0:
            errors.append("Max risk amount must be positive")
        elif signal.execution.max_risk_amount > 1000:
            warnings.append(f"Max risk amount ${signal.execution.max_risk_amount} seems too large")
        
        # スリッページ許容値の妥当性
        if signal.entry.slippage_tolerance < 0:
            errors.append("Slippage tolerance cannot be negative")
        elif signal.entry.slippage_tolerance > 10:
            warnings.append(f"Slippage tolerance {signal.entry.slippage_tolerance} pips seems too large")
        
        # 市場状態のチェック
        if market_data:
            # スプレッドチェック
            if "spread" in market_data:
                spread_pips = market_data["spread"]
                if spread_pips > self.max_spread_pips:
                    warnings.append(f"Current spread {spread_pips} pips exceeds recommended maximum {self.max_spread_pips} pips")
            
            # 市場の開場状態
            if "is_market_open" in market_data and not market_data["is_market_open"]:
                errors.append("Market is currently closed")
            
            # 流動性チェック
            if "liquidity" in market_data and market_data["liquidity"] == "low":
                warnings.append("Low market liquidity detected")
        
        # 優先度の妥当性
        if signal.metadata.priority < 1 or signal.metadata.priority > 10:
            warnings.append(f"Priority {signal.metadata.priority} should be between 1 and 10")
        
        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }