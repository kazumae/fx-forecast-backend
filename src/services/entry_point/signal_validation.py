"""シグナル検証サービス（簡易版）"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from src.domain.models.entry_signal import EntrySignal


@dataclass
class ValidationResult:
    """検証結果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metadata: Optional[Dict[str, Any]] = None


class SignalValidationService:
    """シグナル検証サービス"""
    
    async def validate_signal(
        self,
        signal: EntrySignal,
        context: Dict[str, Any]
    ) -> ValidationResult:
        """シグナルを検証"""
        # 簡易実装：常に有効
        return ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[]
        )