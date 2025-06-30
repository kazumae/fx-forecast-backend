#!/usr/bin/env python3
"""
Signal Monitor Continuous Runner

継続的にエントリーポイントを監視するデーモンスクリプト
1分毎にシグナルをチェックし、検出時にSlack通知を送信する

使用方法:
    python run_signal_monitor.py
"""
import asyncio
import logging
import signal
import sys
from src.batch.jobs.signal_monitor import SignalMonitorJob


# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class SignalMonitorDaemon:
    """シグナルモニターデーモン"""
    
    def __init__(self):
        self.monitor = SignalMonitorJob()
        self.should_stop = False
        
    def setup_signal_handlers(self):
        """シグナルハンドラーのセットアップ"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, stopping...")
            self.should_stop = True
            self.monitor.stop()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    async def run(self):
        """デーモンの実行"""
        logger.info("Starting Signal Monitor Daemon...")
        
        try:
            # シグナルハンドラーのセットアップ
            self.setup_signal_handlers()
            
            # 開始通知
            if self.monitor.slack_notifier:
                self.monitor.send_custom_notification(
                    title="📡 Signal Monitor Started",
                    message="エントリーポイント監視を開始しました",
                    color="good"
                )
            
            # 継続実行
            await self.monitor.run_continuous()
            
        except Exception as e:
            logger.error(f"Fatal error in daemon: {e}")
            
            # エラー通知
            if self.monitor.slack_notifier:
                self.monitor.send_custom_notification(
                    title="❌ Signal Monitor Error",
                    message=f"エントリーポイント監視でエラーが発生しました: {str(e)}",
                    color="danger"
                )
            raise
            
        finally:
            # 終了通知
            if self.monitor.slack_notifier:
                self.monitor.send_custom_notification(
                    title="🛑 Signal Monitor Stopped",
                    message="エントリーポイント監視を停止しました",
                    color="warning"
                )
            
            logger.info("Signal Monitor Daemon stopped")


async def main():
    """メインエントリーポイント"""
    daemon = SignalMonitorDaemon()
    await daemon.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)