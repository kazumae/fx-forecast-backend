"""シグナル生成サービス（簡易版）"""
from typing import List, Dict, Any
from src.domain.models.entry_signal import EntrySignal


class SignalGenerationService:
    """シグナル生成サービス"""
    
    async def generate_signals(
        self,
        evaluations: List[Dict[str, Any]],
        zones: List[Any],
        context: Dict[str, Any]
    ) -> List[EntrySignal]:
        """エントリーシグナルを生成"""
        # 簡易実装：空のリストを返す
        return []