"""エントリーシグナル生成のユニットテスト"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from src.services.entry_point.signal_generation.entry_signal_generator import EntrySignalGenerator
from src.domain.models.pattern import PatternSignal, PatternType
from src.domain.models.entry_signal import SignalDirection, OrderType
from src.domain.models.zone import ZoneType
from src.domain.models.scoring import ScoringResult
from tests.utils import SignalFactory, ZoneFactory, CandlestickFactory


class TestEntrySignalGenerator:
    """エントリーシグナル生成器のテスト"""
    
    @pytest.fixture
    def generator(self):
        """生成器インスタンス"""
        config = {
            "min_confidence": 70.0,
            "default_validity_hours": 2,
            "max_slippage_pips": 2.0
        }
        return EntrySignalGenerator(config)
    
    @pytest.fixture
    def sample_pattern_signal(self):
        """サンプルパターンシグナル"""
        return SignalFactory.create_pattern_signal(
            pattern_type=PatternType.V_SHAPE_REVERSAL,
            confidence=85.0,
            direction="bullish"
        )
    
    @pytest.fixture
    def sample_scoring_result(self):
        """サンプルスコアリング結果"""
        return ScoringResult(
            pattern_id="test_pattern_001",
            timestamp=datetime.now(timezone.utc),
            total_score=82.5,
            score_breakdown={
                "pattern_quality": 85.0,
                "zone_proximity": 80.0,
                "trend_alignment": 75.0,
                "momentum": 90.0
            },
            confidence=85.0,
            recommendation="STRONG_ENTRY",
            metadata={
                "zone_type": "support",
                "trend_strength": 0.75
            }
        )
    
    @pytest.fixture
    def sample_priority_result(self):
        """サンプル優先順位結果"""
        return {
            "priority": "high",
            "rank": 1,
            "score": 85.0,
            "execution_mode": "immediate"
        }
    
    def test_generate_long_signal(self, generator, sample_pattern_signal, sample_scoring_result, sample_priority_result):
        """ロングシグナルの生成テスト"""
        market_data = {
            "current_price": Decimal("3275.50"),
            "spread": 2.5,
            "zones": ZoneFactory.create_major_zones()
        }
        
        signals = generator.generate(
            pattern_signals=[sample_pattern_signal],
            scoring_results=[sample_scoring_result],
            priority_results=[sample_priority_result],
            market_data=market_data
        )
        
        assert len(signals) == 1
        signal = signals[0]
        
        # 基本属性の検証
        assert signal.symbol == "XAUUSD"
        assert signal.direction == SignalDirection.LONG
        assert signal.entry.order_type == OrderType.MARKET
        
        # 価格の検証
        assert signal.entry.price == Decimal("3275.50")
        assert signal.stop_loss.price < signal.entry.price  # ロングのSLはエントリー以下
        assert all(tp.price > signal.entry.price for tp in signal.take_profits)  # TPはエントリー以上
        
        # メタデータの検証
        assert signal.metadata.pattern_type == "V_SHAPE_REVERSAL"
        assert signal.metadata.confidence_score == 0.85
        
        # 実行情報の検証
        assert signal.execution.priority == "high"
        assert signal.execution.execution_mode == "immediate"
    
    def test_generate_short_signal(self, generator):
        """ショートシグナルの生成テスト"""
        pattern = SignalFactory.create_pattern_signal(
            pattern_type=PatternType.FALSE_BREAKOUT,
            direction="bearish"
        )
        pattern.entry_point = Decimal("3280.00")
        
        scoring = ScoringResult(
            pattern_id="test_002",
            timestamp=datetime.now(timezone.utc),
            total_score=78.0,
            score_breakdown={},
            confidence=78.0,
            recommendation="ENTRY"
        )
        
        priority = {"priority": "medium", "rank": 2, "score": 78.0}
        
        market_data = {
            "current_price": Decimal("3280.00"),
            "spread": 2.0,
            "zones": []
        }
        
        signals = generator.generate(
            pattern_signals=[pattern],
            scoring_results=[scoring],
            priority_results=[priority],
            market_data=market_data
        )
        
        assert len(signals) == 1
        signal = signals[0]
        
        assert signal.direction == SignalDirection.SHORT
        assert signal.stop_loss.price > signal.entry.price  # ショートのSLはエントリー以上
        assert all(tp.price < signal.entry.price for tp in signal.take_profits)  # TPはエントリー以下
    
    def test_risk_reward_calculation(self, generator, sample_pattern_signal, sample_scoring_result, sample_priority_result):
        """リスクリワード計算のテスト"""
        market_data = {
            "current_price": Decimal("3275.50"),
            "spread": 2.0,
            "zones": []
        }
        
        signals = generator.generate(
            pattern_signals=[sample_pattern_signal],
            scoring_results=[sample_scoring_result],
            priority_results=[sample_priority_result],
            market_data=market_data
        )
        
        signal = signals[0]
        
        # RR情報の検証
        assert signal.risk_reward.risk_pips > 0
        assert signal.risk_reward.tp1_reward_pips > 0
        assert signal.risk_reward.tp1_rr_ratio > 0
        assert signal.risk_reward.weighted_rr_ratio >= 1.0  # 最小RR比
        
        # TP割合の合計が100%
        total_percentage = sum(tp.percentage for tp in signal.take_profits)
        assert abs(total_percentage - 100.0) < 0.01