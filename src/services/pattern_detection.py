"""パターン検出サービス（簡易版）"""
from typing import List, Optional
from src.domain.models.market_data import Candlestick
from src.domain.models.pattern import PatternSignal


class PatternDetectionService:
    """パターン検出サービス"""
    
    async def detect_all_patterns(self, candles: List[Candlestick]) -> List[PatternSignal]:
        """すべてのパターンを検出"""
        # 簡易実装：常に空のリストを返す
        # 実際の実装では各パターン検出器を呼び出す
        return []