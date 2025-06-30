"""
エントリーシグナルモデル
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Enum
from sqlalchemy.sql import func
import enum

from src.models.base import Base


class SignalStatus(str, enum.Enum):
    """シグナルステータス"""
    ACTIVE = "active"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class EntrySignal(Base):
    """エントリーシグナル"""
    __tablename__ = "entry_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    signal_type = Column(String, nullable=False)  # BUY or SELL
    pattern_type = Column(String, nullable=False)  # v_shape_reversal, ema_squeeze, etc
    timeframe = Column(String, nullable=False)  # 1m, 5m, 15m, etc
    
    # 価格情報
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    
    # スコアと検証
    confidence_score = Column(Float, nullable=False)
    validation_scores = Column(JSON, default={})
    
    # ステータス
    status = Column(Enum(SignalStatus), default=SignalStatus.ACTIVE, nullable=False)
    
    # メタデータ
    signal_metadata = Column("metadata", JSON, default={})
    
    # タイムスタンプ
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    expired_at = Column(DateTime(timezone=True), nullable=True)