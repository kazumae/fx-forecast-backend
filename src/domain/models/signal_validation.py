from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class ValidationCheckType(Enum):
    """検証チェックタイプ"""
    # データ整合性
    REQUIRED_FIELDS = "required_fields"
    DATA_TYPES = "data_types"
    PRICE_SANITY = "price_sanity"
    TIMESTAMP_VALIDITY = "timestamp_validity"
    
    # ビジネスロジック
    ENTRY_PRICE_RANGE = "entry_price_range"
    STOP_LOSS_POSITION = "stop_loss_position"
    TAKE_PROFIT_ORDER = "take_profit_order"
    RISK_REWARD_RATIO = "risk_reward_ratio"
    
    # 市場条件
    MARKET_HOURS = "market_hours"
    SPREAD_CHECK = "spread_check"
    LIQUIDITY_CHECK = "liquidity_check"
    NEWS_TIME_CHECK = "news_time_check"
    
    # ポジション管理
    DUPLICATE_ENTRY = "duplicate_entry"
    POSITION_CONFLICT = "position_conflict"
    MAX_POSITIONS = "max_positions"
    MARGIN_REQUIREMENT = "margin_requirement"


class ValidationSeverity(Enum):
    """検証エラーの重要度"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ValidationDecision(Enum):
    """最終的な検証判定"""
    ACCEPT = "ACCEPT"
    ACCEPT_WITH_WARNINGS = "ACCEPT_WITH_WARNINGS"
    REJECT = "REJECT"
    REQUIRES_ADJUSTMENT = "REQUIRES_ADJUSTMENT"


@dataclass
class ValidationCheck:
    """個別の検証チェック結果"""
    check_name: ValidationCheckType
    passed: bool
    message: str
    severity: Optional[ValidationSeverity] = None
    details: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        # 失敗した場合は重要度を設定
        if not self.passed and self.severity is None:
            self.severity = ValidationSeverity.CRITICAL


@dataclass
class CorrectiveAction:
    """修正アクション"""
    issue: ValidationCheckType
    action: str
    original_value: Any
    suggested_value: Any
    impact: Optional[str] = None


@dataclass
class ValidationResult:
    """検証結果の総合情報"""
    is_valid: bool
    validation_time: datetime
    checks_performed: int
    checks_passed: int
    checks_failed: int
    validation_id: str
    signal_id: str
    
    def get_pass_rate(self) -> float:
        """合格率を計算"""
        if self.checks_performed == 0:
            return 0.0
        return (self.checks_passed / self.checks_performed) * 100


@dataclass
class ValidationReport:
    """検証レポート"""
    validation_result: ValidationResult
    validation_details: List[ValidationCheck]
    corrective_actions: List[CorrectiveAction]
    final_decision: ValidationDecision
    rejection_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_failed_critical_checks(self) -> List[ValidationCheck]:
        """重要な失敗チェックを取得"""
        return [
            check for check in self.validation_details
            if not check.passed and check.severity == ValidationSeverity.CRITICAL
        ]
    
    def get_warnings(self) -> List[ValidationCheck]:
        """警告レベルのチェックを取得"""
        return [
            check for check in self.validation_details
            if not check.passed and check.severity == ValidationSeverity.WARNING
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "validation_result": {
                "is_valid": self.validation_result.is_valid,
                "validation_time": self.validation_result.validation_time.isoformat(),
                "checks_performed": self.validation_result.checks_performed,
                "checks_passed": self.validation_result.checks_passed,
                "checks_failed": self.validation_result.checks_failed,
                "pass_rate": self.validation_result.get_pass_rate()
            },
            "validation_details": [
                {
                    "check_name": check.check_name.value,
                    "passed": check.passed,
                    "message": check.message,
                    "severity": check.severity.value if check.severity else None,
                    "details": check.details
                }
                for check in self.validation_details
            ],
            "corrective_actions": [
                {
                    "issue": action.issue.value,
                    "action": action.action,
                    "original_value": str(action.original_value),
                    "suggested_value": str(action.suggested_value),
                    "impact": action.impact
                }
                for action in self.corrective_actions
            ],
            "final_decision": self.final_decision.value,
            "rejection_reason": self.rejection_reason,
            "warnings": self.warnings
        }


@dataclass
class MarketConditions:
    """市場条件情報"""
    is_market_open: bool
    current_spread: float
    average_spread: float
    liquidity_score: float  # 0-100
    upcoming_news: List[Dict[str, Any]] = field(default_factory=list)
    market_session: str = "unknown"
    volatility_level: str = "normal"


@dataclass
class AccountStatus:
    """アカウント状態"""
    balance: float
    available_margin: float
    used_margin: float
    open_positions: int
    max_positions: int
    margin_level: float  # パーセンテージ
    
    def has_sufficient_margin(self, required_margin: float) -> bool:
        """必要証拠金が十分か確認"""
        return self.available_margin >= required_margin


@dataclass
class ValidationConfig:
    """検証設定"""
    # 価格範囲
    max_entry_distance_pips: float = 5.0
    min_sl_pips: float = 10.0
    max_sl_pips: float = 50.0
    min_rr_ratio: float = 1.5
    
    # スプレッド制限
    max_spread_multiplier: float = 3.0  # 平均スプレッドの倍数
    max_absolute_spread: float = 5.0  # 絶対最大スプレッド（pips）
    
    # 流動性
    min_liquidity_score: float = 30.0
    
    # ニュース
    news_buffer_minutes: int = 30
    
    # ポジション管理
    allow_hedging: bool = False
    max_positions_per_symbol: int = 1
    min_margin_level: float = 100.0  # パーセンテージ
    
    # 検証の厳格さ
    strict_mode: bool = False