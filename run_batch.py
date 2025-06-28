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

# ジョブレジストリ
JOB_REGISTRY: Dict[str, Type[BaseBatchJob]] = {
    "fetch_forex_rates": FetchForexRatesBatch,
    "cleanup_old_data": CleanupOldDataBatch,
    "generate_daily_report": GenerateDailyReportBatch,
    "slack_notification": SlackNotificationBatch,
    "example_notification": ExampleNotificationBatch,
    "disabled_notification": DisabledNotificationBatch,
    "error_notification_only": ErrorNotificationOnlyBatch,
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