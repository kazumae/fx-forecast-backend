"""
通知履歴モデル
送信された通知の履歴を管理
"""

from sqlalchemy import Column, BIGINT, TEXT, BOOLEAN, ForeignKey, TIMESTAMP, func
from sqlalchemy.orm import relationship
from .base import Base


class NotificationHistory(Base):
    __tablename__ = 'notification_history'
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    analysis_id = Column(BIGINT, ForeignKey('ai_analysis_results.id'))
    notification_type = Column(TEXT, nullable=False)  # 'slack', 'email', 'push'
    recipient = Column(TEXT, nullable=False)
    status = Column(TEXT, default='pending')  # 'pending', 'sent', 'failed'
    sent_at = Column(TIMESTAMP(timezone=True))
    error_message = Column(TEXT)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # リレーション
    analysis_result = relationship("AIAnalysisResult", back_populates="notifications")
    
    def __repr__(self):
        return f"<NotificationHistory(type='{self.notification_type}', status='{self.status}', recipient='{self.recipient}')>"
    
    def to_dict(self):
        """辞書形式に変換"""
        return {
            'id': self.id,
            'analysis_id': self.analysis_id,
            'notification_type': self.notification_type,
            'recipient': self.recipient,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create_slack_notification(cls, analysis_id: int, channel: str):
        """Slack通知インスタンス作成"""
        return cls(
            analysis_id=analysis_id,
            notification_type='slack',
            recipient=channel,
            status='pending'
        )
    
    @classmethod
    def create_email_notification(cls, analysis_id: int, email: str):
        """メール通知インスタンス作成"""
        return cls(
            analysis_id=analysis_id,
            notification_type='email',
            recipient=email,
            status='pending'
        )
    
    def mark_as_sent(self):
        """送信完了としてマーク"""
        self.status = 'sent'
        self.sent_at = func.now()
    
    def mark_as_failed(self, error_message: str):
        """送信失敗としてマーク"""
        self.status = 'failed'
        self.error_message = error_message
    
    def is_pending(self) -> bool:
        """送信待ちかどうか"""
        return self.status == 'pending'
    
    def is_sent(self) -> bool:
        """送信完了かどうか"""
        return self.status == 'sent'