"""エントリー評価サービス（簡易版）"""
from typing import List, Dict, Any
from src.domain.models.pattern import PatternSignal


class EntryEvaluationService:
    """エントリー評価サービス"""
    
    async def evaluate_entries(
        self,
        patterns: List[PatternSignal],
        zones: List[Any],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """エントリーポイントを評価"""
        # 簡易実装：パターンをそのまま返す
        return [{"pattern": p, "score": 80.0} for p in patterns]