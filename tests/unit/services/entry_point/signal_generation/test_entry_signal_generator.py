import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock
from src.services.entry_point.signal_generation.entry_signal_generator import EntrySignalGenerator
from src.domain.models.entry_signal import SignalDirection, OrderType, SignalConfidence
from src.domain.models.pattern import PatternType, PatternSignal
from src.domain.models.scoring import ScoringResult, ScoreComponent, ConfidenceLevel


class TestEntrySignalGenerator:
    """エントリーシグナル生成器のテストスイート"""
    
    def setup_method(self):
        """各テストの前に実行される初期化"""
        self.generator = EntrySignalGenerator()
        self.mock_pattern_signal = self._create_mock_pattern_signal()
        self.mock_scoring_result = self._create_mock_scoring_result()
        self.mock_ranking_result = self._create_mock_ranking_result()
        self.current_price = Decimal("2034.50")
        self.market_data = {
            "current_price": 2034.50,
            "current_trend": "up",
            "higher_timeframe_trend": "up",
            "volatility": "normal",
            "spread": 2.0,
            "is_market_open": True
        }
    
    def _create_mock_pattern_signal(self) -> PatternSignal:
        """モックパターンシグナルを作成"""
        return PatternSignal(
            id="pattern_001",
            symbol="XAUUSD",
            timeframe="H1",
            pattern_type=PatternType.V_SHAPE_REVERSAL,
            detected_at=datetime.now(),
            price_level=Decimal("2034.50"),
            confidence=85.0,  # 0-100スケール
            parameters={
                "reversal_type": "bullish",
                "immediate_execution": False,
                "indicators": {
                    "rsi": 35,
                    "macd": {"signal": "bullish"},
                    "ema_positions": {"ema_20": 2033.80, "ema_50": 2032.50}
                }
            },
            zone_id="zone_042"
        )
    
    def _create_mock_scoring_result(self) -> ScoringResult:
        """モックスコアリング結果を作成"""
        # ScoringResultを手動で作成（metadataがないため）
        result = ScoringResult(
            total_score=78.0,
            pass_threshold=65.0,
            passed=True,
            score_breakdown=[
                ScoreComponent(
                    name="pattern_clarity",
                    score=24.0,
                    max_score=30.0,
                    weight=0.8,
                    details="High clarity pattern detected",
                    metadata={"clarity_level": "high"}
                ),
                ScoreComponent(
                    name="zone_strength", 
                    score=25.0,
                    max_score=30.0,
                    weight=0.83,
                    details="Strong support zone",
                    metadata={"zone_type": "support"}
                ),
                ScoreComponent(
                    name="other",
                    score=29.0,
                    max_score=40.0,
                    weight=0.725,
                    details="Other factors",
                    metadata={}
                )
            ],
            confidence_level=ConfidenceLevel.MEDIUM,
            timestamp=datetime.now()
        )
        # ScoringResultにはmetadataフィールドがないので、手動で追加
        result.metadata = {
            "is_power_zone": True,
            "power_level": 3,
            "market_conditions": {"trend": "bullish", "volatility": "normal"}
        }
        return result
    
    def _create_mock_ranking_result(self):
        """モック優先順位結果を作成"""
        # PriorityRankingResultの構造が複雑なため、モックを使用
        mock_ranking = Mock()
        mock_ranking.priority_rank = 2
        mock_ranking.priority_score = 85.0
        mock_ranking.execution_method = "LIMIT_ORDER"
        mock_ranking.urgency_level = "HIGH"
        mock_ranking.queue_position = 2
        mock_ranking.total_patterns_evaluated = 5
        mock_ranking.metadata = {
            "immediate_execution": False,
            "bypass_correlation": False,
            "special_conditions": []
        }
        return mock_ranking
    
    def test_generate_signal_success(self):
        """正常なシグナル生成のテスト"""
        signal = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        assert signal is not None
        assert signal.symbol == "XAUUSD"
        assert signal.direction == SignalDirection.LONG  # bullish reversal
        assert signal.entry.type == OrderType.LIMIT
        assert signal.metadata.pattern_type == "V_SHAPE_REVERSAL"
        assert signal.metadata.total_score == 78.0
        assert signal.metadata.priority == 2
    
    def test_entry_price_calculation(self):
        """エントリー価格計算のテスト"""
        signal = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        # 指値注文の場合、現在価格より有利な価格
        assert signal.entry.type == OrderType.LIMIT
        assert signal.entry.price < self.current_price  # ロングの指値は低い価格
        assert signal.entry.slippage_tolerance == 1.0  # 指値のスリッページは小さい
    
    def test_stop_loss_calculation(self):
        """ストップロス計算のテスト"""
        signal = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        # ロングポジションのSLはエントリーより低い
        assert signal.stop_loss.price < signal.entry.price
        
        # リスクが適切な範囲内
        risk_pips = (float(signal.entry.price) - float(signal.stop_loss.price)) * 10000
        assert 5 <= risk_pips <= 50  # 5-50 pipsの範囲
    
    def test_take_profit_calculation(self):
        """テイクプロフィット計算のテスト"""
        signal = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        # デフォルトで3つのTPレベル
        assert len(signal.take_profits) == 3
        
        # ロングポジションのTPはエントリーより高い
        for tp in signal.take_profits:
            assert tp.price > signal.entry.price
        
        # TPは順次高くなる
        for i in range(1, len(signal.take_profits)):
            assert signal.take_profits[i].price > signal.take_profits[i-1].price
        
        # パーセンテージの合計は100%
        total_percentage = sum(tp.percentage for tp in signal.take_profits)
        assert abs(total_percentage - 100) < 0.01
    
    def test_risk_reward_calculation(self):
        """リスクリワード比計算のテスト"""
        signal = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        # RR比が最小要件を満たす
        assert signal.risk_reward.ratio >= 1.0
        assert signal.risk_reward.risk_pips > 0
        assert signal.risk_reward.reward_pips > 0
    
    def test_metadata_construction(self):
        """メタデータ構築のテスト"""
        signal = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        assert signal.metadata.pattern_type == "V_SHAPE_REVERSAL"
        assert signal.metadata.total_score == 78.0
        assert signal.metadata.confidence == SignalConfidence.HIGH
        assert signal.metadata.priority == 2
        assert "V_SHAPE_REVERSAL" in signal.metadata.detected_patterns
        assert signal.metadata.zone_id == "zone_042"
    
    def test_execution_info_construction(self):
        """実行情報構築のテスト"""
        signal = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        assert signal.execution.recommended_size > 0
        assert signal.execution.max_risk_amount == 100.0
        assert signal.execution.entry_method == "limit"
        assert signal.execution.urgency == "normal"
    
    def test_immediate_execution_signal(self):
        """即時実行シグナルのテスト"""
        # 即時実行フラグを設定
        self.mock_ranking_result.metadata["immediate_execution"] = True
        self.mock_ranking_result.execution_method = "MARKET_ORDER"
        
        signal = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        assert signal.entry.type == OrderType.MARKET
        assert signal.execution.entry_method == "market"
        assert signal.execution.urgency == "immediate"
    
    def test_short_direction_signal(self):
        """ショート方向シグナルのテスト"""
        # ベアリッシュリバーサルに変更
        self.mock_pattern_signal.parameters["reversal_type"] = "bearish"
        
        signal = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        assert signal.direction == SignalDirection.SHORT
        
        # ショートポジションの価格関係
        assert signal.stop_loss.price > signal.entry.price
        for tp in signal.take_profits:
            assert tp.price < signal.entry.price
    
    def test_power_zone_adjustment(self):
        """パワーゾーン調整のテスト"""
        # パワーゾーン情報を設定
        self.mock_scoring_result.metadata["is_power_zone"] = True
        self.mock_scoring_result.metadata["power_level"] = 4
        
        signal = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        # パワーゾーンではSLが縮小される
        risk_pips = signal.risk_reward.risk_pips
        assert risk_pips < 20  # デフォルトより小さい
    
    def test_validation_failure(self):
        """検証失敗時のテスト"""
        # 無効な市場データ
        invalid_market_data = {
            "current_price": -100,  # 負の価格
            "is_market_open": False
        }
        
        signal = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            Decimal("-100"),  # 無効な価格
            invalid_market_data
        )
        
        # 検証に失敗してNoneが返される
        assert signal is None
    
    def test_batch_signal_generation(self):
        """バッチシグナル生成のテスト"""
        # 複数のパターンシグナル
        pattern_signals = [
            self.mock_pattern_signal,
            self._create_mock_pattern_signal()
        ]
        pattern_signals[1].id = "pattern_002"
        
        # 対応するスコアリング結果
        scoring_results = {
            "pattern_001": self.mock_scoring_result,
            "pattern_002": self._create_mock_scoring_result()
        }
        
        # 対応する優先順位結果
        ranking_results = {
            "pattern_001": self.mock_ranking_result,
            "pattern_002": self._create_mock_ranking_result()
        }
        
        signals = self.generator.generate_batch_signals(
            pattern_signals,
            scoring_results,
            ranking_results,
            self.market_data
        )
        
        assert len(signals) == 2
        assert all(signal.symbol == "XAUUSD" for signal in signals)
    
    def test_signal_id_uniqueness(self):
        """シグナルIDの一意性テスト"""
        signal1 = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        signal2 = self.generator.generate_signal(
            self.mock_pattern_signal,
            self.mock_scoring_result,
            self.mock_ranking_result,
            self.current_price,
            self.market_data
        )
        
        # IDが異なることを確認
        assert signal1.id != signal2.id
        assert signal1.id.startswith("entry_")
        assert signal2.id.startswith("entry_")