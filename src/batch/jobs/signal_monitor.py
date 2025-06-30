"""
Signal Monitor Job - Periodic Entry Point Detection
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import redis
from sqlalchemy.orm import Session

from src.batch.base import BaseBatchJob
from src.core.config import settings
from src.db.session import SessionLocal
from src.models.forex import ForexRate
from src.services.entry_point.signal_generation import EntrySignalGenerator
from src.services.entry_point.signal_validation import SignalValidationService
from src.batch.utils.slack_notifier import SlackNotifier


class SignalMonitorJob(BaseBatchJob):
    """エントリーポイント監視ジョブ
    
    1分毎にエントリーポイントを監視し、シグナルを検出する
    """
    
    def __init__(self):
        super().__init__(
            job_name="signal_monitor",
            enable_slack_notification=True
        )
        
        # Services
        self.signal_generator = EntrySignalGenerator()
        self.signal_validator = SignalValidationService()
        
        # Redis for duplicate detection
        try:
            self.redis_client = redis.from_url(
                "redis://redis:6379",
                decode_responses=True
            )
            self.redis_enabled = True
        except Exception as e:
            self.logger.warning(f"Redis connection failed: {e}")
            self.redis_client = None
            self.redis_enabled = False
        
        # Configuration
        self.target_symbols = ["XAUUSD"]  # 監視対象シンボル
        self.timeframes = ["1m", "15m", "1h"]  # 監視時間枠
        self.check_interval = 60  # 実行間隔（秒）
        self.retry_count = 0
        self.max_retries = 3
        
        # Execution control
        self.is_running = False
        self.execution_lock = asyncio.Lock()
        
    def execute(self) -> Dict[str, Any]:
        """メイン実行処理（BaseBatchJobのabstractmethod）"""
        # 非同期処理を同期的に実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(self._execute_async())
            return result
        finally:
            loop.close()
            
    async def _execute_async(self) -> Dict[str, Any]:
        """非同期実行処理"""
        start_time = datetime.utcnow()
        detected_signals = []
        errors = []
        
        try:
            # 各シンボルをチェック
            for symbol in self.target_symbols:
                try:
                    signals = await self._check_symbol_signals(symbol)
                    detected_signals.extend(signals)
                except Exception as e:
                    self.logger.error(f"Error checking {symbol}: {e}")
                    errors.append({
                        "symbol": symbol,
                        "error": str(e),
                        "timestamp": datetime.utcnow()
                    })
                    
            # 実行詳細を設定
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self.set_execution_detail("実行時間", f"{execution_time:.2f}秒")
            self.set_execution_detail("検出シグナル数", len(detected_signals))
            self.set_execution_detail("エラー数", len(errors))
            
            # シグナルが検出された場合は通知
            if detected_signals:
                await self._notify_signals(detected_signals)
                
            return {
                "status": "success",
                "signals": detected_signals,
                "errors": errors,
                "execution_time": execution_time
            }
            
        except Exception as e:
            self.logger.error(f"Fatal error in signal monitor: {e}")
            raise
            
    async def _check_symbol_signals(self, symbol: str) -> List[Dict[str, Any]]:
        """特定シンボルのシグナルをチェック"""
        detected_signals = []
        
        # 最新のデータを取得
        with SessionLocal() as db:
            # 各時間枠でチェック
            for timeframe in self.timeframes:
                try:
                    # 最新のデータを取得（簡易版）
                    latest_data = self._get_latest_data(db, symbol, timeframe)
                    
                    if not latest_data:
                        continue
                        
                    # シグナル生成
                    signals = self.signal_generator.generate_signals(latest_data)
                    
                    # シグナル検証
                    for signal in signals:
                        if self.signal_validator.validate_signal(signal):
                            # 重複チェック
                            if not self._is_duplicate_signal(symbol, timeframe, signal):
                                detected_signals.append({
                                    "symbol": symbol,
                                    "timeframe": timeframe,
                                    "signal": signal,
                                    "timestamp": datetime.utcnow()
                                })
                                
                                # 重複防止のためRedisに記録
                                self._record_signal(symbol, timeframe, signal)
                                
                except Exception as e:
                    self.logger.error(f"Error processing {symbol} {timeframe}: {e}")
                    
        return detected_signals
        
    def _get_latest_data(self, db: Session, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """最新データを取得（簡易実装）"""
        # TODO: 実際の実装では時間枠に応じたキャンドルデータを取得
        # ここでは最新のティックデータを返す
        
        latest = db.query(ForexRate).filter(
            ForexRate.currency_pair == symbol
        ).order_by(ForexRate.timestamp.desc()).first()
        
        if latest:
            return {
                "symbol": symbol,
                "bid": latest.bid,
                "ask": latest.ask,
                "rate": latest.rate,
                "timestamp": latest.timestamp
            }
        return None
        
    def _is_duplicate_signal(self, symbol: str, timeframe: str, signal: Dict) -> bool:
        """重複シグナルかチェック"""
        if not self.redis_enabled:
            return False
            
        # キー生成（1時間有効）
        key = f"signal:{symbol}:{timeframe}:{signal.get('type', 'unknown')}"
        
        # 既存チェック
        if self.redis_client.exists(key):
            return True
            
        return False
        
    def _record_signal(self, symbol: str, timeframe: str, signal: Dict):
        """シグナルを記録"""
        if not self.redis_enabled:
            return
            
        key = f"signal:{symbol}:{timeframe}:{signal.get('type', 'unknown')}"
        self.redis_client.setex(key, 3600, "1")  # 1時間有効
        
    async def _notify_signals(self, signals: List[Dict[str, Any]]):
        """検出されたシグナルを通知"""
        if not signals:
            return
            
        # Slack通知の構築
        fields = []
        for signal in signals[:5]:  # 最大5件まで
            fields.append({
                "title": f"{signal['symbol']} - {signal['timeframe']}",
                "value": f"Signal: {signal['signal'].get('type', 'Unknown')}",
                "short": True
            })
            
        self.send_custom_notification(
            title="🎯 エントリーポイント検出",
            message=f"{len(signals)}件のシグナルを検出しました",
            color="good",
            fields=fields
        )
        
    async def run_continuous(self):
        """継続実行モード（デーモン用）"""
        self.is_running = True
        self.logger.info("Starting continuous signal monitoring...")
        
        while self.is_running:
            try:
                # 次の分の00秒まで待機
                await self._wait_until_next_minute()
                
                # ロックを取得して実行
                async with self.execution_lock:
                    self.logger.info(f"Executing signal check at {datetime.utcnow()}")
                    result = await self._execute_async()
                    
                    # エラーがあった場合はリトライカウントを増やす
                    if result.get("errors"):
                        self.retry_count += 1
                        if self.retry_count >= self.max_retries:
                            self.logger.error("Max retries reached, stopping execution")
                            break
                    else:
                        self.retry_count = 0
                        
            except Exception as e:
                self.logger.error(f"Error in continuous execution: {e}")
                self.retry_count += 1
                
                if self.retry_count >= self.max_retries:
                    self.logger.error("Max retries reached, stopping execution")
                    break
                    
                # エラー時は少し待機
                await asyncio.sleep(10)
                
    async def _wait_until_next_minute(self):
        """次の分の00秒まで待機"""
        now = datetime.utcnow()
        next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        wait_seconds = (next_minute - now).total_seconds()
        
        if wait_seconds > 0:
            self.logger.debug(f"Waiting {wait_seconds:.1f} seconds until next minute")
            await asyncio.sleep(wait_seconds)
            
    def stop(self):
        """実行を停止"""
        self.is_running = False
        self.logger.info("Stopping signal monitor...")
        
    def should_notify_on_start(self) -> bool:
        """開始時に通知を送るか"""
        return True
        
    def should_notify_on_complete(self) -> bool:
        """完了時に通知を送るか"""
        # 定期実行のため個別完了通知は不要
        return False
        
    def should_notify_on_error(self) -> bool:
        """エラー時に通知を送るか"""
        return True