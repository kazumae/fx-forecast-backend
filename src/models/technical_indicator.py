"""
技術指標データモデル
移動平均線等の技術指標データを格納
"""

from sqlalchemy import Column, TEXT, DECIMAL, JSON, TIMESTAMP, func
from .base import Base


class TechnicalIndicator(Base):
    __tablename__ = 'technical_indicators'
    
    symbol = Column(TEXT, nullable=False, primary_key=True)
    timeframe = Column(TEXT, nullable=False, primary_key=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, primary_key=True)
    indicator_type = Column(TEXT, nullable=False, primary_key=True)
    value = Column(DECIMAL(12, 6), nullable=False)
    extra_metadata = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<TechnicalIndicator(symbol='{self.symbol}', timeframe='{self.timeframe}', type='{self.indicator_type}', value={self.value})>"
    
    def to_dict(self):
        """辞書形式に変換"""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'indicator_type': self.indicator_type,
            'value': float(self.value) if self.value else None,
            'metadata': self.extra_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create_sma(cls, symbol: str, timeframe: str, timestamp, period: int, value: float):
        """SMA指標インスタンス作成"""
        return cls(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            indicator_type=f'sma_{period}',
            value=value,
            extra_metadata={'period': period, 'type': 'simple_moving_average'}
        )
    
    @classmethod
    def create_ema(cls, symbol: str, timeframe: str, timestamp, period: int, value: float):
        """EMA指標インスタンス作成"""
        return cls(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            indicator_type=f'ema_{period}',
            value=value,
            extra_metadata={'period': period, 'type': 'exponential_moving_average'}
        )
    
    @classmethod
    def create_custom(cls, symbol: str, timeframe: str, timestamp, indicator_type: str, 
                     value: float, metadata: dict = None):
        """カスタム指標インスタンス作成"""
        return cls(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            indicator_type=indicator_type,
            value=value,
            metadata=metadata or {}
        )