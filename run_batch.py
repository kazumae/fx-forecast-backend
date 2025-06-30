#!/usr/bin/env python
"""
バッチジョブ実行スクリプト

使用方法:
    python run_batch.py <job_name> [options]

例:
    python run_batch.py fetch_forex_rates
    python run_batch.py cleanup_old_data --days 90
    python run_batch.py generate_daily_report
"""

import sys
import argparse
import logging
from typing import Dict, Type

# バッチジョブのインポート
from src.batch.base import BaseBatchJob
from src.batch.jobs.fetch_forex_rates import FetchForexRatesBatch
from src.batch.jobs.cleanup_old_data import CleanupOldDataBatch
from src.batch.jobs.generate_daily_report import GenerateDailyReportBatch
from src.batch.jobs.slack_notification import SlackNotificationBatch
from src.batch.jobs.example_notification import (
    ExampleNotificationBatch,
    DisabledNotificationBatch,
    ErrorNotificationOnlyBatch
)
from src.batch.jobs.signal_monitor import SignalMonitorJob
from src.batch.jobs.signal_monitor_v2 import EnhancedSignalMonitorJob
from src.batch.jobs.ai_market_analysis import AIMarketAnalysisJob
from src.batch.jobs.update_indicators import UpdateIndicatorsJob

# ジョブレジストリ
JOB_REGISTRY: Dict[str, Type[BaseBatchJob]] = {
    "fetch_forex_rates": FetchForexRatesBatch,
    "cleanup_old_data": CleanupOldDataBatch,
    "generate_daily_report": GenerateDailyReportBatch,
    "slack_notification": SlackNotificationBatch,
    "example_notification": ExampleNotificationBatch,
    "disabled_notification": DisabledNotificationBatch,
    "error_notification_only": ErrorNotificationOnlyBatch,
    "signal_monitor": EnhancedSignalMonitorJob,  # Enhanced version with pattern detection
    "ai_market_analysis": AIMarketAnalysisJob,
    "update_indicators": UpdateIndicatorsJob,
}


def setup_logging():
    """ロギングの設定"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            # ファイルハンドラーも追加可能
            # logging.FileHandler('batch.log')
        ]
    )


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description="Run batch jobs")
    parser.add_argument("job_name", choices=list(JOB_REGISTRY.keys()),
                       help="Name of the batch job to run")
    
    # ジョブ固有のオプション
    parser.add_argument("--days", type=int, default=30,
                       help="Days to keep for cleanup job")
    parser.add_argument("--pairs", nargs="+",
                       help="Currency pairs for forex fetch job")
    parser.add_argument("--notification-type", 
                       choices=["daily_summary", "rate_alert", "system_status"],
                       default="daily_summary",
                       help="Type of Slack notification to send")
    parser.add_argument("--symbol", type=str, default="XAUUSD",
                       help="Symbol to analyze for AI market analysis")
    parser.add_argument("--dry-run", action="store_true",
                       help="Run without sending notifications")
    parser.add_argument("--timeframe", type=str,
                       help="Timeframe for indicator update (1m, 5m, 15m, 1h, 4h, 1d)")
    
    args = parser.parse_args()
    
    # ロギング設定
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # ジョブクラスを取得
    job_class = JOB_REGISTRY.get(args.job_name)
    if not job_class:
        logger.error(f"Unknown job: {args.job_name}")
        sys.exit(1)
    
    try:
        # ジョブインスタンスを作成
        if args.job_name == "cleanup_old_data":
            job = job_class(days_to_keep=args.days)
        elif args.job_name == "fetch_forex_rates" and args.pairs:
            job = job_class(currency_pairs=args.pairs)
        elif args.job_name == "slack_notification":
            job = job_class(notification_type=args.notification_type)
        elif args.job_name == "ai_market_analysis":
            job = job_class()
            # AI分析は非同期なので特別な処理
            import asyncio
            result = asyncio.run(job.execute(symbol=args.symbol, dry_run=args.dry_run))
            logger.info(f"AI analysis completed: {result}")
            sys.exit(0)
        elif args.job_name == "update_indicators":
            job = job_class()
            # 通常のバッチジョブとして実行
            with job:
                result = job.execute(timeframe=args.timeframe, symbol=args.symbol)
                logger.info(f"Indicator update completed: {result}")
                sys.exit(0)
        else:
            job = job_class()
        
        # ジョブを実行
        with job:
            result = job.run()
            logger.info(f"Job completed successfully: {result}")
            
    except Exception as e:
        logger.error(f"Job failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()