"""
Integration tests for DuplicateSignalManager
"""
import pytest
import redis
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from src.batch.duplicate_management import DuplicateSignalManager
from src.batch.signal_detection import ValidatedSignal, SignalPriority, SignalDetector
from src.batch.jobs.signal_monitor import SignalMonitorJob


class TestDuplicateSignalManagerIntegration:
    """DuplicateSignalManagerの統合テスト"""
    
    @pytest.fixture
    def redis_client(self):
        """テスト用Redisクライアント"""
        # テスト用のRedisデータベース（DB 15）を使用
        try:
            client = redis.from_url("redis://localhost:6379/15", decode_responses=True)
            # テスト開始前にクリーンアップ
            client.flushdb()
            yield client
            # テスト後にクリーンアップ
            client.flushdb()
        except redis.ConnectionError:
            pytest.skip("Redis not available")
            
    @pytest.fixture
    def manager(self, redis_client):
        """DuplicateSignalManagerのフィクスチャ"""
        return DuplicateSignalManager(redis_client)
        
    @pytest.fixture
    def sample_signals(self):
        """テスト用シグナルセット"""
        return [
            ValidatedSignal(
                signal={
                    'type': 'BUY',
                    'entry_price': 1850.0,
                    'pattern_type': 'bullish_reversal',
                    'score': 85.0
                },
                detected_at=datetime.utcnow(),
                confidence_score=85.0,
                priority=SignalPriority.HIGH,
                metadata={
                    'symbol': 'XAUUSD',
                    'timeframe': '15m'
                }
            ),
            ValidatedSignal(
                signal={
                    'type': 'BUY',
                    'entry_price': 1850.4,  # 同じ1850に丸められる
                    'pattern_type': 'bullish_reversal',
                    'score': 80.0
                },
                detected_at=datetime.utcnow(),
                confidence_score=80.0,
                priority=SignalPriority.MEDIUM,
                metadata={
                    'symbol': 'XAUUSD',
                    'timeframe': '15m'
                }
            ),
            ValidatedSignal(
                signal={
                    'type': 'SELL',
                    'entry_price': 1855.0,
                    'pattern_type': 'bearish_reversal',
                    'score': 75.0
                },
                detected_at=datetime.utcnow(),
                confidence_score=75.0,
                priority=SignalPriority.MEDIUM,
                metadata={
                    'symbol': 'XAUUSD',
                    'timeframe': '15m'
                }
            )
        ]
        
    def test_duplicate_detection_flow(self, manager, sample_signals):
        """重複検出フローの統合テスト"""
        # 最初のシグナル（新規）
        assert manager.is_duplicate(sample_signals[0]) is False
        
        # 同じシグナルを再度送信（重複）
        assert manager.is_duplicate(sample_signals[0]) is True
        
        # 価格が微妙に異なるが許容範囲内（重複）
        assert manager.is_duplicate(sample_signals[1]) is True
        
        # 異なるタイプのシグナル（新規）
        assert manager.is_duplicate(sample_signals[2]) is False
        
    @pytest.mark.asyncio
    async def test_statistics_accumulation(self, manager, sample_signals):
        """統計情報の蓄積テスト"""
        # 複数のシグナルを処理
        for signal in sample_signals * 3:  # 各シグナルを3回送信
            manager.is_duplicate(signal)
            
        # 統計を確認
        stats = await manager.get_duplicate_stats("15m")
        
        assert stats['total_signals'] == 2  # ユニークなシグナル数（BUYとSELL）
        assert stats['duplicate_signals'] == 7  # 重複数
        assert abs(stats['duplicate_rate'] - 77.78) < 0.01  # 重複率
        
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, redis_client):
        """TTL期限切れのテスト"""
        # TTLを短く設定したマネージャーを作成
        manager = DuplicateSignalManager(redis_client)
        manager.ttl_seconds = 1
        
        signal = ValidatedSignal(
            signal={'type': 'BUY', 'entry_price': 1850.0, 'pattern_type': 'test'},
            detected_at=datetime.utcnow(),
            confidence_score=80.0,
            priority=SignalPriority.MEDIUM,
            metadata={'symbol': 'XAUUSD', 'timeframe': '1m'}
        )
        
        # シグナルを登録
        assert manager.is_duplicate(signal) is False
        
        # 再度チェック（重複）
        assert manager.is_duplicate(signal) is True
        
        # 2秒待機
        import time
        time.sleep(2)
        
        # TTL期限切れ後は新規として扱われる
        assert manager.is_duplicate(signal) is False
        
    def test_concurrent_access(self, manager, sample_signals):
        """並行アクセスのテスト"""
        import threading
        results = []
        
        def check_duplicate(signal, idx):
            result = manager.is_duplicate(signal)
            results.append((idx, result))
            
        # 10スレッドで同じシグナルをチェック
        threads = []
        for i in range(10):
            t = threading.Thread(target=check_duplicate, args=(sample_signals[0], i))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        # 最初の1つだけがFalse、残りはTrue
        false_count = sum(1 for _, result in results if not result)
        true_count = sum(1 for _, result in results if result)
        
        assert false_count == 1
        assert true_count == 9
        
    @pytest.mark.asyncio
    async def test_signal_monitor_integration(self, redis_client):
        """SignalMonitorJobとの統合テスト"""
        with patch('src.batch.jobs.signal_monitor.redis.from_url') as mock_redis:
            mock_redis.return_value = redis_client
            
            monitor = SignalMonitorJob()
            assert monitor.duplicate_manager.enabled is True
            
            # テスト用シグナル
            test_signal = ValidatedSignal(
                signal={'type': 'BUY', 'entry_price': 1850.0, 'score': 80.0},
                detected_at=datetime.utcnow(),
                confidence_score=80.0,
                priority=SignalPriority.MEDIUM,
                metadata={'symbol': 'XAUUSD', 'timeframe': '1m'}
            )
            
            # 最初は重複なし
            assert monitor.duplicate_manager.is_duplicate(test_signal) is False
            
            # 2回目は重複
            assert monitor.duplicate_manager.is_duplicate(test_signal) is True
            
            # 統計確認
            stats = await monitor.duplicate_manager.get_duplicate_stats("1m")
            assert stats['total_signals'] == 1
            assert stats['duplicate_signals'] == 1
            
    def test_recent_signals_retrieval(self, manager, sample_signals):
        """最近のシグナル取得の統合テスト"""
        # 複数のシグナルを登録
        for signal in sample_signals:
            manager.is_duplicate(signal)
            
        # 最近のシグナルを取得
        recent = manager.get_recent_signals(limit=10)
        
        assert len(recent) == 2  # BUYは重複で1つ、SELLで1つ
        assert all('ttl_remaining' in s for s in recent)
        assert all('fingerprint' in s for s in recent)
        
    @pytest.mark.asyncio
    async def test_daily_statistics(self, manager, sample_signals):
        """日次統計の統合テスト"""
        # 今日の日付
        today = datetime.utcnow().strftime('%Y%m%d')
        
        # シグナルを処理
        for signal in sample_signals * 2:
            manager.is_duplicate(signal)
            
        # 日次統計を確認
        daily_stats = await manager.get_daily_stats(today)
        
        assert daily_stats['date'] == today
        assert daily_stats['total_signals'] == 2  # ユニークなシグナル（BUYとSELL）
        assert daily_stats['duplicate_signals'] == 4  # 重複（各シグナル2回の重複）
        
    def test_clear_statistics(self, manager, sample_signals):
        """統計クリアの統合テスト"""
        # データを蓄積
        for signal in sample_signals:
            manager.is_duplicate(signal)
            
        # クリア前の確認
        stats_before = manager.redis.get("signal_count:15m")
        assert int(stats_before or 0) > 0
        
        # 統計をクリア
        manager.clear_stats()
        
        # クリア後の確認
        stats_after = manager.redis.get("signal_count:15m")
        assert stats_after is None