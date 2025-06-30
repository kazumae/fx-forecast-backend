from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy import func

from src.batch.base import BaseBatchJob
from src.models.forex import ForexRate
from src.models.candlestick import CandlestickData
from src.models.technical_indicator import TechnicalIndicator


class GenerateDailyReportBatch(BaseBatchJob):
    """日次レポートを生成するバッチジョブ"""
    
    def __init__(self):
        super().__init__("GenerateDailyReport")
    
    def execute(self):
        """日次レポートを生成"""
        report_date = datetime.utcnow().date()
        start_time = datetime.combine(report_date, datetime.min.time())
        end_time = start_time + timedelta(days=1)
        
        # 為替レート統計
        forex_stats = self._get_forex_statistics(start_time, end_time)
        
        # ローソク足統計
        candle_stats = self._get_candlestick_statistics(start_time, end_time)
        
        # 技術指標統計
        indicator_stats = self._get_indicator_statistics(start_time, end_time)
        
        # レポート作成
        report = {
            "report_date": report_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "forex_statistics": forex_stats,
            "candlestick_statistics": candle_stats,
            "indicator_statistics": indicator_stats
        }
        
        # レポートを表示
        self.logger.info("=== Daily Report ===")
        self.logger.info(f"Date: {report_date}")
        
        for pair, stats in forex_stats.items():
            self.logger.info(
                f"{pair}: Records={stats['count']}, "
                f"Avg={stats['avg_rate']:.4f}, "
                f"Min={stats['min_rate']:.4f}, "
                f"Max={stats['max_rate']:.4f}"
            )
        
        return report
    
    def _get_candlestick_statistics(self, start_time: datetime, end_time: datetime) -> Dict:
        """ローソク足統計を取得"""
        stats_query = self.db.query(
            CandlestickData.symbol,
            CandlestickData.timeframe,
            func.count().label('count')
        ).filter(
            CandlestickData.created_at >= start_time,
            CandlestickData.created_at < end_time
        ).group_by(
            CandlestickData.symbol,
            CandlestickData.timeframe
        ).all()
        
        candle_stats = {}
        for stat in stats_query:
            key = f"{stat.symbol}_{stat.timeframe}"
            candle_stats[key] = {"count": stat.count}
        
        return candle_stats
    
    def _get_indicator_statistics(self, start_time: datetime, end_time: datetime) -> Dict:
        """技術指標統計を取得"""
        count = self.db.query(func.count(TechnicalIndicator.id))\
            .filter(
                TechnicalIndicator.created_at >= start_time,
                TechnicalIndicator.created_at < end_time
            ).scalar()
        
        return {"total_calculations": count}
    
    def _get_forex_statistics(self, start_time: datetime, end_time: datetime) -> Dict:
        """為替レート統計を取得"""
        # 通貨ペアごとの統計を取得
        stats_query = self.db.query(
            ForexRate.currency_pair,
            func.count(ForexRate.id).label('count'),
            func.avg(ForexRate.rate).label('avg_rate'),
            func.min(ForexRate.rate).label('min_rate'),
            func.max(ForexRate.rate).label('max_rate')
        ).filter(
            ForexRate.timestamp >= start_time,
            ForexRate.timestamp < end_time
        ).group_by(ForexRate.currency_pair).all()
        
        forex_stats = {}
        for stat in stats_query:
            forex_stats[stat.currency_pair] = {
                "count": stat.count,
                "avg_rate": float(stat.avg_rate) if stat.avg_rate else 0,
                "min_rate": float(stat.min_rate) if stat.min_rate else 0,
                "max_rate": float(stat.max_rate) if stat.max_rate else 0
            }
        
        return forex_stats