"""
Unit tests for SignalMonitorJob
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
import asyncio

from src.batch.jobs.signal_monitor import SignalMonitorJob


class TestSignalMonitorJob:
    """SignalMonitorJobのテスト"""
    
    @pytest.fixture
    def monitor_job(self):
        """SignalMonitorJobのフィクスチャ"""
        with patch('src.batch.jobs.signal_monitor.redis.from_url'):
            job = SignalMonitorJob()
            job.slack_notifier = MagicMock()
            job.signal_generator = MagicMock()
            job.signal_validator = MagicMock()
            return job
            
    def test_initialization(self, monitor_job):
        """初期化のテスト"""
        assert monitor_job.job_name == "signal_monitor"
        assert monitor_job.target_symbols == ["XAUUSD"]
        assert monitor_job.timeframes == ["1m", "15m", "1h"]
        assert monitor_job.check_interval == 60
        assert monitor_job.max_retries == 3
        assert monitor_job.is_running is False
        
    @pytest.mark.asyncio
    async def test_wait_until_next_minute(self, monitor_job):
        """次の分まで待機するメソッドのテスト"""
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # 現在時刻を30秒に設定
            with patch('src.batch.jobs.signal_monitor.datetime') as mock_dt:
                now = datetime(2024, 1, 1, 12, 0, 30)
                mock_dt.utcnow.return_value = now
                
                await monitor_job._wait_until_next_minute()
                
                # 30秒待機することを確認
                mock_sleep.assert_called_once()
                wait_time = mock_sleep.call_args[0][0]
                assert 29.9 < wait_time < 30.1
                
    def test_is_duplicate_signal_without_redis(self, monitor_job):
        """Redis無効時の重複チェックテスト"""
        monitor_job.redis_enabled = False
        
        result = monitor_job._is_duplicate_signal(
            "XAUUSD", "1m", {"type": "BUY"}
        )
        assert result is False
        
    def test_is_duplicate_signal_with_redis(self, monitor_job):
        """Redis有効時の重複チェックテスト"""
        monitor_job.redis_enabled = True
        monitor_job.redis_client = MagicMock()
        
        # 既存シグナルがある場合
        monitor_job.redis_client.exists.return_value = True
        result = monitor_job._is_duplicate_signal(
            "XAUUSD", "1m", {"type": "BUY"}
        )
        assert result is True
        
        # 既存シグナルがない場合
        monitor_job.redis_client.exists.return_value = False
        result = monitor_job._is_duplicate_signal(
            "XAUUSD", "1m", {"type": "BUY"}
        )
        assert result is False
        
    def test_record_signal(self, monitor_job):
        """シグナル記録のテスト"""
        monitor_job.redis_enabled = True
        monitor_job.redis_client = MagicMock()
        
        monitor_job._record_signal("XAUUSD", "1m", {"type": "BUY"})
        
        monitor_job.redis_client.setex.assert_called_once_with(
            "signal:XAUUSD:1m:BUY", 3600, "1"
        )
        
    @patch('src.batch.jobs.signal_monitor.SessionLocal')
    def test_get_latest_data(self, mock_session, monitor_job):
        """最新データ取得のテスト"""
        # モックセッションとクエリ設定
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        
        mock_forex_rate = MagicMock()
        mock_forex_rate.bid = 1.1234
        mock_forex_rate.ask = 1.1236
        mock_forex_rate.rate = 1.1235
        mock_forex_rate.timestamp = datetime.utcnow()
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_forex_rate
        
        result = monitor_job._get_latest_data(mock_db, "XAUUSD", "1m")
        
        assert result is not None
        assert result["symbol"] == "XAUUSD"
        assert result["bid"] == 1.1234
        assert result["ask"] == 1.1236
        assert result["rate"] == 1.1235
        
    @pytest.mark.asyncio
    async def test_check_symbol_signals(self, monitor_job):
        """シンボルシグナルチェックのテスト"""
        # モックの設定
        monitor_job.signal_generator.generate_signals.return_value = [
            {"type": "BUY", "strength": 0.8}
        ]
        monitor_job.signal_validator.validate_signal.return_value = True
        monitor_job.redis_enabled = False  # 重複チェックを無効化
        
        with patch.object(monitor_job, '_get_latest_data') as mock_get_data:
            mock_get_data.return_value = {
                "symbol": "XAUUSD",
                "bid": 1.1234,
                "ask": 1.1236,
                "rate": 1.1235,
                "timestamp": datetime.utcnow()
            }
            
            signals = await monitor_job._check_symbol_signals("XAUUSD")
            
            assert len(signals) == 3  # 3つの時間枠
            assert signals[0]["symbol"] == "XAUUSD"
            assert signals[0]["timeframe"] == "1m"
            assert signals[0]["signal"]["type"] == "BUY"
            
    @pytest.mark.asyncio
    async def test_notify_signals(self, monitor_job):
        """シグナル通知のテスト"""
        signals = [
            {
                "symbol": "XAUUSD",
                "timeframe": "1m",
                "signal": {"type": "BUY"},
                "timestamp": datetime.utcnow()
            },
            {
                "symbol": "XAUUSD",
                "timeframe": "15m",
                "signal": {"type": "SELL"},
                "timestamp": datetime.utcnow()
            }
        ]
        
        await monitor_job._notify_signals(signals)
        
        monitor_job.send_custom_notification.assert_called_once()
        call_args = monitor_job.send_custom_notification.call_args
        assert call_args[1]["title"] == "🎯 エントリーポイント検出"
        assert "2件のシグナル" in call_args[1]["message"]
        assert call_args[1]["color"] == "good"
        assert len(call_args[1]["fields"]) == 2
        
    @pytest.mark.asyncio
    async def test_execute_async(self, monitor_job):
        """非同期実行のテスト"""
        # モックの設定
        with patch.object(monitor_job, '_check_symbol_signals') as mock_check:
            mock_check.return_value = [
                {
                    "symbol": "XAUUSD",
                    "timeframe": "1m",
                    "signal": {"type": "BUY"},
                    "timestamp": datetime.utcnow()
                }
            ]
            
            with patch.object(monitor_job, '_notify_signals') as mock_notify:
                result = await monitor_job._execute_async()
                
                assert result["status"] == "success"
                assert len(result["signals"]) == 1
                assert len(result["errors"]) == 0
                assert "execution_time" in result
                
                mock_check.assert_called_once_with("XAUUSD")
                mock_notify.assert_called_once()
                
    def test_execute(self, monitor_job):
        """同期実行のテスト"""
        with patch.object(monitor_job, '_execute_async') as mock_async:
            mock_async.return_value = {
                "status": "success",
                "signals": [],
                "errors": [],
                "execution_time": 0.5
            }
            
            result = monitor_job.execute()
            
            assert result["status"] == "success"
            
    @pytest.mark.asyncio
    async def test_run_continuous(self, monitor_job):
        """継続実行のテスト"""
        monitor_job.is_running = True
        
        # 2回実行後に停止
        execution_count = 0
        async def mock_execute():
            nonlocal execution_count
            execution_count += 1
            if execution_count >= 2:
                monitor_job.is_running = False
            return {
                "status": "success",
                "signals": [],
                "errors": [],
                "execution_time": 0.1
            }
            
        with patch.object(monitor_job, '_execute_async', side_effect=mock_execute):
            with patch.object(monitor_job, '_wait_until_next_minute', new_callable=AsyncMock):
                await monitor_job.run_continuous()
                
                assert execution_count == 2
                
    @pytest.mark.asyncio
    async def test_run_continuous_with_errors(self, monitor_job):
        """エラー時の継続実行テスト"""
        monitor_job.is_running = True
        monitor_job.max_retries = 2
        
        with patch.object(monitor_job, '_execute_async') as mock_exec:
            mock_exec.return_value = {
                "status": "error",
                "signals": [],
                "errors": [{"error": "test error"}],
                "execution_time": 0.1
            }
            
            with patch.object(monitor_job, '_wait_until_next_minute', new_callable=AsyncMock):
                await monitor_job.run_continuous()
                
                assert monitor_job.retry_count == 2
                assert mock_exec.call_count == 2
                
    def test_stop(self, monitor_job):
        """停止処理のテスト"""
        monitor_job.is_running = True
        monitor_job.stop()
        
        assert monitor_job.is_running is False
        
    def test_should_notify_flags(self, monitor_job):
        """通知フラグのテスト"""
        assert monitor_job.should_notify_on_start() is True
        assert monitor_job.should_notify_on_complete() is False
        assert monitor_job.should_notify_on_error() is True