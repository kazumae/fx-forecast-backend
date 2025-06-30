from datetime import datetime, timedelta

from src.batch.base import BaseBatchJob
from src.models.forex import ForexRate
from src.models.candlestick import CandlestickData
from src.models.technical_indicator import TechnicalIndicator


class CleanupOldDataBatch(BaseBatchJob):
    """古いデータを削除するバッチジョブ"""
    
    def __init__(self, days_to_keep: int = 7):
        super().__init__("CleanupOldData")
        self.days_to_keep = days_to_keep
    
    def execute(self):
        """指定日数より古いデータを削除"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.days_to_keep)
        
        # 古い為替レートを削除
        deleted_rates = self.db.query(ForexRate)\
            .filter(ForexRate.created_at < cutoff_date)\
            .delete()
        
        # 古いローソク足データを削除
        deleted_candles = self.db.query(CandlestickData)\
            .filter(CandlestickData.created_at < cutoff_date)\
            .delete()
        
        # 古い技術指標データを削除
        deleted_indicators = self.db.query(TechnicalIndicator)\
            .filter(TechnicalIndicator.created_at < cutoff_date)\
            .delete()
        
        self.db.commit()
        
        self.logger.info(
            f"Deleted data older than {cutoff_date}: "
            f"forex_rates={deleted_rates}, "
            f"candlesticks={deleted_candles}, "
            f"indicators={deleted_indicators}"
        )
        
        # Slackに通知するための詳細情報を設定
        self.set_execution_detail("削除期間", f"{self.days_to_keep}日以前")
        self.set_execution_detail("削除基準日", cutoff_date.isoformat())
        self.set_execution_detail("forex_rates削除件数", deleted_rates)
        self.set_execution_detail("candlestick_data削除件数", deleted_candles)
        self.set_execution_detail("technical_indicators削除件数", deleted_indicators)
        
        return {
            "deleted_rates": deleted_rates,
            "deleted_candles": deleted_candles,
            "deleted_indicators": deleted_indicators,
            "cutoff_date": cutoff_date
        }