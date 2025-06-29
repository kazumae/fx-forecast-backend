"""
Unit tests for Zone Multiplier Service (US-014)

Tests the complete zone multiplication system including
power zone detection, scoring enhancement, and priority boosting.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

from src.services.entry_point.zone_multiplier_service import ZoneMultiplierService
from src.services.entry_point.zone_analysis.risk_reward_optimizer import TradeDirection
from src.domain.models.zone_multiplier import (
    ZoneInfo, EMAInfo, MultiplierConfig, PowerLevel
)


class TestZoneMultiplierService:
    """Test cases for zone multiplier service"""
    
    @pytest.fixture
    def service(self):
        """Create service instance"""
        config = MultiplierConfig()
        return ZoneMultiplierService(config)
    
    @pytest.fixture
    def sample_zone(self):
        """Sample zone for testing"""
        return ZoneInfo(
            zone_id="zone_001",
            price_level=Decimal("2034.50"),
            zone_type="support",
            timeframe="1H",
            strength=0.8,
            role_history=["support"],  # Single role - no reversal
            created_at="2024-06-29T10:00:00Z",
            test_count=1
        )
    
    @pytest.fixture
    def sample_ema_values(self):
        """Sample EMA values"""
        return [
            EMAInfo(period=20, value=Decimal("2030.00"), timeframe="1H"),
            EMAInfo(period=75, value=Decimal("2033.00"), timeframe="1H"),
            EMAInfo(period=200, value=Decimal("2034.45"), timeframe="1H")  # Close to zone
        ]
    
    @pytest.fixture
    def nearby_zones(self):
        """Nearby zones for cluster testing"""
        return [
            ZoneInfo(
                zone_id="zone_002",
                price_level=Decimal("2035.00"),  # 5 pips away
                zone_type="support",
                timeframe="4H",
                strength=0.7,
                role_history=["support"],
                created_at="2024-06-29T09:00:00Z"
            ),
            ZoneInfo(
                zone_id="zone_003", 
                price_level=Decimal("2036.20"),  # 17 pips away
                zone_type="support",
                timeframe="1D",
                strength=0.9,
                role_history=["support", "resistance"],
                created_at="2024-06-29T08:00:00Z"
            )
        ]
    
    def test_analyze_zone_multiplier_effects_power_zone(
        self, service, sample_zone, sample_ema_values, nearby_zones
    ):
        """Test complete analysis for power zone"""
        # Test with power zone conditions (EMA overlap + cluster)
        result = service.analyze_zone_multiplier_effects(
            target_zone=sample_zone,
            nearby_zones=nearby_zones,
            ema_values=sample_ema_values,
            current_price=Decimal("2034.00"),
            timeframe="1H",
            market_session="london",
            original_zone_score=20.0,
            psychological_levels=[Decimal("2034.00")],
            trade_direction=TradeDirection.LONG,
            entry_price=Decimal("2034.10")
        )
        
        # Verify power zone detection
        assert result['zone_analysis']['is_power_zone'] is True
        assert result['zone_analysis']['power_level'] >= 2
        assert len(result['zone_analysis']['components']) >= 2
        
        # Verify score enhancement
        assert result['enhanced_scores']['multiplied_zone_score'] > 20.0
        assert result['score_multipliers']['final_multiplier'] > 1.0
        
        # Verify priority boost
        assert result['execution_priority']['final_priority'] > 5
        assert result['execution_priority']['weight_multiplier'] >= 1.5
        
        # Verify risk-reward enhancement
        assert 'detailed_risk_reward' in result
        assert result['detailed_risk_reward']['optimized_sl_distance'] <= 20.0  # Tighter SL
        assert result['detailed_risk_reward']['optimized_tp_distance'] >= 30.0  # Extended TP
    
    def test_analyze_zone_multiplier_effects_regular_zone(self, service, nearby_zones):
        """Test analysis for regular zone (no power zone features)"""
        # Create regular zone with no reversal history
        regular_zone = ZoneInfo(
            zone_id="regular_zone",
            price_level=Decimal("2034.50"),
            zone_type="support",
            timeframe="1H",
            strength=0.6,
            role_history=["support"],  # Only one role - no reversal
            created_at="2024-06-29T10:00:00Z",
            test_count=1
        )
        
        # Remove power zone conditions
        regular_ema_values = [
            EMAInfo(period=200, value=Decimal("2020.00"), timeframe="1H")  # Far from zone
        ]
        
        distant_zones = [
            ZoneInfo(
                zone_id="zone_004",
                price_level=Decimal("2100.00"),  # 65+ pips away - no cluster
                zone_type="resistance",
                timeframe="1H",
                strength=0.5,
                role_history=["resistance"],  # No reversal
                created_at="2024-06-29T09:00:00Z"
            )
        ]
        
        result = service.analyze_zone_multiplier_effects(
            target_zone=regular_zone,
            nearby_zones=distant_zones,
            ema_values=regular_ema_values,
            current_price=Decimal("2034.00"),
            timeframe="1H",
            market_session="sydney",
            original_zone_score=15.0
        )
        
        # Verify regular zone behavior
        assert result['zone_analysis']['is_power_zone'] is False
        assert result['score_multipliers']['final_multiplier'] == 1.0
        assert result['enhanced_scores']['multiplied_zone_score'] == 15.0
        assert result['execution_priority']['final_priority'] == 5  # Base priority
        assert result['execution_priority']['immediate_execution'] is False
    
    def test_quick_power_zone_check_positive(
        self, service, sample_zone, sample_ema_values, nearby_zones
    ):
        """Test quick power zone check for power zone"""
        result = service.quick_power_zone_check(
            target_zone=sample_zone,
            nearby_zones=nearby_zones,
            ema_values=sample_ema_values,
            current_price=Decimal("2034.00"),
            timeframe="1H",
            market_session="london"
        )
        
        assert result['is_power_zone'] is True
        assert result['component_count'] >= 2
        assert result['estimated_multiplier'] > 1.0
        assert result['recommendation'] in ['enhanced_analysis', 'full_analysis']
        assert 'component_types' in result
    
    def test_quick_power_zone_check_negative(self, service, sample_zone):
        """Test quick power zone check for regular zone"""
        # No nearby zones or EMA overlaps
        result = service.quick_power_zone_check(
            target_zone=sample_zone,
            nearby_zones=[],
            ema_values=[],
            current_price=Decimal("2034.00"),
            timeframe="1H",
            market_session="sydney"
        )
        
        assert result['is_power_zone'] is False
        assert result['component_count'] == 0
        assert result['estimated_multiplier'] == 1.0
        assert result['recommendation'] == 'standard_analysis'
    
    def test_get_enhanced_signal_parameters(self, service):
        """Test enhanced signal parameters extraction"""
        # Mock results
        mock_multiplier_result = Mock()
        mock_multiplier_result.multiplied_zone_score = 45.0
        mock_multiplier_result.final_multiplier = 2.3
        mock_multiplier_result.total_score_boost = 25.0
        mock_multiplier_result.recommended_size_multiplier = 1.5
        
        mock_priority_result = {
            'final_priority': 12,
            'weight_multiplier': 2.0,
            'immediate_execution': True,
            'bypass_correlation': True,
            'queue_position': 2
        }
        
        mock_rr_result = Mock()
        mock_rr_result.adjusted_sl_distance = Decimal("15.0")
        mock_rr_result.adjusted_tp_distance = Decimal("45.0")
        mock_rr_result.enhanced_rr_ratio = 3.0
        mock_rr_result.confidence_boost = 0.85
        mock_rr_result.sl_reduction_pips = Decimal("5.0")
        mock_rr_result.tp_extension_pips = Decimal("15.0")
        
        params = service.get_enhanced_signal_parameters(
            mock_multiplier_result, mock_priority_result, mock_rr_result
        )
        
        # Verify all enhanced parameters
        assert params['enhanced_zone_score'] == 45.0
        assert params['score_multiplier'] == 2.3
        assert params['execution_priority'] == 12
        assert params['priority_weight'] == 2.0
        assert params['immediate_execution'] is True
        assert params['bypass_correlation'] is True
        assert params['optimized_sl_pips'] == 15.0
        assert params['optimized_tp_pips'] == 45.0
        assert params['enhanced_rr_ratio'] == 3.0
        assert params['confidence_level'] == 0.85
    
    def test_create_execution_summary_power_zone(self, service):
        """Test execution summary for power zone"""
        analysis_result = {
            'zone_analysis': {
                'is_power_zone': True,
                'power_level': 4,
                'components': []
            },
            'score_multipliers': {
                'final_multiplier': 2.5
            },
            'execution_priority': {
                'final_priority': 15,
                'weight_multiplier': 2.0,
                'immediate_execution': True
            },
            'detailed_risk_reward': {
                'optimized_sl_distance': 12.0,
                'optimized_tp_distance': 48.0
            }
        }
        
        summary = service.create_execution_summary(analysis_result)
        
        assert "POWER ZONE" in summary
        assert "Level 4" in summary
        assert "2.50x multiplier" in summary
        assert "Priority: 15" in summary
        assert "Weight: 2.0x" in summary
        assert "IMMEDIATE EXECUTION" in summary
        assert "12/48 pips" in summary
    
    def test_create_execution_summary_regular_zone(self, service):
        """Test execution summary for regular zone"""
        analysis_result = {
            'zone_analysis': {
                'is_power_zone': False
            },
            'score_multipliers': {
                'final_multiplier': 1.0
            },
            'execution_priority': {
                'final_priority': 5,
                'weight_multiplier': 1.0,
                'immediate_execution': False
            }
        }
        
        summary = service.create_execution_summary(analysis_result)
        assert summary == "Regular zone - standard execution parameters"
    
    def test_ema_overlap_detection(self, service, sample_zone, nearby_zones):
        """Test EMA overlap component detection"""
        # EMA 200 very close to zone (2 pips difference)
        close_ema_values = [
            EMAInfo(period=200, value=Decimal("2034.48"), timeframe="1H")
        ]
        
        result = service.analyze_zone_multiplier_effects(
            target_zone=sample_zone,
            nearby_zones=nearby_zones,
            ema_values=close_ema_values,
            current_price=Decimal("2034.00"),
            timeframe="1H",
            market_session="london",
            original_zone_score=20.0
        )
        
        # Should detect EMA overlap
        components = result['zone_analysis']['components']
        ema_components = [c for c in components if c['type'] == 'zone_ema_overlap']
        assert len(ema_components) >= 1
        assert ema_components[0]['ema'] == 200
        assert ema_components[0]['distance'] <= 10.0  # Within threshold
    
    def test_multi_zone_cluster_detection(self, service, sample_zone):
        """Test multi-zone cluster detection"""
        # Create cluster of zones within 50 pips
        cluster_zones = [
            ZoneInfo(
                zone_id="cluster_1",
                price_level=Decimal("2034.80"),  # 3 pips away
                zone_type="support",
                timeframe="4H",
                strength=0.7,
                role_history=["support"],
                created_at="2024-06-29T09:00:00Z"
            ),
            ZoneInfo(
                zone_id="cluster_2",
                price_level=Decimal("2035.20"),  # 7 pips away
                zone_type="support",
                timeframe="1D",
                strength=0.8,
                role_history=["support"],
                created_at="2024-06-29T08:00:00Z"
            ),
            ZoneInfo(
                zone_id="cluster_3",
                price_level=Decimal("2034.10"),  # 4 pips away
                zone_type="support",
                timeframe="1H",
                strength=0.6,
                role_history=["support"],
                created_at="2024-06-29T07:00:00Z"
            )
        ]
        
        result = service.analyze_zone_multiplier_effects(
            target_zone=sample_zone,
            nearby_zones=cluster_zones,
            ema_values=[],
            current_price=Decimal("2034.00"),
            timeframe="1H",
            market_session="london",
            original_zone_score=20.0
        )
        
        # Should detect cluster (4 zones total including target)
        components = result['zone_analysis']['components']
        cluster_components = [c for c in components if c['type'] == 'multi_zone_cluster']
        assert len(cluster_components) >= 1
        assert len(cluster_components[0]['zones']) >= 3  # Minimum for cluster
    
    def test_role_reversal_detection(self, service, nearby_zones):
        """Test role reversal detection"""
        # Zone with strong role reversal history
        reversal_zone = ZoneInfo(
            zone_id="reversal_zone",
            price_level=Decimal("2034.50"),
            zone_type="support",
            timeframe="1H",
            strength=0.9,
            role_history=["support", "resistance", "support", "resistance", "support"],  # 4 changes
            created_at="2024-06-29T10:00:00Z",
            test_count=5
        )
        
        result = service.analyze_zone_multiplier_effects(
            target_zone=reversal_zone,
            nearby_zones=nearby_zones,
            ema_values=[],
            current_price=Decimal("2034.00"),
            timeframe="1H",
            market_session="london",
            original_zone_score=20.0
        )
        
        # Should detect role reversal
        components = result['zone_analysis']['components']
        reversal_components = [c for c in components if c['type'] == 'role_reversal']
        assert len(reversal_components) >= 1
        assert len(reversal_components[0]['history']) >= 5
    
    def test_multiplier_cap_enforcement(self, service):
        """Test that multiplier cap of 3.0 is enforced"""
        # Create extreme power zone conditions that would exceed cap
        extreme_zone = ZoneInfo(
            zone_id="extreme_zone",
            price_level=Decimal("2034.50"),
            zone_type="support",
            timeframe="1H",
            strength=1.0,
            role_history=["support", "resistance"] * 5,  # Many reversals
            created_at="2024-06-29T10:00:00Z",
            test_count=10
        )
        
        # Multiple overlapping zones
        many_zones = [
            ZoneInfo(f"zone_{i}", Decimal(f"2034.{50+i}"), "support", "1H", 0.8, ["support"], "2024-06-29T10:00:00Z")
            for i in range(5)
        ]
        
        # EMA overlap
        overlap_emas = [
            EMAInfo(200, Decimal("2034.51"), "1H"),  # Very close
            EMAInfo(75, Decimal("2034.49"), "1H")    # Also close
        ]
        
        result = service.analyze_zone_multiplier_effects(
            target_zone=extreme_zone,
            nearby_zones=many_zones,
            ema_values=overlap_emas,
            current_price=Decimal("2034.00"),
            timeframe="1H",
            market_session="london",
            original_zone_score=20.0
        )
        
        # Multiplier should be capped at 3.0
        assert result['score_multipliers']['final_multiplier'] <= 3.0
        assert result['zone_analysis']['is_power_zone'] is True
        assert result['zone_analysis']['power_level'] == 5  # EXTREME level
    
    def test_immediate_execution_flag(self, service, sample_zone, sample_ema_values, nearby_zones):
        """Test immediate execution flag for extreme power zones"""
        result = service.analyze_zone_multiplier_effects(
            target_zone=sample_zone,
            nearby_zones=nearby_zones,
            ema_values=sample_ema_values,
            current_price=Decimal("2034.00"),
            timeframe="1H",
            market_session="london_ny_overlap",  # Best session
            original_zone_score=25.0  # High base score
        )
        
        # High priority power zones should get immediate execution
        if result['execution_priority']['final_priority'] >= 15:
            assert result['execution_priority']['immediate_execution'] is True
        
        # Should have elevated priority
        assert result['execution_priority']['final_priority'] > 5
        assert result['execution_priority']['weight_multiplier'] >= 1.5