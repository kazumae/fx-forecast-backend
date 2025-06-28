from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Any, Dict, List
import logging
from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.batch.utils.slack_notifier import SlackNotifier

logging.basicConfig(level=logging.INFO)


class BaseBatchJob(ABC):
    """バッチジョブの基底クラス"""
    
    def __init__(self, job_name: str, enable_slack_notification: bool = True):
        self.job_name = job_name
        self.logger = logging.getLogger(job_name)
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self._db: Optional[Session] = None
        self.enable_slack_notification = enable_slack_notification
        self.slack_notifier = SlackNotifier() if enable_slack_notification else None
        self._execution_details: Dict[str, Any] = {}
    
    @property
    def db(self) -> Session:
        """データベースセッションを取得"""
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def __enter__(self):
        """コンテキストマネージャーの開始"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャーの終了"""
        if self._db:
            self._db.close()
    
    def run(self) -> Any:
        """バッチジョブを実行"""
        self.start_time = datetime.utcnow()
        self.logger.info(f"Starting batch job: {self.job_name} at {self.start_time}")
        
        # 開始通知を送信
        if self.slack_notifier and self.should_notify_on_start():
            self.slack_notifier.send_batch_notification(
                job_name=self.job_name,
                status="started",
                message=f"バッチジョブ {self.job_name} を開始しました"
            )
        
        try:
            # 前処理
            self.before_execute()
            
            # メイン処理
            result = self.execute()
            
            # 後処理
            self.after_execute()
            
            # コミット
            if self._db:
                self._db.commit()
            
            self.end_time = datetime.utcnow()
            duration = (self.end_time - self.start_time).total_seconds()
            self.logger.info(
                f"Completed batch job: {self.job_name} "
                f"Duration: {duration:.2f} seconds"
            )
            
            # 完了通知を送信
            if self.slack_notifier and self.should_notify_on_complete():
                details = {
                    "実行時間": f"{duration:.2f}秒",
                    "開始時刻": self.start_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "終了時刻": self.end_time.strftime("%Y-%m-%d %H:%M:%S UTC")
                }
                # 実行詳細を追加
                details.update(self._execution_details)
                
                self.slack_notifier.send_batch_notification(
                    job_name=self.job_name,
                    status="completed",
                    message=f"バッチジョブ {self.job_name} が正常に完了しました",
                    details=details
                )
            
            return result
            
        except Exception as e:
            # ロールバック
            if self._db:
                self._db.rollback()
            
            self.logger.error(f"Error in batch job {self.job_name}: {str(e)}", exc_info=True)
            
            # エラー通知を送信
            if self.slack_notifier and self.should_notify_on_error():
                self.slack_notifier.send_batch_notification(
                    job_name=self.job_name,
                    status="failed",
                    message=f"バッチジョブ {self.job_name} でエラーが発生しました",
                    error=e
                )
            
            self.on_error(e)
            raise
        
        finally:
            # クリーンアップ
            self.cleanup()
    
    def before_execute(self):
        """実行前の処理（オーバーライド可能）"""
        pass
    
    @abstractmethod
    def execute(self) -> Any:
        """メイン処理（必須実装）"""
        pass
    
    def after_execute(self):
        """実行後の処理（オーバーライド可能）"""
        pass
    
    def on_error(self, error: Exception):
        """エラー時の処理（オーバーライド可能）"""
        pass
    
    def cleanup(self):
        """クリーンアップ処理（オーバーライド可能）"""
        pass
    
    def should_notify_on_start(self) -> bool:
        """開始時に通知を送るかどうか（オーバーライド可能）"""
        return False  # デフォルトでは開始通知は送らない
    
    def should_notify_on_complete(self) -> bool:
        """完了時に通知を送るかどうか（オーバーライド可能）"""
        return True  # デフォルトでは完了通知を送る
    
    def should_notify_on_error(self) -> bool:
        """エラー時に通知を送るかどうか（オーバーライド可能）"""
        return True  # デフォルトではエラー通知を送る
    
    def set_execution_detail(self, key: str, value: Any):
        """実行詳細を設定（Slack通知に含まれる）"""
        self._execution_details[key] = value
    
    def send_custom_notification(self, title: str, message: str, color: str = "good", 
                                fields: Optional[List[Dict[str, str]]] = None, emoji: Optional[str] = None):
        """カスタム通知を送信"""
        if self.slack_notifier:
            return self.slack_notifier.send_custom_notification(
                title=title,
                message=message,
                color=color,
                fields=fields,
                emoji=emoji
            )
        return False