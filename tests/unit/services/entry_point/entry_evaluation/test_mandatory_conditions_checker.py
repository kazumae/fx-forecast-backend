"""
Unit tests for Mandatory Conditions Checker
"""
import pytest
from datetime import datetime, time
from decimal import Decimal

from src.services.entry_point.entry_evaluation.mandatory_conditions_checker import MandatoryConditionsChecker
from src.domain.models.entry_evaluation import (
    EntryContext, ConditionConfig, TrendData, TrendDirection, 
    MarketSession, ConditionType
)


class TestMandatoryConditionsChecker:
    """Test cases for mandatory conditions checker"""
    
    @pytest.fixture
    def default_config(self):
        """Default configuration for tests"""
        return ConditionConfig(
            min_trend_alignment_score=0.5,
            higher_timeframes=["15m", "1h"],
            zone_proximity_threshold=Decimal('5'),
            zone_acceptable_threshold=Decimal('20'),
            min_risk_reward_ratio=1.5,
            preferred_sessions=[MarketSession.LONDON, MarketSession.NEW_YORK, MarketSession.OVERLAP_LONDON_NY],
            min_session_score=0.4  # Raised to avoid boundary issues
        )
    
    @pytest.fixture
    def checker(self, default_config):
        """Create checker instance"""
        return MandatoryConditionsChecker(default_config)
    
    @pytest.fixture
    def base_time(self):
        """Base timestamp for tests (London session)"""
        return datetime(2024, 6, 29, 10, 0, 0)  # 10:00 UTC (London time)
    
    def create_entry_context(
        self,
        timestamp: datetime,
        entry_price: float = 3280.0,
        stop_loss: float = 3270.0,
        take_profit: float = 3295.0,
        zone_distance: float = 3.0,
        zone_strength: str = 'A',
        trends: list = None,
        session: MarketSession = MarketSession.LONDON
    ) -> EntryContext:
        """Helper to create entry context"""
        if trends is None:
            trends = [
                TrendData("1m", TrendDirection.UPTREND, 0.8, 0.9),
                TrendData("15m", TrendDirection.UPTREND, 0.7, 0.8),
                TrendData("1h", TrendDirection.UPTREND, 0.6, 0.7)
            ]
        
        return EntryContext(
            symbol="XAUUSD",
            timestamp=timestamp,
            entry_price=Decimal(str(entry_price)),
            stop_loss=Decimal(str(stop_loss)),
            take_profit=Decimal(str(take_profit)),
            pattern_type="V_SHAPE_REVERSAL",
            pattern_confidence=0.85,
            current_timeframe="1m",
            trends=trends,
            nearest_zone_distance=Decimal(str(zone_distance)),
            nearest_zone_strength=zone_strength,
            current_session=session
        )
    
    @pytest.mark.asyncio
    async def test_all_conditions_pass(self, checker, base_time):
        """Test when all conditions are met"""
        context = self.create_entry_context(
            timestamp=base_time,
            entry_price=3280.0,
            stop_loss=3270.0,  # 10 pips risk
            take_profit=3295.0,  # 15 pips reward (1:1.5 RR)
            zone_distance=3.0,   # Close to zone
            zone_strength='A'
        )
        
        result = await checker.check_all_conditions(context)
        
        # Should pass all conditions
        assert result.all_conditions_met is True
        assert result.rejection_reason is None
        assert len(result.conditions) == 4
        assert result.passed_conditions_count == 4
        assert result.failed_conditions_count == 0
        assert result.overall_score > 0.7
        
        # Check individual conditions
        condition_types = {c.condition_type for c in result.conditions}
        expected_types = {
            ConditionType.TREND_ALIGNMENT,
            ConditionType.ZONE_RELATIONSHIP,
            ConditionType.RISK_REWARD_RATIO,
            ConditionType.MARKET_SESSION
        }
        assert condition_types == expected_types
        
        # All should pass
        for condition in result.conditions:
            assert condition.passed is True
            assert condition.score > 0.0
    
    @pytest.mark.asyncio
    async def test_trend_alignment_failure(self, checker, base_time):
        """Test trend alignment failure"""
        # Mixed trends - current uptrend, higher timeframes downtrend
        mixed_trends = [
            TrendData("1m", TrendDirection.UPTREND, 0.8, 0.9),
            TrendData("15m", TrendDirection.DOWNTREND, 0.7, 0.8),
            TrendData("1h", TrendDirection.DOWNTREND, 0.8, 0.9)
        ]
        
        context = self.create_entry_context(
            timestamp=base_time,
            trends=mixed_trends
        )
        
        result = await checker.check_all_conditions(context)
        
        assert result.all_conditions_met is False
        assert "トレンド整合性" in result.rejection_reason
        
        # Find trend alignment condition
        trend_condition = next(
            c for c in result.conditions 
            if c.condition_type == ConditionType.TREND_ALIGNMENT
        )
        assert trend_condition.passed is False
        assert trend_condition.score < checker.config.min_trend_alignment_score
    
    @pytest.mark.asyncio
    async def test_zone_distance_failure(self, checker, base_time):
        """Test zone distance too far"""
        context = self.create_entry_context(
            timestamp=base_time,
            zone_distance=25.0  # Beyond 20 pip threshold
        )
        
        result = await checker.check_all_conditions(context)
        
        assert result.all_conditions_met is False
        assert "ゾーン" in result.rejection_reason
        
        # Find zone condition
        zone_condition = next(
            c for c in result.conditions 
            if c.condition_type == ConditionType.ZONE_RELATIONSHIP
        )
        assert zone_condition.passed is False
        assert "遠すぎる" in zone_condition.details
    
    @pytest.mark.asyncio
    async def test_risk_reward_ratio_failure(self, checker, base_time):
        """Test insufficient risk-reward ratio"""
        context = self.create_entry_context(
            timestamp=base_time,
            entry_price=3280.0,
            stop_loss=3270.0,  # 10 pips risk
            take_profit=3285.0   # 5 pips reward (1:0.5 RR)
        )
        
        result = await checker.check_all_conditions(context)
        
        assert result.all_conditions_met is False
        assert "リスクリワード比" in result.rejection_reason
        
        # Find RR condition
        rr_condition = next(
            c for c in result.conditions 
            if c.condition_type == ConditionType.RISK_REWARD_RATIO
        )
        assert rr_condition.passed is False
        assert "基準未満" in rr_condition.details
        assert rr_condition.metadata['risk_reward_ratio'] < 1.5
    
    @pytest.mark.asyncio
    async def test_market_session_failure(self, checker, base_time):
        """Test bad market session timing"""
        # Quiet session
        context = self.create_entry_context(
            timestamp=base_time,
            session=MarketSession.QUIET
        )
        
        result = await checker.check_all_conditions(context)
        
        assert result.all_conditions_met is False
        assert "時間帯" in result.rejection_reason
        
        # Find session condition
        session_condition = next(
            c for c in result.conditions 
            if c.condition_type == ConditionType.MARKET_SESSION
        )
        assert session_condition.passed is False
        assert "非推奨" in session_condition.details
    
    @pytest.mark.asyncio
    async def test_zone_strength_scoring(self, checker, base_time):
        """Test zone strength affects scoring"""
        contexts = [
            self.create_entry_context(base_time, zone_strength='S', zone_distance=3.0),
            self.create_entry_context(base_time, zone_strength='A', zone_distance=3.0),
            self.create_entry_context(base_time, zone_strength='B', zone_distance=3.0),
            self.create_entry_context(base_time, zone_strength='C', zone_distance=3.0)
        ]
        
        scores = []
        for context in contexts:
            result = await checker.check_all_conditions(context)
            zone_condition = next(
                c for c in result.conditions 
                if c.condition_type == ConditionType.ZONE_RELATIONSHIP
            )
            scores.append(zone_condition.score)
        
        # Scores should decrease with zone strength: S > A > B > C
        assert scores[0] > scores[1] > scores[2] > scores[3]
        
        # All should still pass (within proximity threshold)
        for score in scores:
            assert score >= 0.7
    
    @pytest.mark.asyncio
    async def test_excellent_risk_reward_bonus(self, checker, base_time):
        """Test bonus scoring for excellent risk-reward ratios"""
        contexts = [
            self.create_entry_context(base_time, take_profit=3295.0),  # 1:1.5 RR
            self.create_entry_context(base_time, take_profit=3300.0),  # 1:2.0 RR
            self.create_entry_context(base_time, take_profit=3310.0)   # 1:3.0 RR
        ]
        
        scores = []
        for context in contexts:
            result = await checker.check_all_conditions(context)
            rr_condition = next(
                c for c in result.conditions 
                if c.condition_type == ConditionType.RISK_REWARD_RATIO
            )
            scores.append(rr_condition.score)
        
        # Higher RR ratios should get better scores
        assert scores[0] < scores[1] < scores[2]
        assert all(score >= 0.7 for score in scores)
    
    @pytest.mark.asyncio
    async def test_session_overlap_premium(self, checker, base_time):
        """Test London-NY overlap gets premium scoring"""
        sessions = [
            MarketSession.TOKYO,
            MarketSession.LONDON,
            MarketSession.NEW_YORK,
            MarketSession.OVERLAP_LONDON_NY,
            MarketSession.QUIET
        ]
        
        scores = []
        for session in sessions:
            context = self.create_entry_context(base_time, session=session)
            result = await checker.check_all_conditions(context)
            session_condition = next(
                c for c in result.conditions 
                if c.condition_type == ConditionType.MARKET_SESSION
            )
            scores.append(session_condition.score)
        
        # Overlap should have highest score
        overlap_score = scores[3]  # OVERLAP_LONDON_NY
        london_score = scores[1]   # LONDON
        ny_score = scores[2]       # NEW_YORK
        
        assert overlap_score == 1.0
        assert overlap_score > london_score
        assert overlap_score > ny_score
    
    @pytest.mark.asyncio
    async def test_missing_trend_data(self, checker, base_time):
        """Test handling of missing trend data"""
        # Missing current timeframe trend
        incomplete_trends = [
            TrendData("15m", TrendDirection.UPTREND, 0.7, 0.8),
            TrendData("1h", TrendDirection.UPTREND, 0.6, 0.7)
        ]
        
        context = self.create_entry_context(base_time, trends=incomplete_trends)
        
        result = await checker.check_all_conditions(context)
        
        # Should fail due to missing current timeframe
        assert result.all_conditions_met is False
        
        trend_condition = next(
            c for c in result.conditions 
            if c.condition_type == ConditionType.TREND_ALIGNMENT
        )
        assert trend_condition.passed is False
        assert "現在時間軸のトレンドデータが不足" in trend_condition.details
    
    @pytest.mark.asyncio
    async def test_range_trend_partial_alignment(self, checker, base_time):
        """Test range trend gets partial alignment credit"""
        range_trends = [
            TrendData("1m", TrendDirection.UPTREND, 0.8, 0.9),
            TrendData("15m", TrendDirection.RANGE, 0.5, 0.6),
            TrendData("1h", TrendDirection.UPTREND, 0.7, 0.8)
        ]
        
        context = self.create_entry_context(base_time, trends=range_trends)
        
        result = await checker.check_all_conditions(context)
        
        trend_condition = next(
            c for c in result.conditions 
            if c.condition_type == ConditionType.TREND_ALIGNMENT
        )
        
        # Should get partial credit for range alignment
        assert 0.3 < trend_condition.score < 0.9
        # May or may not pass depending on exact calculation
    
    def test_market_session_detection(self, checker):
        """Test market session detection based on time"""
        test_times = [
            (datetime(2024, 6, 29, 2, 0, 0), MarketSession.TOKYO),      # 02:00 UTC
            (datetime(2024, 6, 29, 10, 0, 0), MarketSession.LONDON),    # 10:00 UTC
            (datetime(2024, 6, 29, 15, 0, 0), MarketSession.OVERLAP_LONDON_NY),  # 15:00 UTC
            (datetime(2024, 6, 29, 20, 0, 0), MarketSession.NEW_YORK),  # 20:00 UTC
            (datetime(2024, 6, 29, 23, 30, 0), MarketSession.QUIET)     # 23:30 UTC
        ]
        
        for timestamp, expected_session in test_times:
            detected_session = checker.get_market_session(timestamp)
            assert detected_session == expected_session
    
    @pytest.mark.asyncio
    async def test_boundary_conditions(self, checker, base_time):
        """Test boundary value conditions"""
        # Exactly at thresholds
        boundary_contexts = [
            # Exactly at zone proximity threshold
            self.create_entry_context(base_time, zone_distance=5.0),
            # Exactly at zone acceptable threshold  
            self.create_entry_context(base_time, zone_distance=20.0),
            # Exactly at minimum RR ratio
            self.create_entry_context(base_time, take_profit=3295.0),  # 1:1.5
        ]
        
        for context in boundary_contexts:
            result = await checker.check_all_conditions(context)
            # Boundary conditions should generally pass
            assert result.all_conditions_met is True
    
    @pytest.mark.asyncio
    async def test_multiple_failures(self, checker, base_time):
        """Test multiple condition failures"""
        # Create context that fails multiple conditions
        bad_trends = [
            TrendData("1m", TrendDirection.UPTREND, 0.8, 0.9),
            TrendData("15m", TrendDirection.DOWNTREND, 0.8, 0.9),
            TrendData("1h", TrendDirection.DOWNTREND, 0.8, 0.9)
        ]
        
        context = self.create_entry_context(
            timestamp=base_time,
            trends=bad_trends,        # Trend misalignment
            zone_distance=25.0,       # Too far from zone
            take_profit=3285.0,       # Poor RR ratio
            session=MarketSession.QUIET  # Bad session
        )
        
        result = await checker.check_all_conditions(context)
        
        assert result.all_conditions_met is False
        assert result.failed_conditions_count >= 3
        assert "複数条件未達成" in result.rejection_reason
        assert result.overall_score < 0.5