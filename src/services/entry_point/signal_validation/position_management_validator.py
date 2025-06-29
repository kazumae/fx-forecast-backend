from decimal import Decimal
from typing import List, Optional, Dict, Any
from src.domain.models.entry_signal import EntrySignal, SignalDirection
from src.domain.models.signal_validation import (
    ValidationCheck, ValidationCheckType, ValidationSeverity,
    AccountStatus
)


class PositionManagementValidator:
    """ポジション管理検証器"""
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.allow_hedging = self.config.get("allow_hedging", False)
        self.max_positions_per_symbol = self.config.get("max_positions_per_symbol", 1)
        self.max_total_positions = self.config.get("max_total_positions", 10)
        self.min_margin_level = self.config.get("min_margin_level", 100.0)
        self.position_size_limits = self.config.get("position_size_limits", {
            "min_lots": 0.01,
            "max_lots": 10.0
        })
    
    def validate(
        self,
        signal: EntrySignal,
        account_status: AccountStatus,
        existing_positions: List[Dict[str, Any]],
        required_margin: float
    ) -> List[ValidationCheck]:
        """ポジション管理ルールを検証"""
        checks = []
        
        # 重複エントリーチェック
        checks.append(self._check_duplicate_entry(signal, existing_positions))
        
        # ポジション競合チェック
        checks.append(self._check_position_conflict(signal, existing_positions))
        
        # 最大ポジション数チェック
        checks.append(self._check_max_positions(signal, account_status, existing_positions))
        
        # 証拠金チェック
        checks.append(self._check_margin_requirement(signal, account_status, required_margin))
        
        return checks
    
    def _check_duplicate_entry(
        self,
        signal: EntrySignal,
        existing_positions: List[Dict[str, Any]]
    ) -> ValidationCheck:
        """同一シンボルでの重複エントリーを検出"""
        
        # 同じシンボルの既存ポジションを探す
        same_symbol_positions = [
            pos for pos in existing_positions
            if pos.get("symbol") == signal.symbol
        ]
        
        if not same_symbol_positions:
            return ValidationCheck(
                check_name=ValidationCheckType.DUPLICATE_ENTRY,
                passed=True,
                message="同一シンボルの既存ポジションなし"
            )
        
        # 同じ方向のポジションをチェック
        same_direction_positions = [
            pos for pos in same_symbol_positions
            if pos.get("direction") == signal.direction.value
        ]
        
        if same_direction_positions:
            # エントリー価格の近さをチェック
            for pos in same_direction_positions:
                existing_entry = Decimal(str(pos.get("entry_price", 0)))
                new_entry = Decimal(str(signal.entry.price))
                price_diff_pips = abs(float(existing_entry - new_entry)) * 10000
                
                # 5pips以内は重複とみなす
                if price_diff_pips < 5.0:
                    return ValidationCheck(
                        check_name=ValidationCheckType.DUPLICATE_ENTRY,
                        passed=False,
                        message=f"既存ポジションと重複: {signal.symbol} {signal.direction.value} @ {existing_entry}",
                        severity=ValidationSeverity.CRITICAL,
                        details={
                            "existing_position_id": pos.get("id"),
                            "existing_entry": float(existing_entry),
                            "new_entry": float(new_entry),
                            "price_diff_pips": price_diff_pips
                        }
                    )
        
        # 既存ポジション数をチェック
        if len(same_symbol_positions) >= self.max_positions_per_symbol:
            return ValidationCheck(
                check_name=ValidationCheckType.DUPLICATE_ENTRY,
                passed=False,
                message=f"{signal.symbol}の最大ポジション数に達しています（{len(same_symbol_positions)}/{self.max_positions_per_symbol}）",
                severity=ValidationSeverity.WARNING
            )
        
        return ValidationCheck(
            check_name=ValidationCheckType.DUPLICATE_ENTRY,
            passed=True,
            message=f"重複なし（{signal.symbol}の既存ポジション: {len(same_symbol_positions)}）"
        )
    
    def _check_position_conflict(
        self,
        signal: EntrySignal,
        existing_positions: List[Dict[str, Any]]
    ) -> ValidationCheck:
        """逆方向のポジションとの競合を確認"""
        
        # ヘッジングが許可されている場合はスキップ
        if self.allow_hedging:
            return ValidationCheck(
                check_name=ValidationCheckType.POSITION_CONFLICT,
                passed=True,
                message="ヘッジング許可（両建て可能）"
            )
        
        # 同じシンボルの逆方向ポジションを探す
        opposite_direction = (
            SignalDirection.SHORT.value
            if signal.direction == SignalDirection.LONG
            else SignalDirection.LONG.value
        )
        
        conflicting_positions = [
            pos for pos in existing_positions
            if pos.get("symbol") == signal.symbol
            and pos.get("direction") == opposite_direction
        ]
        
        if conflicting_positions:
            total_lots = sum(pos.get("lots", 0) for pos in conflicting_positions)
            return ValidationCheck(
                check_name=ValidationCheckType.POSITION_CONFLICT,
                passed=False,
                message=f"逆方向のポジションが存在: {signal.symbol} {opposite_direction} ({total_lots:.2f}ロット)",
                severity=ValidationSeverity.CRITICAL,
                details={
                    "conflicting_positions": len(conflicting_positions),
                    "total_opposite_lots": total_lots
                }
            )
        
        # 相関の高い通貨ペアのチェック（オプション）
        correlated_conflicts = self._check_correlated_conflicts(signal, existing_positions)
        if correlated_conflicts:
            return ValidationCheck(
                check_name=ValidationCheckType.POSITION_CONFLICT,
                passed=True,
                message=f"相関通貨ペアに逆ポジションあり: {', '.join(correlated_conflicts)}",
                severity=ValidationSeverity.WARNING
            )
        
        return ValidationCheck(
            check_name=ValidationCheckType.POSITION_CONFLICT,
            passed=True,
            message="ポジション競合なし"
        )
    
    def _check_max_positions(
        self,
        signal: EntrySignal,
        account_status: AccountStatus,
        existing_positions: List[Dict[str, Any]]
    ) -> ValidationCheck:
        """最大ポジション数の制限を確認"""
        
        current_positions = account_status.open_positions
        max_positions = account_status.max_positions
        
        # 総ポジション数チェック
        if current_positions >= max_positions:
            return ValidationCheck(
                check_name=ValidationCheckType.MAX_POSITIONS,
                passed=False,
                message=f"最大ポジション数に達しています（{current_positions}/{max_positions}）",
                severity=ValidationSeverity.CRITICAL
            )
        
        # 設定による追加制限
        if current_positions >= self.max_total_positions:
            return ValidationCheck(
                check_name=ValidationCheckType.MAX_POSITIONS,
                passed=False,
                message=f"システム設定の最大ポジション数に達しています（{current_positions}/{self.max_total_positions}）",
                severity=ValidationSeverity.CRITICAL
            )
        
        # 警告レベル（80%以上）
        usage_percentage = (current_positions / max_positions) * 100
        if usage_percentage >= 80:
            return ValidationCheck(
                check_name=ValidationCheckType.MAX_POSITIONS,
                passed=True,
                message=f"ポジション数が上限に近づいています（{current_positions}/{max_positions}, {usage_percentage:.0f}%）",
                severity=ValidationSeverity.WARNING
            )
        
        return ValidationCheck(
            check_name=ValidationCheckType.MAX_POSITIONS,
            passed=True,
            message=f"ポジション数は制限内（{current_positions}/{max_positions}）"
        )
    
    def _check_margin_requirement(
        self,
        signal: EntrySignal,
        account_status: AccountStatus,
        required_margin: float
    ) -> ValidationCheck:
        """証拠金の十分性を検証"""
        
        # 利用可能証拠金チェック
        if not account_status.has_sufficient_margin(required_margin):
            shortage = required_margin - account_status.available_margin
            return ValidationCheck(
                check_name=ValidationCheckType.MARGIN_REQUIREMENT,
                passed=False,
                message=f"証拠金不足（必要: ${required_margin:.2f}, 利用可能: ${account_status.available_margin:.2f}, 不足: ${shortage:.2f}）",
                severity=ValidationSeverity.CRITICAL,
                details={
                    "required_margin": required_margin,
                    "available_margin": account_status.available_margin,
                    "shortage": shortage
                }
            )
        
        # 証拠金維持率チェック
        # 新規ポジション後の証拠金維持率を計算
        new_used_margin = account_status.used_margin + required_margin
        new_margin_level = (account_status.balance / new_used_margin) * 100 if new_used_margin > 0 else float('inf')
        
        if new_margin_level < self.min_margin_level:
            return ValidationCheck(
                check_name=ValidationCheckType.MARGIN_REQUIREMENT,
                passed=False,
                message=f"新規ポジション後の証拠金維持率が最小値未満（{new_margin_level:.1f}% < {self.min_margin_level}%）",
                severity=ValidationSeverity.CRITICAL,
                details={
                    "current_margin_level": account_status.margin_level,
                    "new_margin_level": new_margin_level,
                    "min_required": self.min_margin_level
                }
            )
        
        # 警告レベル（150%未満）
        warning_level = 150.0
        if new_margin_level < warning_level:
            return ValidationCheck(
                check_name=ValidationCheckType.MARGIN_REQUIREMENT,
                passed=True,
                message=f"証拠金維持率が低下します（{account_status.margin_level:.1f}% → {new_margin_level:.1f}%）",
                severity=ValidationSeverity.WARNING
            )
        
        # 余裕率の計算
        margin_usage = (required_margin / account_status.available_margin) * 100
        
        return ValidationCheck(
            check_name=ValidationCheckType.MARGIN_REQUIREMENT,
            passed=True,
            message=f"証拠金は十分（必要: ${required_margin:.2f}, 利用可能: ${account_status.available_margin:.2f}, 使用率: {margin_usage:.1f}%）",
            details={
                "required_margin": required_margin,
                "available_margin": account_status.available_margin,
                "margin_usage_percentage": margin_usage,
                "new_margin_level": new_margin_level
            }
        )
    
    def _check_correlated_conflicts(
        self,
        signal: EntrySignal,
        existing_positions: List[Dict[str, Any]]
    ) -> List[str]:
        """相関の高い通貨ペアとの競合をチェック"""
        
        # 簡易的な相関チェック
        correlations = {
            "EURUSD": ["GBPUSD", "EURCAD"],
            "GBPUSD": ["EURUSD", "GBPJPY"],
            "USDJPY": ["EURJPY", "GBPJPY"],
            "AUDUSD": ["NZDUSD"],
            "XAUUSD": ["XAGUSD"]  # ゴールドと銀
        }
        
        base_symbol = signal.symbol[:6] if len(signal.symbol) >= 6 else signal.symbol
        correlated_symbols = correlations.get(base_symbol, [])
        
        conflicts = []
        opposite_direction = (
            SignalDirection.SHORT.value
            if signal.direction == SignalDirection.LONG
            else SignalDirection.LONG.value
        )
        
        for pos in existing_positions:
            pos_symbol = pos.get("symbol", "")[:6]
            if pos_symbol in correlated_symbols and pos.get("direction") == opposite_direction:
                conflicts.append(f"{pos_symbol} {opposite_direction}")
        
        return conflicts
    
    def calculate_required_margin(
        self,
        signal: EntrySignal,
        position_size_lots: float,
        leverage: int = 100
    ) -> float:
        """必要証拠金を計算"""
        
        # 簡易計算（実際はブローカーAPIを使用）
        contract_size = 100000  # 標準ロット
        if "XAU" in signal.symbol:
            contract_size = 100  # ゴールドは100オンス
        elif "JPY" in signal.symbol:
            contract_size = 100000
        
        entry_price = float(signal.entry.price)
        required_margin = (position_size_lots * contract_size * entry_price) / leverage
        
        # 通貨換算（必要に応じて）
        # ここでは簡易的にUSDベースと仮定
        
        return required_margin