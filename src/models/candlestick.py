"""
ローソク足データモデル
ティックデータから生成されるOHLCデータを格納
"""

from sqlalchemy import Column, TEXT, DECIMAL, INTEGER, TIMESTAMP, func, UniqueConstraint
from .base import Base


class CandlestickData(Base):
    __tablename__ = 'candlestick_data'
    
    symbol = Column(TEXT, nullable=False, primary_key=True)
    timeframe = Column(TEXT, nullable=False, primary_key=True)
    open_time = Column(TIMESTAMP(timezone=True), nullable=False, primary_key=True)
    close_time = Column(TIMESTAMP(timezone=True), nullable=False)
    open_price = Column(DECIMAL(12, 6), nullable=False)
    high_price = Column(DECIMAL(12, 6), nullable=False)
    low_price = Column(DECIMAL(12, 6), nullable=False)
    close_price = Column(DECIMAL(12, 6), nullable=False)
    tick_count = Column(INTEGER, default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<CandlestickData(symbol='{self.symbol}', timeframe='{self.timeframe}', open_time='{self.open_time}', OHLC=[{self.open_price},{self.high_price},{self.low_price},{self.close_price}])>"
    
    def to_dict(self):
        """辞書形式に変換"""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'open_time': self.open_time.isoformat() if self.open_time else None,
            'close_time': self.close_time.isoformat() if self.close_time else None,
            'open_price': float(self.open_price) if self.open_price else None,
            'high_price': float(self.high_price) if self.high_price else None,
            'low_price': float(self.low_price) if self.low_price else None,
            'close_price': float(self.close_price) if self.close_price else None,
            'tick_count': self.tick_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_csv_row(cls, symbol: str, timeframe: str, date_str: str, open_val: float, 
                     high_val: float, low_val: float, close_val: float):
        """CSVデータからインスタンス作成"""
        from datetime import datetime, timedelta
        
        # 時間枠に応じてclose_timeを計算
        open_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        
        if timeframe == '1m':
            close_time = open_time + timedelta(minutes=1)
        elif timeframe == '15m':
            close_time = open_time + timedelta(minutes=15)
        elif timeframe == '1h':
            close_time = open_time + timedelta(hours=1)
        elif timeframe == '4h':
            close_time = open_time + timedelta(hours=4)
        elif timeframe == '1d':
            close_time = open_time + timedelta(days=1)
        else:
            close_time = open_time + timedelta(minutes=1)  # デフォルト
        
        return cls(
            symbol=symbol,
            timeframe=timeframe,
            open_time=open_time,
            close_time=close_time,
            open_price=open_val,
            high_price=high_val,
            low_price=low_val,
            close_price=close_val,
            tick_count=0
        )
    
    def get_ohlc_array(self):
        """OHLC価格を配列で返す"""
        return [
            float(self.open_price),
            float(self.high_price),
            float(self.low_price),
            float(self.close_price)
        ]
    
    @property
    def body_size(self):
        """ローソク足の実体サイズ"""
        return abs(self.close_price - self.open_price)
    
    @property
    def upper_wick(self):
        """上ヒゲの長さ"""
        return self.high_price - max(self.open_price, self.close_price)
    
    @property
    def lower_wick(self):
        """下ヒゲの長さ"""
        return min(self.open_price, self.close_price) - self.low_price
    
    @property
    def is_bullish(self):
        """陽線かどうか"""
        return self.close_price > self.open_price
    
    @property
    def is_bearish(self):
        """陰線かどうか"""
        return self.close_price < self.open_price