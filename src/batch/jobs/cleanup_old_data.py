from datetime import datetime, timedelta

from src.batch.base import BaseBatchJob
from src.models.forex import ForexRate, ForexForecast


class CleanupOldDataBatch(BaseBatchJob):
    """古いデータを削除するバッチジョブ"""
    
    def __init__(self, days_to_keep: int = 30):
        super().__init__("CleanupOldData")
        self.days_to_keep = days_to_keep
    
    def execute(self):
        """指定日数より古いデータを削除"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.days_to_keep)
        
        # 古い為替レートを削除
        deleted_rates = self.db.query(ForexRate)\
            .filter(ForexRate.created_at < cutoff_date)\
            .delete()
        
        # 古い予測データを削除
        deleted_forecasts = self.db.query(ForexForecast)\
            .filter(ForexForecast.created_at < cutoff_date)\
            .delete()
        
        self.logger.info(
            f"Deleted {deleted_rates} forex rates and "
            f"{deleted_forecasts} forecasts older than {cutoff_date}"
        )
        
        return {
            "deleted_rates": deleted_rates,
            "deleted_forecasts": deleted_forecasts,
            "cutoff_date": cutoff_date
        }