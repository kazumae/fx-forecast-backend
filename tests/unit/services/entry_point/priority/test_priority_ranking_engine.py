"""
Unit tests for Priority Ranking Engine
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from src.services.entry_point.priority.priority_ranking_engine import PriorityRankingEngine
from src.domain.models.priority_ranking import (
    EntrySignal, ExistingPosition, PriorityRankingConfig,
    ExclusionReason
)
from src.domain.models.scoring import (
    ScoringResult, ScoreComponent, PatternType, ConfidenceLevel
)


class TestPriorityRankingEngine:
    """Test cases for priority ranking engine"""
    
    @pytest.fixture
    def default_config(self):
        """Default configuration for tests"""
        return PriorityRankingConfig()
    
    @pytest.fixture
    def engine(self, default_config):
        """Create priority ranking engine instance"""
        return PriorityRankingEngine(default_config)
    
    @pytest.fixture
    def base_timestamp(self):
        """Base timestamp for tests"""
        return datetime(2024, 6, 29, 10, 0, 0)
    
    def create_scoring_result(
        self,
        total_score: float = 75.0,
        confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    ) -> ScoringResult:
        """Helper to create scoring result"""
        # Adjust component scores to match total_score
        factor = total_score / 75.0  # Base total is 75
        components = [
            ScoreComponent("Pattern", 22.0 * factor, 30.0, 0.3, "Test pattern"),
            ScoreComponent("MA", 15.0 * factor, 20.0, 0.2, "Test MA"),
            ScoreComponent("Zone", 20.0 * factor, 25.0, 0.25, "Test zone"),
            ScoreComponent("Price Action", 10.0 * factor, 15.0, 0.15, "Test PA"),
            ScoreComponent("Market Env", 8.0 * factor, 10.0, 0.1, "Test env")
        ]
        
        return ScoringResult(
            total_score=total_score,
            pass_threshold=65.0,
            passed=total_score >= 65.0,
            score_breakdown=components,
            confidence_level=confidence_level,
            timestamp=datetime.utcnow()
        )
    
    def create_entry_signal(
        self,
        signal_id: str,
        entry_price: float = 3280.0,
        stop_loss: float = 3270.0,
        take_profit: float = 3295.0,
        pattern_type: PatternType = PatternType.V_SHAPE_REVERSAL,
        confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM,
        score: float = 75.0,
        timeframe: str = "1m",
        timestamp: datetime = None
    ) -> EntrySignal:
        """Helper to create entry signal"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        return EntrySignal(
            signal_id=signal_id,
            symbol="XAUUSD",
            timestamp=timestamp,
            pattern_type=pattern_type,
            timeframe=timeframe,
            entry_price=Decimal(str(entry_price)),
            stop_loss=Decimal(str(stop_loss)),
            take_profit=Decimal(str(take_profit)),
            scoring_result=self.create_scoring_result(score, confidence_level)
        )
    
    @pytest.mark.asyncio
    async def test_single_high_quality_signal(self, engine, base_timestamp):
        """Test ranking of single high-quality signal"""
        signal = self.create_entry_signal(
            "signal_1",
            confidence_level=ConfidenceLevel.HIGH,
            score=85.0,
            timestamp=base_timestamp
        )
        
        result = await engine.rank_signals([signal])
        
        assert len(result.prioritized_signals) == 1
        assert len(result.excluded_signals) == 0
        
        prioritized = result.prioritized_signals[0]
        assert prioritized.priority_rank == 1
        assert prioritized.signal.signal_id == "signal_1"
        assert prioritized.priority_score > 0
        assert len(prioritized.ranking_reasons) > 0
    
    @pytest.mark.asyncio
    async def test_multiple_signals_confidence_prioritization(self, engine, base_timestamp):
        """Test prioritization by confidence level"""
        signals = [
            self.create_entry_signal("signal_low", confidence_level=ConfidenceLevel.LOW, score=70.0),
            self.create_entry_signal("signal_high", confidence_level=ConfidenceLevel.HIGH, score=75.0),
            self.create_entry_signal("signal_medium", confidence_level=ConfidenceLevel.MEDIUM, score=72.0)
        ]
        
        result = await engine.rank_signals(signals)
        
        assert len(result.prioritized_signals) == 3
        assert result.prioritized_signals[0].signal.signal_id == "signal_high"
        assert result.prioritized_signals[1].signal.signal_id == "signal_medium"
        assert result.prioritized_signals[2].signal.signal_id == "signal_low"
    
    @pytest.mark.asyncio
    async def test_correlation_detection_same_direction(self, engine, base_timestamp):
        """Test correlation detection for same direction signals"""
        signals = [
            self.create_entry_signal("signal_1", entry_price=3280.0, take_profit=3295.0),  # Long
            self.create_entry_signal("signal_2", entry_price=3285.0, take_profit=3300.0),  # Long, 5 pips apart
            self.create_entry_signal("signal_3", entry_price=3350.0, take_profit=3365.0)   # Long, far apart
        ]
        
        result = await engine.rank_signals(signals)
        
        # signal_1 and signal_2 should be correlated, one should be excluded
        # Total should be 3 processed, but only 2 prioritized
        total_processed = len(result.prioritized_signals) + len(result.excluded_signals)
        assert total_processed == 3
        assert len(result.excluded_signals) >= 1
        
        # At least one signal should be excluded for correlation
        correlation_excluded = [s for s in result.excluded_signals 
                              if s.exclusion_reason == ExclusionReason.CORRELATION_SAME_DIRECTION]
        assert len(correlation_excluded) >= 1
    
    @pytest.mark.asyncio
    async def test_correlation_detection_stop_loss_overlap(self, engine, base_timestamp):
        """Test correlation detection for stop loss overlap"""
        signals = [
            self.create_entry_signal("signal_1", entry_price=3280.0, stop_loss=3270.0, take_profit=3295.0),  # Long
            self.create_entry_signal("signal_2", entry_price=3260.0, stop_loss=3272.0, take_profit=3245.0)   # Short, SL overlap
        ]
        
        result = await engine.rank_signals(signals)
        
        # Should detect stop loss overlap and exclude one
        assert len(result.prioritized_signals) == 1
        assert len(result.excluded_signals) == 1
        
        excluded = result.excluded_signals[0]
        assert excluded.exclusion_reason == ExclusionReason.CORRELATION_STOP_LOSS_OVERLAP
    
    @pytest.mark.asyncio
    async def test_position_limits_same_direction(self, engine, base_timestamp):
        """Test position limits for same direction"""
        # Create 4 long signals (exceeds default limit of 3) - spread them far apart to avoid correlation
        signals = [
            self.create_entry_signal(f"long_signal_{i}", entry_price=3200.0 + i*100, take_profit=3215.0 + i*100)
            for i in range(4)
        ]
        
        result = await engine.rank_signals(signals)
        
        # Total processed should be 4
        total_processed = len(result.prioritized_signals) + len(result.excluded_signals)
        assert total_processed == 4
        
        # Should have some position limit exclusions
        position_excluded = [s for s in result.excluded_signals 
                           if s.exclusion_reason == ExclusionReason.POSITION_LIMIT_EXCEEDED]
        assert len(position_excluded) >= 1
    
    @pytest.mark.asyncio
    async def test_position_limits_with_existing_positions(self, engine, base_timestamp):
        """Test position limits considering existing positions"""
        existing_positions = [
            ExistingPosition(
                position_id="existing_1",
                symbol="XAUUSD",
                direction="long",
                entry_price=Decimal("3200.0"),
                stop_loss=Decimal("3190.0"),
                take_profit=Decimal("3215.0"),
                timeframe="1m",
                pattern_type=PatternType.TREND_CONTINUATION
            ),
            ExistingPosition(
                position_id="existing_2",
                symbol="XAUUSD",
                direction="long",
                entry_price=Decimal("3250.0"),
                stop_loss=Decimal("3240.0"),
                take_profit=Decimal("3265.0"),
                timeframe="5m",
                pattern_type=PatternType.V_SHAPE_REVERSAL
            )
        ]
        
        # Try to add 2 more long signals (would exceed limit of 3)
        signals = [
            self.create_entry_signal("new_long_1", entry_price=3280.0, take_profit=3295.0),
            self.create_entry_signal("new_long_2", entry_price=3330.0, take_profit=3345.0)
        ]
        
        result = await engine.rank_signals(signals, existing_positions)
        
        # Should only allow 1 more long position
        assert len(result.prioritized_signals) == 1
        assert len(result.excluded_signals) == 1
    
    @pytest.mark.asyncio
    async def test_quality_filtering(self, engine, base_timestamp):
        """Test filtering by minimum quality thresholds"""
        signals = [
            self.create_entry_signal("good_signal", score=75.0),  # Above threshold
            self.create_entry_signal("bad_score", score=50.0),   # Below score threshold
            self.create_entry_signal(                            # Below RR threshold
                "bad_rr", 
                entry_price=3280.0, 
                stop_loss=3270.0, 
                take_profit=3285.0,  # 1:0.5 RR ratio
                score=75.0
            )
        ]
        
        result = await engine.rank_signals(signals)
        
        # Only the good signal should pass quality filtering
        assert len(result.prioritized_signals) == 1
        assert result.prioritized_signals[0].signal.signal_id == "good_signal"
    
    @pytest.mark.asyncio
    async def test_risk_reward_ratio_prioritization(self, engine, base_timestamp):
        """Test prioritization by risk-reward ratio"""
        signals = [
            self.create_entry_signal(
                "rr_1_5",
                entry_price=3280.0, stop_loss=3270.0, take_profit=3295.0,  # 1:1.5
                confidence_level=ConfidenceLevel.MEDIUM
            ),
            self.create_entry_signal(
                "rr_2_0", 
                entry_price=3280.0, stop_loss=3270.0, take_profit=3300.0,  # 1:2.0
                confidence_level=ConfidenceLevel.MEDIUM
            ),
            self.create_entry_signal(
                "rr_3_0",
                entry_price=3280.0, stop_loss=3270.0, take_profit=3310.0,  # 1:3.0
                confidence_level=ConfidenceLevel.MEDIUM
            )
        ]
        
        result = await engine.rank_signals(signals)
        
        # Should be ordered by RR ratio (highest first)
        assert result.prioritized_signals[0].signal.signal_id == "rr_3_0"
        assert result.prioritized_signals[1].signal.signal_id == "rr_2_0"
        assert result.prioritized_signals[2].signal.signal_id == "rr_1_5"
    
    @pytest.mark.asyncio
    async def test_pattern_complexity_scoring(self, engine, base_timestamp):
        """Test pattern complexity scoring (simpler patterns preferred)"""
        signals = [
            self.create_entry_signal("complex", pattern_type=PatternType.EMA_SQUEEZE),      # Most complex
            self.create_entry_signal("simple", pattern_type=PatternType.TREND_CONTINUATION), # Simplest
            self.create_entry_signal("medium", pattern_type=PatternType.V_SHAPE_REVERSAL)   # Medium
        ]
        
        # Give all same confidence and RR to test pattern complexity
        for signal in signals:
            signal.scoring_result = self.create_scoring_result(75.0, ConfidenceLevel.MEDIUM)
        
        result = await engine.rank_signals(signals)
        
        # Simpler patterns should be prioritized
        assert result.prioritized_signals[0].signal.signal_id == "simple"
    
    @pytest.mark.asyncio
    async def test_statistics_generation(self, engine, base_timestamp):
        """Test statistics generation in result"""
        signals = [
            self.create_entry_signal("signal_1", confidence_level=ConfidenceLevel.HIGH, entry_price=3200.0, take_profit=3215.0),
            self.create_entry_signal("signal_2", confidence_level=ConfidenceLevel.MEDIUM, entry_price=3300.0, take_profit=3315.0),
            self.create_entry_signal("signal_3", entry_price=3400.0, take_profit=3415.0)  # Spread far apart
        ]
        
        result = await engine.rank_signals(signals)
        
        stats = result.statistics
        total_processed = len(result.prioritized_signals) + len(result.excluded_signals)
        assert stats['total_signals_processed'] == total_processed
        assert stats['prioritized_count'] == len(result.prioritized_signals)
        assert stats['excluded_count'] == len(result.excluded_signals)
        assert 'average_confidence_level' in stats
        assert 'average_risk_reward_ratio' in stats
        assert 'average_composite_score' in stats
        assert 'exclusion_reasons_breakdown' in stats
        assert 'pattern_type_distribution' in stats
        assert 'timeframe_distribution' in stats
    
    @pytest.mark.asyncio
    async def test_json_serialization(self, engine, base_timestamp):
        """Test JSON serialization of results"""
        signals = [
            self.create_entry_signal("signal_1", confidence_level=ConfidenceLevel.HIGH),
            self.create_entry_signal("signal_2", entry_price=3285.0, take_profit=3300.0)  # Correlated
        ]
        
        result = await engine.rank_signals(signals)
        
        # Should be able to convert to dict for JSON serialization
        result_dict = result.to_dict()
        
        assert 'prioritized_signals' in result_dict
        assert 'excluded_signals' in result_dict
        assert 'statistics' in result_dict
        assert 'timestamp' in result_dict
        assert 'processing_summary' in result_dict
        
        # Check structure of prioritized signals
        if result_dict['prioritized_signals']:
            signal_dict = result_dict['prioritized_signals'][0]
            required_fields = [
                'signal_id', 'symbol', 'pattern_type', 'timeframe',
                'priority_rank', 'priority_score', 'confidence_level',
                'risk_reward_ratio', 'composite_score', 'ranking_reasons'
            ]
            for field in required_fields:
                assert field in signal_dict
        
        # Check structure of excluded signals
        if result_dict['excluded_signals']:
            excluded_dict = result_dict['excluded_signals'][0]
            required_fields = [
                'signal_id', 'symbol', 'exclusion_reason', 
                'exclusion_details', 'correlations'
            ]
            for field in required_fields:
                assert field in excluded_dict
    
    @pytest.mark.asyncio
    async def test_time_decay_functionality(self, engine, base_timestamp):
        """Test time decay functionality"""
        # Enable time decay
        engine.config.enable_time_decay = True
        engine.config.time_decay_factor_per_minute = 0.1
        
        old_signal = self.create_entry_signal(
            "old_signal",
            timestamp=base_timestamp - timedelta(minutes=5)  # 5 minutes old
        )
        new_signal = self.create_entry_signal(
            "new_signal", 
            timestamp=base_timestamp
        )
        
        result = await engine.rank_signals([old_signal, new_signal])
        
        # New signal should have higher priority due to time decay
        assert result.prioritized_signals[0].signal.signal_id == "new_signal"
        assert result.prioritized_signals[1].signal.signal_id == "old_signal"
    
    @pytest.mark.asyncio
    async def test_large_signal_batch_performance(self, engine, base_timestamp):
        """Test performance with large number of signals"""
        # Create 20 signals with varying parameters
        signals = []
        for i in range(20):
            confidence = [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH][i % 3]
            pattern = list(PatternType)[i % len(PatternType)]
            
            signals.append(self.create_entry_signal(
                f"signal_{i}",
                entry_price=3200.0 + i * 10,  # Spread them out to avoid correlation
                take_profit=3215.0 + i * 10,
                confidence_level=confidence,
                pattern_type=pattern,
                score=65.0 + (i % 30)  # Varying scores
            ))
        
        result = await engine.rank_signals(signals)
        
        # Should handle large batch efficiently
        assert len(result.prioritized_signals) + len(result.excluded_signals) == 20
        assert len(result.prioritized_signals) > 0
        
        # Results should be properly ranked
        for i in range(len(result.prioritized_signals) - 1):
            current_rank = result.prioritized_signals[i].priority_rank
            next_rank = result.prioritized_signals[i + 1].priority_rank
            assert current_rank < next_rank
    
    def test_correlation_group_building(self, engine):
        """Test correlation group building algorithm"""
        # This tests the internal DFS algorithm for finding correlation groups
        signal1 = self.create_entry_signal("s1", entry_price=3280.0)
        signal2 = self.create_entry_signal("s2", entry_price=3285.0)  # Correlated with s1
        signal3 = self.create_entry_signal("s3", entry_price=3290.0)  # Correlated with s2
        signal4 = self.create_entry_signal("s4", entry_price=3350.0)  # Independent
        
        signals = [signal1, signal2, signal3, signal4]
        
        # Mock correlations: s1-s2, s2-s3 (so s1,s2,s3 form one group, s4 is separate)
        from src.domain.models.priority_ranking import CorrelationInfo, ExclusionReason
        correlations = [
            CorrelationInfo("s1", "s2", ExclusionReason.CORRELATION_SAME_DIRECTION, 5.0, "test"),
            CorrelationInfo("s2", "s3", ExclusionReason.CORRELATION_SAME_DIRECTION, 5.0, "test")
        ]
        
        groups = engine._build_correlation_groups(signals, correlations)
        
        # Should have 2 groups: [s1,s2,s3] and [s4]
        assert len(groups) == 2
        group_sizes = sorted([len(group) for group in groups])
        assert group_sizes == [1, 3]