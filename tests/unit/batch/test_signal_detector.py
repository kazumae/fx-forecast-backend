"""
Unit tests for SignalDetector
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

from src.batch.signal_detection import SignalDetector, ValidatedSignal, SignalPriority


class TestSignalDetector:
    """SignalDetectorのテスト"""
    
    @pytest.fixture
    def detector(self):
        """SignalDetectorのフィクスチャ"""
        with patch('src.batch.signal_detection.signal_detector.SignalValidationService'):
            detector = SignalDetector()
            detector.validation_service = MagicMock()
            detector.validation_service.validate_signal.return_value = True
            return detector
            
    @pytest.fixture
    def sample_signal(self):
        """サンプルシグナル"""
        return {
            'type': 'BUY',
            'score': 75.0,
            'entry_price': 1850.0,
            'current_price': 1852.0,  # 0.108%の変動
            'risk_reward_ratio': 2.5,
            'stop_loss': 1845.0,
            'take_profit': 1862.5
        }
        
    @pytest.mark.asyncio
    async def test_detect_and_validate_basic(self, detector, sample_signal):
        """基本的な検出と検証のテスト"""
        # 市場時間内に設定
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 0, 0)  # NY市場時間
            
            result = await detector.detect_and_validate(
                raw_signals=[sample_signal],
                timeframe="15m",
                symbol="XAUUSD"
            )
            
            assert len(result) == 1
            validated = result[0]
            assert isinstance(validated, ValidatedSignal)
            assert validated.confidence_score == 75.0
            assert validated.priority == SignalPriority.MEDIUM
            assert validated.metadata['symbol'] == "XAUUSD"
            assert validated.metadata['timeframe'] == "15m"
            
    @pytest.mark.asyncio
    async def test_score_threshold_filtering(self, detector, sample_signal):
        """スコア閾値によるフィルタリングテスト"""
        # 閾値以下のシグナル
        low_score_signal = sample_signal.copy()
        low_score_signal['score'] = 60.0
        
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 0, 0)
            
            result = await detector.detect_and_validate(
                raw_signals=[low_score_signal],
                timeframe="15m",
                symbol="XAUUSD"
            )
            
            assert len(result) == 0  # フィルタリングされる
            
    @pytest.mark.asyncio
    async def test_time_interval_check(self, detector, sample_signal):
        """時間間隔チェックのテスト"""
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 0, 0)
            
            # 最初のシグナル
            result1 = await detector.detect_and_validate(
                raw_signals=[sample_signal],
                timeframe="15m",
                symbol="XAUUSD"
            )
            assert len(result1) == 1
            
            # 同じシグナルを3分後に再度送信
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 3, 0)
            result2 = await detector.detect_and_validate(
                raw_signals=[sample_signal],
                timeframe="15m",
                symbol="XAUUSD"
            )
            assert len(result2) == 0  # 5分以内なので除外
            
            # 6分後に送信
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 6, 0)
            result3 = await detector.detect_and_validate(
                raw_signals=[sample_signal],
                timeframe="15m",
                symbol="XAUUSD"
            )
            assert len(result3) == 1  # 5分経過したので通過
            
    @pytest.mark.asyncio
    async def test_market_hours_check(self, detector, sample_signal):
        """市場時間チェックのテスト"""
        # 市場クローズ時間（23:00 UTC）
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 23, 0, 0)
            
            result = await detector.detect_and_validate(
                raw_signals=[sample_signal],
                timeframe="15m",
                symbol="XAUUSD"
            )
            
            assert len(result) == 0  # 市場時間外なので除外
            
    @pytest.mark.asyncio
    async def test_price_movement_check(self, detector, sample_signal):
        """価格変動幅チェックのテスト"""
        # 価格変動が小さいシグナル
        small_move_signal = sample_signal.copy()
        small_move_signal['current_price'] = 1850.01  # 0.01の変動
        
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 0, 0)
            
            result = await detector.detect_and_validate(
                raw_signals=[small_move_signal],
                timeframe="15m",
                symbol="XAUUSD"
            )
            
            assert len(result) == 0  # 最小変動幅以下なので除外
            
    def test_priority_calculation(self, detector):
        """優先度計算のテスト"""
        # HIGH優先度
        high_signal = {'score': 90.0, 'risk_reward_ratio': 3.0}
        assert detector._calculate_priority(high_signal) == SignalPriority.HIGH
        
        # MEDIUM優先度
        medium_signal = {'score': 78.0, 'risk_reward_ratio': 1.2}
        assert detector._calculate_priority(medium_signal) == SignalPriority.MEDIUM
        
        # LOW優先度
        low_signal = {'score': 70.0, 'risk_reward_ratio': 1.0}
        assert detector._calculate_priority(low_signal) == SignalPriority.LOW
        
    def test_get_market_session(self, detector):
        """市場セッション取得のテスト"""
        # 東京市場
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 3, 0, 0)
            assert detector._get_market_session() == "tokyo"
            
        # ロンドン市場
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 10, 0, 0)
            assert detector._get_market_session() == "london"
            
        # ニューヨーク市場
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 18, 0, 0)
            assert detector._get_market_session() == "newyork"
            
        # ロンドン/ニューヨーク重複
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 15, 0, 0)
            session = detector._get_market_session()
            assert "london" in session
            assert "newyork" in session
            
    @pytest.mark.asyncio
    async def test_basic_validation_failure(self, detector):
        """基本検証失敗のテスト"""
        # 必須フィールド不足
        invalid_signal = {'score': 75.0}  # typeとentry_priceが不足
        
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 0, 0)
            
            result = await detector.detect_and_validate(
                raw_signals=[invalid_signal],
                timeframe="15m",
                symbol="XAUUSD"
            )
            
            assert len(result) == 0
            
    def test_get_validation_summary(self, detector):
        """検証サマリー取得のテスト"""
        # 空のリスト
        summary = detector.get_validation_summary([])
        assert summary['total_validated'] == 0
        assert summary['average_score'] == 0
        
        # 複数の検証済みシグナル
        validated_signals = [
            ValidatedSignal(
                signal={'type': 'BUY'},
                detected_at=datetime.utcnow(),
                confidence_score=85.0,
                priority=SignalPriority.HIGH,
                metadata={'market_session': 'london'}
            ),
            ValidatedSignal(
                signal={'type': 'SELL'},
                detected_at=datetime.utcnow(),
                confidence_score=75.0,
                priority=SignalPriority.MEDIUM,
                metadata={'market_session': 'newyork'}
            ),
            ValidatedSignal(
                signal={'type': 'BUY'},
                detected_at=datetime.utcnow(),
                confidence_score=70.0,
                priority=SignalPriority.LOW,
                metadata={'market_session': 'london'}
            )
        ]
        
        summary = detector.get_validation_summary(validated_signals)
        assert summary['total_validated'] == 3
        assert summary['by_priority']['high'] == 1
        assert summary['by_priority']['medium'] == 1
        assert summary['by_priority']['low'] == 1
        assert abs(summary['average_score'] - 76.67) < 0.01  # (85+75+70)/3
        assert 'london' in summary['market_sessions']
        assert 'newyork' in summary['market_sessions']