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
    symbol = Column(String(10), nullable=False, index=True)
    timeframe = Column(String(5), nullable=False)
    signal_type = Column(String(10), nullable=False)  # BUY or SELL
    pattern_type = Column(String(50), nullable=True)  # v_shape_reversal, ema_squeeze, etc
    
    # 価格情報
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    
    # スコアと検証
    confidence_score = Column(Float, nullable=True)
    
    # ステータス
    status = Column(String(20), nullable=True)
    
    # メタデータ
    signal_metadata = Column("metadata", JSON, nullable=True)
    
    # タイムスタンプ
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)