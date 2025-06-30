from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from .base import Base


class TechnicalIndicator(Base):
    """技術指標データモデル"""
    
    __tablename__ = "technical_indicators"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), nullable=False)
    timeframe = Column(String(5), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    
    # 移動平均
    ema_5 = Column(Float)
    ema_10 = Column(Float)
    ema_15 = Column(Float)
    ema_20 = Column(Float)
    ema_50 = Column(Float)
    ema_100 = Column(Float)
    ema_200 = Column(Float)
    
    # RSI
    rsi_14 = Column(Float)
    
    # MACD
    macd = Column(Float)
    macd_signal = Column(Float)
    macd_histogram = Column(Float)
    
    # ボリンジャーバンド
    bb_upper = Column(Float)
    bb_middle = Column(Float)
    bb_lower = Column(Float)
    
    # ATR
    atr_14 = Column(Float)
    
    # ストキャスティクス
    stoch_k = Column(Float)
    stoch_d = Column(Float)
    
    # 作成日時
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        # 複合インデックス: symbol, timeframe, timestamp でクエリが高速化
        Index('idx_technical_indicators_symbol_timeframe_timestamp', 
              'symbol', 'timeframe', 'timestamp'),
    )