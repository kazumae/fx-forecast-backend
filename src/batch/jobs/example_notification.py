"""
Slack通知機能の使用例を示すバッチジョブ
"""
from datetime import datetime
from src.batch.base import BaseBatchJob


class ExampleNotificationBatch(BaseBatchJob):
    """通知設定をカスタマイズした例"""
    
    def __init__(self):
        # 通知を有効化してバッチジョブを初期化
        super().__init__("ExampleNotification", enable_slack_notification=True)
    
    def should_notify_on_start(self) -> bool:
        """開始時も通知を送る例"""
        return True
    
    def execute(self):
        """メイン処理"""
        # 処理中にカスタム通知を送信する例
        self.send_custom_notification(
            title="処理状況",
            message="データ処理を開始しました",
            color="warning",
            fields=[
                {"title": "ステップ", "value": "1/3", "short": True},
                {"title": "処理内容", "value": "データ検証", "short": True}
            ],
            emoji="⚡"
        )
        
        # 実際の処理（例として簡単な処理）
        total_records = 1000
        processed = 0
        
        # バッチ処理のシミュレーション
        for i in range(10):
            processed += 100
            self.logger.info(f"Processed {processed}/{total_records} records")
        
        # 実行詳細を設定（完了通知に含まれる）
        self.set_execution_detail("処理レコード数", total_records)
        self.set_execution_detail("成功率", "100%")
        
        # 処理完了のカスタム通知
        self.send_custom_notification(
            title="処理完了",
            message="すべてのデータ処理が完了しました",
            color="good",
            fields=[
                {"title": "総レコード数", "value": str(total_records), "short": True},
                {"title": "処理時間", "value": "10秒", "short": True}
            ],
            emoji="✨"
        )
        
        return {"total_records": total_records, "processed": processed}


class DisabledNotificationBatch(BaseBatchJob):
    """通知を無効化した例"""
    
    def __init__(self):
        # 通知を無効化してバッチジョブを初期化
        super().__init__("DisabledNotification", enable_slack_notification=False)
    
    def execute(self):
        """通知なしで実行される処理"""
        self.logger.info("This job runs without Slack notifications")
        return {"status": "completed"}


class ErrorNotificationOnlyBatch(BaseBatchJob):
    """エラー時のみ通知を送る例"""
    
    def __init__(self):
        super().__init__("ErrorNotificationOnly", enable_slack_notification=True)
    
    def should_notify_on_complete(self) -> bool:
        """完了時の通知は送らない"""
        return False
    
    def execute(self):
        """エラー時のみ通知される処理"""
        # 正常に処理が完了した場合は通知されない
        self.logger.info("Processing data...")
        
        # エラーをシミュレートする場合はコメントを外す
        # raise Exception("データ処理でエラーが発生しました")
        
        return {"status": "success"}