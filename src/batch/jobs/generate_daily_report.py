from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy import func

from src.batch.base import BaseBatchJob
from src.models.forex import ForexRate
from src.models.user import User


class GenerateDailyReportBatch(BaseBatchJob):
    """日次レポートを生成するバッチジョブ"""
    
    def __init__(self):
        super().__init__("GenerateDailyReport")
    
    def execute(self):
        """日次レポートを生成"""
        report_date = datetime.utcnow().date()
        start_time = datetime.combine(report_date, datetime.min.time())
        end_time = start_time + timedelta(days=1)
        
        # ユーザー統計
        user_stats = self._get_user_statistics()
        
        # 為替レート統計
        forex_stats = self._get_forex_statistics(start_time, end_time)
        
        # レポート作成
        report = {
            "report_date": report_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "user_statistics": user_stats,
            "forex_statistics": forex_stats
        }
        
        # レポートを表示（実際はメール送信やファイル保存など）
        self.logger.info("=== Daily Report ===")
        self.logger.info(f"Date: {report_date}")
        self.logger.info(f"Total Users: {user_stats['total_users']}")
        self.logger.info(f"Active Users: {user_stats['active_users']}")
        
        for pair, stats in forex_stats.items():
            self.logger.info(
                f"{pair}: Records={stats['count']}, "
                f"Avg={stats['avg_rate']:.4f}, "
                f"Min={stats['min_rate']:.4f}, "
                f"Max={stats['max_rate']:.4f}"
            )
        
        return report
    
    def _get_user_statistics(self) -> Dict:
        """ユーザー統計を取得"""
        total_users = self.db.query(func.count(User.id)).scalar()
        active_users = self.db.query(func.count(User.id))\
            .filter(User.is_active == True).scalar()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users
        }
    
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