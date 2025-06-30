"""
Integration tests for SignalDetector
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.batch.signal_detection import SignalDetector, ValidatedSignal, SignalPriority
from src.services.entry_point.signal_generation import EntrySignalGenerator
from src.services.entry_point.signal_validation import SignalValidationService


class TestSignalDetectorIntegration:
    """SignalDetectorの統合テスト"""
    
    @pytest.fixture
    def detector(self):
        """SignalDetectorのフィクスチャ"""
        detector = SignalDetector()
        # 実際のサービスインスタンスを使用（モックしない）
        return detector
        
    @pytest.fixture
    def sample_signals(self):
        """テスト用シグナルセット"""
        return [
            {
                'type': 'BUY',
                'score': 85.0,
                'entry_price': 1850.0,
                'current_price': 1851.0,
                'risk_reward_ratio': 3.0,
                'stop_loss': 1845.0,
                'take_profit': 1865.0
            },
            {
                'type': 'SELL',
                'score': 75.0,
                'entry_price': 1852.0,
                'current_price': 1851.5,
                'risk_reward_ratio': 2.0,
                'stop_loss': 1855.0,
                'take_profit': 1846.0
            },
            {
                'type': 'BUY',
                'score': 60.0,  # 閾値以下
                'entry_price': 1849.0,
                'current_price': 1849.1,
                'risk_reward_ratio': 1.5
            }
        ]
        
    @pytest.mark.asyncio
    async def test_full_validation_flow(self, detector, sample_signals):
        """完全な検証フローのテスト"""
        # 市場時間内に設定
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 0, 0)  # NY市場時間
            
            # 実際のSignalValidationServiceをモック（簡易化のため）
            with patch.object(detector.validation_service, 'validate_signal', return_value=True):
                result = await detector.detect_and_validate(
                    raw_signals=sample_signals,
                    timeframe="15m",
                    symbol="XAUUSD"
                )
                
                # 2つのシグナルが通過（60点のシグナルは除外）
                assert len(result) == 2
                
                # 最初のシグナル（HIGH優先度）
                assert result[0].confidence_score == 85.0
                assert result[0].priority == SignalPriority.HIGH
                assert result[0].metadata['symbol'] == "XAUUSD"
                assert result[0].metadata['validation_layers_passed'] == 4
                
                # 2番目のシグナル（MEDIUM優先度）
                assert result[1].confidence_score == 75.0
                assert result[1].priority == SignalPriority.MEDIUM
                
    @pytest.mark.asyncio
    async def test_market_hours_filtering(self, detector, sample_signals):
        """市場時間によるフィルタリングの統合テスト"""
        with patch.object(detector.validation_service, 'validate_signal', return_value=True):
            # 市場時間内（ロンドン/NY重複時間）
            with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
                mock_dt.utcnow.return_value = datetime(2024, 1, 1, 15, 0, 0)
                
                result_active = await detector.detect_and_validate(
                    raw_signals=sample_signals[:1],
                    timeframe="1h",
                    symbol="XAUUSD"
                )
                assert len(result_active) == 1
                assert "london" in result_active[0].metadata['market_session']
                assert "newyork" in result_active[0].metadata['market_session']
                
            # 市場時間外
            with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
                mock_dt.utcnow.return_value = datetime(2024, 1, 1, 23, 30, 0)
                
                result_closed = await detector.detect_and_validate(
                    raw_signals=sample_signals[:1],
                    timeframe="1h",
                    symbol="XAUUSD"
                )
                assert len(result_closed) == 0
                
    @pytest.mark.asyncio
    async def test_duplicate_prevention(self, detector, sample_signals):
        """重複防止機能の統合テスト"""
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 0, 0)
            
            with patch.object(detector.validation_service, 'validate_signal', return_value=True):
                # 最初のバッチ
                result1 = await detector.detect_and_validate(
                    raw_signals=sample_signals[:1],
                    timeframe="5m",
                    symbol="XAUUSD"
                )
                assert len(result1) == 1
                
                # 3分後に同じシグナル（重複）
                mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 3, 0)
                result2 = await detector.detect_and_validate(
                    raw_signals=sample_signals[:1],
                    timeframe="5m",
                    symbol="XAUUSD"
                )
                assert len(result2) == 0
                
                # 6分後（時間間隔クリア）
                mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 6, 0)
                result3 = await detector.detect_and_validate(
                    raw_signals=sample_signals[:1],
                    timeframe="5m",
                    symbol="XAUUSD"
                )
                assert len(result3) == 1
                
    @pytest.mark.asyncio
    async def test_priority_sorting_and_summary(self, detector, sample_signals):
        """優先度ソートとサマリーの統合テスト"""
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 0, 0)
            
            with patch.object(detector.validation_service, 'validate_signal', return_value=True):
                # 異なる優先度のシグナルを生成
                mixed_signals = [
                    {
                        'type': 'BUY',
                        'score': 70.0,
                        'entry_price': 1850.0,
                        'current_price': 1850.5,
                        'risk_reward_ratio': 1.2
                    },
                    {
                        'type': 'SELL',
                        'score': 90.0,
                        'entry_price': 1852.0,
                        'current_price': 1851.0,
                        'risk_reward_ratio': 3.5
                    },
                    {
                        'type': 'BUY',
                        'score': 80.0,
                        'entry_price': 1849.0,
                        'current_price': 1849.8,
                        'risk_reward_ratio': 1.8
                    }
                ]
                
                result = await detector.detect_and_validate(
                    raw_signals=mixed_signals,
                    timeframe="30m",
                    symbol="XAUUSD"
                )
                
                assert len(result) == 3
                
                # サマリーの検証
                summary = detector.get_validation_summary(result)
                assert summary['total_validated'] == 3
                assert summary['by_priority']['high'] == 1  # 90点
                assert summary['by_priority']['medium'] == 1  # 80点
                assert summary['by_priority']['low'] == 1  # 70点
                assert 78.0 < summary['average_score'] < 82.0  # (70+90+80)/3
                
    @pytest.mark.asyncio
    async def test_error_handling(self, detector):
        """エラーハンドリングの統合テスト"""
        # 不正なシグナルデータ
        invalid_signals = [
            {'score': 75.0},  # typeとentry_priceが不足
            {'type': 'INVALID', 'score': 80.0, 'entry_price': 1850.0},  # 無効なタイプ
            None  # Noneデータ
        ]
        
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 0, 0)
            
            # エラーが発生してもクラッシュしないことを確認
            try:
                result = await detector.detect_and_validate(
                    raw_signals=invalid_signals,
                    timeframe="1m",
                    symbol="XAUUSD"
                )
                # 有効なシグナルがないので空のリスト
                assert len(result) == 0
            except Exception as e:
                pytest.fail(f"Unexpected exception: {e}")
                
    @pytest.mark.asyncio
    async def test_performance_with_many_signals(self, detector):
        """多数のシグナルでのパフォーマンステスト"""
        # 100個のシグナルを生成
        many_signals = []
        for i in range(100):
            many_signals.append({
                'type': 'BUY' if i % 2 == 0 else 'SELL',
                'score': 65.0 + (i % 30),  # 65-94の範囲
                'entry_price': 1850.0 + i * 0.1,
                'current_price': 1850.0 + i * 0.1 + 0.5,
                'risk_reward_ratio': 1.5 + (i % 3) * 0.5
            })
            
        with patch('src.batch.signal_detection.signal_detector.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 14, 0, 0)
            
            with patch.object(detector.validation_service, 'validate_signal', return_value=True):
                start_time = datetime.utcnow()
                result = await detector.detect_and_validate(
                    raw_signals=many_signals,
                    timeframe="1m",
                    symbol="XAUUSD"
                )
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                # パフォーマンス確認
                assert execution_time < 1.0  # 1秒以内に完了
                assert len(result) > 0  # 少なくともいくつかのシグナルが通過