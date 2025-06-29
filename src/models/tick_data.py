"""
ティックデータモデル
TraderMadeから受信する生の価格データを格納
"""

from sqlalchemy import Column, BIGINT, TEXT, DECIMAL, TIMESTAMP, func
from sqlalchemy.sql import text
from .base import Base


class TickData(Base):
    __tablename__ = 'tick_data'
    
    # Note: For TimescaleDB, we need timestamp in primary key for hypertables
    # Using composite primary key instead of id
    symbol = Column(TEXT, primary_key=True)
    timestamp = Column(TIMESTAMP(timezone=True), primary_key=True)
    bid = Column(DECIMAL(12, 6), nullable=False)
    ask = Column(DECIMAL(12, 6), nullable=False)
    # spread = Column(DECIMAL(12, 6))  # Calculated property instead
    source = Column(TEXT, default='tradermade')
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    @property
    def spread(self):
        """スプレッドを計算"""
        if self.ask is not None and self.bid is not None:
            return self.ask - self.bid
        return None
    
    def __repr__(self):
        return f"<TickData(symbol='{self.symbol}', timestamp='{self.timestamp}', bid={self.bid}, ask={self.ask})>"
    
    def to_dict(self):
        """辞書形式に変換"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'bid': float(self.bid) if self.bid else None,
            'ask': float(self.ask) if self.ask else None,
            'spread': float(self.spread) if self.spread else None,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_tradermade_data(cls, symbol: str, bid: float, ask: float, timestamp=None):
        """TraderMadeデータからインスタンス作成"""
        return cls(
            symbol=symbol,
            bid=bid,
            ask=ask,
            timestamp=timestamp or func.now(),
            source='tradermade'
        )