"""
バッチジョブスケジューラー
"""
import schedule
import time
import logging
from datetime import datetime
import subprocess
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_batch_job(job_name: str, *args):
    """バッチジョブを実行"""
    try:
        cmd = ["python", "run_batch.py", job_name] + list(args)
        logger.info(f"Running batch job: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd="/app"
        )
        
        if result.returncode == 0:
            logger.info(f"Batch job {job_name} completed successfully")
        else:
            logger.error(f"Batch job {job_name} failed: {result.stderr}")
            
    except Exception as e:
        logger.error(f"Error running batch job {job_name}: {e}")


def main():
    """スケジューラーのメイン処理"""
    logger.info("Starting batch job scheduler...")
    
    # ジョブをスケジュール
    # 毎日午前2時にクリーンアップ
    schedule.every().day.at("02:00").do(
        run_batch_job, "cleanup_old_data", "--days", "7"
    )
    
    # 毎日午前6時に日次レポート
    schedule.every().day.at("06:00").do(
        run_batch_job, "generate_daily_report"
    )
    
    # 毎朝9時にSlack通知
    schedule.every().day.at("09:00").do(
        run_batch_job, "slack_notification", "--notification-type", "daily_summary"
    )
    
    # テスト用：1時間ごとにヘルスチェック
    schedule.every().hour.do(
        lambda: logger.info(f"Scheduler health check at {datetime.now()}")
    )
    
    logger.info("Scheduler initialized. Waiting for jobs...")
    
    # スケジューラーを実行
    while True:
        schedule.run_pending()
        time.sleep(60)  # 1分ごとにチェック


if __name__ == "__main__":
    main()