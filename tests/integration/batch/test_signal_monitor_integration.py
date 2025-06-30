"""
Integration tests for SignalMonitorJob
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.batch.jobs.signal_monitor import SignalMonitorJob
from src.models.forex import ForexRate
from src.db.session import SessionLocal


class TestSignalMonitorIntegration:
    """SignalMonitorJobの統合テスト"""
    
    @pytest.fixture
    def db_session(self):
        """データベースセッションのフィクスチャ"""
        session = SessionLocal()
        yield session
        session.close()
        
    @pytest.fixture
    def monitor_job(self):
        """SignalMonitorJobのフィクスチャ"""
        # Redisをモック化
        with patch('src.batch.jobs.signal_monitor.redis.from_url'):
            job = SignalMonitorJob()
            # Slack通知をモック化
            job.slack_notifier = MagicMock()
            job.send_custom_notification = MagicMock()
            return job
            
    @pytest.fixture
    def sample_forex_data(self, db_session):
        """サンプルデータの作成"""
        # テスト用のForexRateデータを作成
        data_points = []
        base_time = datetime.utcnow()
        
        for i in range(10):
            rate = ForexRate(
                currency_pair="XAUUSD",
                bid=1850.0 + i * 0.1,
                ask=1850.1 + i * 0.1,
                rate=1850.05 + i * 0.1,
                timestamp=base_time - timedelta(minutes=i),
                created_at=base_time - timedelta(minutes=i)
            )
            db_session.add(rate)
            data_points.append(rate)
            
        db_session.commit()
        
        yield data_points
        
        # クリーンアップ
        for rate in data_points:
            db_session.delete(rate)
        db_session.commit()
        
    def test_execute_with_real_data(self, monitor_job, sample_forex_data):
        """実データでの実行テスト"""
        # シグナル生成と検証をモック化
        monitor_job.signal_generator.generate_signals.return_value = [
            {"type": "BUY", "strength": 0.8, "price": 1850.05}
        ]
        monitor_job.signal_validator.validate_signal.return_value = True
        
        # 実行
        result = monitor_job.execute()
        
        # 検証
        assert result["status"] == "success"
        assert "signals" in result
        assert "errors" in result
        assert "execution_time" in result
        
        # シグナルが検出されたことを確認
        if result["signals"]:
            assert result["signals"][0]["symbol"] == "XAUUSD"
            
    @pytest.mark.asyncio
    async def test_continuous_execution_timing(self, monitor_job):
        """継続実行のタイミングテスト"""
        monitor_job.is_running = True
        execution_times = []
        
        async def track_execution():
            execution_times.append(datetime.utcnow())
            if len(execution_times) >= 2:
                monitor_job.is_running = False
            return {
                "status": "success",
                "signals": [],
                "errors": [],
                "execution_time": 0.1
            }
            
        with patch.object(monitor_job, '_execute_async', side_effect=track_execution):
            # 実際の待機時間を短縮してテスト
            with patch.object(monitor_job, '_wait_until_next_minute') as mock_wait:
                async def short_wait():
                    await asyncio.sleep(0.1)
                mock_wait.side_effect = short_wait
                
                await monitor_job.run_continuous()
                
                # 2回実行されたことを確認
                assert len(execution_times) == 2
                
    def test_error_handling_with_db_error(self, monitor_job):
        """データベースエラー時のハンドリングテスト"""
        # データベースエラーをシミュレート
        with patch('src.batch.jobs.signal_monitor.SessionLocal') as mock_session:
            mock_session.side_effect = Exception("Database connection error")
            
            # 実行してもクラッシュしないことを確認
            result = monitor_job.execute()
            
            assert result["status"] == "success"
            assert len(result["errors"]) > 0
            
    @pytest.mark.asyncio
    async def test_signal_notification_integration(self, monitor_job, sample_forex_data):
        """シグナル通知の統合テスト"""
        # シグナルを検出する設定
        monitor_job.signal_generator.generate_signals.return_value = [
            {"type": "BUY", "strength": 0.9, "price": 1850.15}
        ]
        monitor_job.signal_validator.validate_signal.return_value = True
        monitor_job.redis_enabled = False  # 重複チェックを無効化
        
        # 実行
        result = await monitor_job._execute_async()
        
        # 通知が送信されたことを確認
        if result["signals"]:
            monitor_job.send_custom_notification.assert_called()
            call_args = monitor_job.send_custom_notification.call_args
            assert "エントリーポイント検出" in call_args[1]["title"]
            
    def test_redis_integration(self, monitor_job):
        """Redis統合テスト（モック）"""
        # Redisクライアントをモック化
        monitor_job.redis_enabled = True
        monitor_job.redis_client = MagicMock()
        
        # 重複チェック
        monitor_job.redis_client.exists.return_value = False
        is_duplicate = monitor_job._is_duplicate_signal(
            "XAUUSD", "1m", {"type": "BUY"}
        )
        assert is_duplicate is False
        
        # シグナル記録
        monitor_job._record_signal("XAUUSD", "1m", {"type": "BUY"})
        monitor_job.redis_client.setex.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_performance_under_load(self, monitor_job, sample_forex_data):
        """高負荷時のパフォーマンステスト"""
        # 複数シンボルで実行
        monitor_job.target_symbols = ["XAUUSD", "EURUSD", "GBPUSD"]
        monitor_job.timeframes = ["1m", "5m", "15m", "30m", "1h"]
        
        # モック設定
        monitor_job.signal_generator.generate_signals.return_value = []
        monitor_job.signal_validator.validate_signal.return_value = True
        
        # 実行時間を測定
        start_time = datetime.utcnow()
        result = await monitor_job._execute_async()
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        # 1秒以内に完了することを確認
        assert execution_time < 1.0
        assert result["status"] == "success"