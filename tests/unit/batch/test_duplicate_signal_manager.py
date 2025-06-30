"""
Unit tests for DuplicateSignalManager
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime
from decimal import Decimal

from src.batch.duplicate_management import DuplicateSignalManager
from src.batch.signal_detection import ValidatedSignal, SignalPriority


class TestDuplicateSignalManager:
    """DuplicateSignalManagerのテスト"""
    
    @pytest.fixture
    def redis_mock(self):
        """Redisクライアントのモック"""
        mock = MagicMock()
        mock.exists.return_value = False
        mock.setex.return_value = True
        mock.incr.return_value = 1
        mock.get.return_value = 0
        mock.scan_iter.return_value = []
        return mock
        
    @pytest.fixture
    def manager(self, redis_mock):
        """DuplicateSignalManagerのフィクスチャ"""
        return DuplicateSignalManager(redis_mock)
        
    @pytest.fixture
    def sample_signal(self):
        """サンプルValidatedSignal"""
        return ValidatedSignal(
            signal={
                'type': 'BUY',
                'entry_price': 1850.0,
                'pattern_type': 'bullish_reversal'
            },
            detected_at=datetime.utcnow(),
            confidence_score=80.0,
            priority=SignalPriority.MEDIUM,
            metadata={
                'symbol': 'XAUUSD',
                'timeframe': '15m'
            }
        )
        
    def test_initialization(self, manager):
        """初期化のテスト"""
        assert manager.ttl_seconds == 300
        assert manager.price_tolerance == Decimal("0.001")
        assert manager.enabled is True
        
    def test_initialization_without_redis(self):
        """Redis無しでの初期化テスト"""
        manager = DuplicateSignalManager(None)
        assert manager.enabled is False
        
    def test_is_duplicate_new_signal(self, manager, sample_signal, redis_mock):
        """新規シグナルの重複チェック"""
        redis_mock.exists.return_value = False
        
        result = manager.is_duplicate(sample_signal)
        
        assert result is False
        assert redis_mock.exists.called
        assert redis_mock.setex.called
        assert redis_mock.incr.called
        
    def test_is_duplicate_existing_signal(self, manager, sample_signal, redis_mock):
        """既存シグナルの重複チェック"""
        redis_mock.exists.return_value = True
        
        result = manager.is_duplicate(sample_signal)
        
        assert result is True
        assert redis_mock.exists.called
        assert not redis_mock.setex.called  # 新規登録はされない
        assert redis_mock.incr.called  # 重複カウンターは増加
        
    def test_is_duplicate_disabled(self, sample_signal):
        """無効状態での重複チェック"""
        manager = DuplicateSignalManager(None)
        
        result = manager.is_duplicate(sample_signal)
        
        assert result is False
        
    def test_generate_fingerprint(self, manager, sample_signal):
        """フィンガープリント生成のテスト"""
        fingerprint = manager._generate_fingerprint(sample_signal)
        
        assert fingerprint.startswith("signal:fp:")
        assert len(fingerprint) > 20
        
        # 同じシグナルは同じフィンガープリント
        fingerprint2 = manager._generate_fingerprint(sample_signal)
        assert fingerprint == fingerprint2
        
    def test_generate_fingerprint_different_signals(self, manager):
        """異なるシグナルのフィンガープリント"""
        signal1 = ValidatedSignal(
            signal={'type': 'BUY', 'entry_price': 1850.0},
            detected_at=datetime.utcnow(),
            confidence_score=80.0,
            priority=SignalPriority.MEDIUM,
            metadata={'symbol': 'XAUUSD', 'timeframe': '15m'}
        )
        
        signal2 = ValidatedSignal(
            signal={'type': 'SELL', 'entry_price': 1850.0},
            detected_at=datetime.utcnow(),
            confidence_score=80.0,
            priority=SignalPriority.MEDIUM,
            metadata={'symbol': 'XAUUSD', 'timeframe': '15m'}
        )
        
        fp1 = manager._generate_fingerprint(signal1)
        fp2 = manager._generate_fingerprint(signal2)
        
        assert fp1 != fp2
        
    def test_round_price(self, manager):
        """価格丸めのテスト"""
        # 0.1%単位で丸める
        assert manager._round_price(Decimal("1850.0")) == Decimal("1850.0")
        assert manager._round_price(Decimal("1850.5")) == Decimal("1851.0")
        assert manager._round_price(Decimal("1849.5")) == Decimal("1850.0")
        assert manager._round_price(Decimal("0")) == Decimal("0")
        
    def test_price_tolerance(self, manager):
        """価格許容誤差のテスト"""
        # 同じ値に丸められるケース
        signal1 = ValidatedSignal(
            signal={'type': 'BUY', 'entry_price': 1850.0},
            detected_at=datetime.utcnow(),
            confidence_score=80.0,
            priority=SignalPriority.MEDIUM,
            metadata={'symbol': 'XAUUSD', 'timeframe': '15m'}
        )
        
        signal2 = ValidatedSignal(
            signal={'type': 'BUY', 'entry_price': 1850.4},  # 同じ1850に丸められる
            detected_at=datetime.utcnow(),
            confidence_score=80.0,
            priority=SignalPriority.MEDIUM,
            metadata={'symbol': 'XAUUSD', 'timeframe': '15m'}
        )
        
        fp1 = manager._generate_fingerprint(signal1)
        fp2 = manager._generate_fingerprint(signal2)
        
        # 丸められて同じになる
        assert fp1 == fp2
        
        # 異なる値に丸められるケース
        signal3 = ValidatedSignal(
            signal={'type': 'BUY', 'entry_price': 1851.8},  # 1852に丸められる
            detected_at=datetime.utcnow(),
            confidence_score=80.0,
            priority=SignalPriority.MEDIUM,
            metadata={'symbol': 'XAUUSD', 'timeframe': '15m'}
        )
        
        fp3 = manager._generate_fingerprint(signal3)
        
        # 異なるフィンガープリント
        assert fp1 != fp3
        
    @pytest.mark.asyncio
    async def test_get_duplicate_stats(self, manager, redis_mock):
        """重複統計取得のテスト"""
        redis_mock.get.side_effect = lambda key: {
            "signal_count:15m": "10",
            "duplicate_count:15m": "3"
        }.get(key, "0")
        
        stats = await manager.get_duplicate_stats("15m")
        
        assert stats['total_signals'] == 10
        assert stats['duplicate_signals'] == 3
        assert stats['duplicate_rate'] == 30.0
        assert stats['timeframe'] == "15m"
        assert stats['redis_enabled'] is True
        
    @pytest.mark.asyncio
    async def test_get_duplicate_stats_all(self, manager, redis_mock):
        """全時間軸の重複統計取得"""
        redis_mock.get.side_effect = lambda key: {
            "signal_count:1m": "5",
            "signal_count:15m": "10",
            "signal_count:1h": "3",
            "duplicate_count:1m": "1",
            "duplicate_count:15m": "3",
            "duplicate_count:1h": "1"
        }.get(key, "0")
        
        stats = await manager.get_duplicate_stats()
        
        assert stats['total_signals'] == 18  # 5+10+3
        assert stats['duplicate_signals'] == 5  # 1+3+1
        assert abs(stats['duplicate_rate'] - 27.78) < 0.01
        assert stats['timeframe'] == "all"
        
    @pytest.mark.asyncio
    async def test_get_daily_stats(self, manager, redis_mock):
        """日次統計取得のテスト"""
        date = "20240101"
        redis_mock.get.side_effect = lambda key: {
            f"signal_count:daily:{date}": "50",
            f"duplicate_count:daily:{date}": "10"
        }.get(key, "0")
        
        stats = await manager.get_daily_stats(date)
        
        assert stats['date'] == date
        assert stats['total_signals'] == 50
        assert stats['duplicate_signals'] == 10
        assert stats['duplicate_rate'] == 20.0
        
    def test_clear_stats(self, manager, redis_mock):
        """統計クリアのテスト"""
        redis_mock.scan_iter.side_effect = [
            ["signal_count:1m", "signal_count:15m"],
            ["duplicate_count:1m", "duplicate_count:15m"]
        ]
        
        manager.clear_stats()
        
        assert redis_mock.delete.call_count == 4
        
    def test_get_recent_signals(self, manager, redis_mock):
        """最近のシグナル取得のテスト"""
        signal_data = {
            "signal": {"type": "BUY"},
            "detected_at": "2024-01-01T12:00:00",
            "confidence_score": 80.0
        }
        
        redis_mock.scan_iter.return_value = ["signal:fp:abc123"]
        redis_mock.ttl.return_value = 120
        redis_mock.get.return_value = json.dumps(signal_data)
        
        signals = manager.get_recent_signals(limit=5)
        
        assert len(signals) == 1
        assert signals[0]['signal']['type'] == "BUY"
        assert signals[0]['ttl_remaining'] == 120
        assert signals[0]['fingerprint'] == "signal:fp:abc123"