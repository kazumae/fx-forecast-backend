"""
AI解析結果モデル
Anthropic APIによる解析結果とシグナルを格納
"""

from sqlalchemy import Column, BIGINT, TEXT, DECIMAL, BOOLEAN, JSON, TIMESTAMP, func
from .base import Base
from sqlalchemy.orm import relationship


class AIAnalysisResult(Base):
    __tablename__ = 'ai_analysis_results'
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    symbol = Column(TEXT, nullable=False)
    analysis_timestamp = Column(TIMESTAMP(timezone=True), nullable=False)
    timeframe = Column(TEXT, nullable=False)
    entry_signal = Column(TEXT)  # 'BUY', 'SELL', 'HOLD'
    confidence_score = Column(DECIMAL(5, 4))  # 0.0000 - 1.0000
    reasoning = Column(TEXT)
    technical_data = Column(JSON)
    anthropic_response = Column(JSON)
    notification_sent = Column(BOOLEAN, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # リレーション
    notifications = relationship("NotificationHistory", back_populates="analysis_result")
    
    def __repr__(self):
        return f"<AIAnalysisResult(symbol='{self.symbol}', signal='{self.entry_signal}', confidence={self.confidence_score})>"
    
    def to_dict(self):
        """辞書形式に変換"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'analysis_timestamp': self.analysis_timestamp.isoformat() if self.analysis_timestamp else None,
            'timeframe': self.timeframe,
            'entry_signal': self.entry_signal,
            'confidence_score': float(self.confidence_score) if self.confidence_score else None,
            'reasoning': self.reasoning,
            'technical_data': self.technical_data,
            'anthropic_response': self.anthropic_response,
            'notification_sent': self.notification_sent,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create_analysis(cls, symbol: str, timeframe: str, signal: str, confidence: float,
                       reasoning: str, technical_data: dict, anthropic_response: dict):
        """AI解析結果インスタンス作成"""
        return cls(
            symbol=symbol,
            analysis_timestamp=func.now(),
            timeframe=timeframe,
            entry_signal=signal,
            confidence_score=confidence,
            reasoning=reasoning,
            technical_data=technical_data,
            anthropic_response=anthropic_response,
            notification_sent=False
        )
    
    def is_strong_signal(self, threshold: float = 0.8) -> bool:
        """強いシグナルかどうか判定"""
        return (self.confidence_score is not None and 
                float(self.confidence_score) >= threshold and
                self.entry_signal in ['BUY', 'SELL'])
    
    def should_notify(self) -> bool:
        """通知すべきかどうか判定"""
        return (not self.notification_sent and 
                self.is_strong_signal() and
                self.entry_signal is not None)