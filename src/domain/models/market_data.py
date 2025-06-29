"""市場データ関連のドメインモデル"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any


@dataclass
class Candlestick:
    """ローソク足データ"""
    symbol: str
    timeframe: str
    timestamp: datetime
    open: Decimal
    close: Decimal
    high: Decimal
    low: Decimal
    volume: int
    metadata: Optional[Dict[str, Any]] = None
    
    @property
    def is_bullish(self) -> bool:
        """陽線かどうか"""
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        """陰線かどうか"""
        return self.close < self.open
    
    @property
    def body_size(self) -> Decimal:
        """実体の大きさ"""
        return abs(self.close - self.open)
    
    @property
    def upper_shadow(self) -> Decimal:
        """上ヒゲの長さ"""
        return self.high - max(self.open, self.close)
    
    @property
    def lower_shadow(self) -> Decimal:
        """下ヒゲの長さ"""
        return min(self.open, self.close) - self.low
    
    @property
    def range(self) -> Decimal:
        """高値と安値の差"""
        return self.high - self.low
    
    @property
    def typical_price(self) -> Decimal:
        """典型価格"""
        return (self.high + self.low + self.close) / 3
    
    def is_inside_bar(self, previous: 'Candlestick') -> bool:
        """インサイドバーかどうか"""
        return self.high <= previous.high and self.low >= previous.low
    
    def is_outside_bar(self, previous: 'Candlestick') -> bool:
        """アウトサイドバーかどうか"""
        return self.high > previous.high and self.low < previous.low


@dataclass
class MarketSnapshot:
    """市場スナップショット"""
    timestamp: datetime
    symbol: str
    bid: Decimal
    ask: Decimal
    spread: Decimal
    volume: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @property
    def mid_price(self) -> Decimal:
        """中値"""
        return (self.bid + self.ask) / 2