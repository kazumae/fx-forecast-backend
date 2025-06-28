#!/usr/bin/env python
"""
Slack通知統合のテストスクリプト

使用方法:
    docker-compose exec app python test_slack_integration.py
"""

import sys
import logging
from src.batch.jobs.fetch_forex_rates import FetchForexRatesBatch
from src.batch.jobs.example_notification import ExampleNotificationBatch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_basic_notification():
    """基本的な通知機能のテスト"""
    logger.info("=== 基本的な通知機能のテスト ===")
    
    # 為替レート取得バッチを実行（完了通知が自動送信される）
    job = FetchForexRatesBatch(currency_pairs=["USD/JPY", "EUR/USD"])
    with job:
        result = job.run()
        logger.info(f"Result: {result}")


def test_custom_notification():
    """カスタム通知機能のテスト"""
    logger.info("=== カスタム通知機能のテスト ===")
    
    # カスタム通知を含むバッチを実行
    job = ExampleNotificationBatch()
    with job:
        result = job.run()
        logger.info(f"Result: {result}")


def main():
    """メイン処理"""
    if len(sys.argv) > 1 and sys.argv[1] == "custom":
        test_custom_notification()
    else:
        test_basic_notification()
    
    logger.info("テスト完了")


if __name__ == "__main__":
    main()