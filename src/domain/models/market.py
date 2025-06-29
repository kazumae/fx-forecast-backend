"""
Market context domain models
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from src.models.candlestick import CandlestickData
from src.models.zone import Zone


@dataclass
class Indicators:
    """Technical indicators at a point in time"""
    ema20: Decimal
    ema75: Decimal
    ema200: Decimal
    atr14: Decimal
    
    @property
    def ema_alignment(self) -> str:
        """Check EMA alignment (bullish/bearish/mixed)"""
        if self.ema20 > self.ema75 > self.ema200:
            return "bullish"
        elif self.ema20 < self.ema75 < self.ema200:
            return "bearish"
        else:
            return "mixed"


@dataclass
class MarketContext:
    """Complete market context for pattern detection"""
    symbol: str
    timestamp: datetime
    current_candle: CandlestickData
    recent_candles: List[CandlestickData]  # Last N candles
    indicators: Indicators
    nearby_zones: List[Zone]  # Zones within reasonable distance
    
    @property
    def current_price(self) -> Decimal:
        """Get current price (close of current candle)"""
        return self.current_candle.close_price
    
    def get_candles_range(self, count: int) -> List[CandlestickData]:
        """Get last N candles including current"""
        all_candles = self.recent_candles + [self.current_candle]
        return all_candles[-count:] if len(all_candles) >= count else all_candles