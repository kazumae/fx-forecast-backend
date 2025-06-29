"""ゾーン近接スコアラーのユニットテスト"""
import pytest
from decimal import Decimal
from src.services.entry_point.evaluation.zone_proximity_scorer import ZoneProximityScorer
from src.domain.models.pattern import PatternSignal, PatternType, PatternStrength
from src.domain.models.zone import Zone, ZoneType, ZoneStatus
from tests.utils import SignalFactory, ZoneFactory
from datetime import datetime, timezone


class TestZoneProximityScorer:
    """ゾーン近接スコアラーのテスト"""
    
    @pytest.fixture
    def scorer(self):
        """スコアラーインスタンス"""
        config = {
            "max_distance_pips": 5.0,
            "zone_strength_multiplier": 1.2,
            "touch_count_bonus": 0.1
        }
        return ZoneProximityScorer(config)
    
    def test_pattern_at_strong_zone(self, scorer):
        """強いゾーンでのパターン"""
        # パターンシグナル（ゾーン直上）
        pattern = SignalFactory.create_pattern_signal(
            pattern_type=PatternType.V_SHAPE_REVERSAL,
            confidence=85.0
        )
        pattern.entry_point = Decimal("3270.50")
        
        # 強いサポートゾーン
        zones = [
            ZoneFactory.create_zone(
                upper=3271.00,
                lower=3269.00,
                zone_type=ZoneType.SUPPORT,
                strength=0.95,
                touch_count=6
            )
        ]
        
        score = scorer.calculate_score(pattern, zones, {})
        
        # 高スコアが期待される
        assert score.total_score >= 80.0
        assert score.zone_proximity_score >= 90.0
        assert score.zone_strength_score >= 90.0
    
    def test_pattern_far_from_zones(self, scorer):
        """ゾーンから離れたパターン"""
        pattern = SignalFactory.create_pattern_signal()
        pattern.entry_point = Decimal("3280.00")
        
        # 離れたゾーン
        zones = [
            ZoneFactory.create_zone(
                upper=3271.00,
                lower=3269.00,
                zone_type=ZoneType.SUPPORT
            ),
            ZoneFactory.create_zone(
                upper=3291.00,
                lower=3289.00,
                zone_type=ZoneType.RESISTANCE
            )
        ]
        
        score = scorer.calculate_score(pattern, zones, {})
        
        # 低スコアが期待される
        assert score.total_score < 50.0
        assert score.zone_proximity_score < 20.0
    
    def test_pattern_between_zones(self, scorer):
        """ゾーン間でのパターン"""
        pattern = SignalFactory.create_pattern_signal()
        pattern.entry_point = Decimal("3275.00")
        
        zones = [
            ZoneFactory.create_zone(
                upper=3273.00,
                lower=3271.00,
                zone_type=ZoneType.SUPPORT,
                strength=0.8
            ),
            ZoneFactory.create_zone(
                upper=3278.00,
                lower=3276.00,
                zone_type=ZoneType.RESISTANCE,
                strength=0.75
            )
        ]
        
        score = scorer.calculate_score(pattern, zones, {})
        
        # 中程度のスコア
        assert 40.0 <= score.total_score <= 70.0
    
    def test_zone_type_matching(self, scorer):
        """ゾーンタイプのマッチング"""
        # 強気パターン
        bullish_pattern = SignalFactory.create_pattern_signal(direction="bullish")
        bullish_pattern.entry_point = Decimal("3270.00")
        
        # 弱気パターン
        bearish_pattern = SignalFactory.create_pattern_signal(direction="bearish")
        bearish_pattern.entry_point = Decimal("3280.00")
        
        zones = [
            ZoneFactory.create_zone(
                upper=3271.00,
                lower=3269.00,
                zone_type=ZoneType.SUPPORT
            ),
            ZoneFactory.create_zone(
                upper=3281.00,
                lower=3279.00,
                zone_type=ZoneType.RESISTANCE
            )
        ]
        
        # 強気パターンはサポートゾーンで高スコア
        bullish_score = scorer.calculate_score(bullish_pattern, zones, {})
        
        # 弱気パターンはレジスタンスゾーンで高スコア
        bearish_score = scorer.calculate_score(bearish_pattern, zones, {})
        
        assert bullish_score.total_score > 70.0
        assert bearish_score.total_score > 70.0
    
    def test_multiple_zone_consideration(self, scorer):
        """複数ゾーンの考慮"""
        pattern = SignalFactory.create_pattern_signal()
        pattern.entry_point = Decimal("3275.00")
        
        # 複数の近接ゾーン
        zones = [
            ZoneFactory.create_zone(
                upper=3276.00,
                lower=3274.00,
                zone_type=ZoneType.SUPPORT,
                strength=0.7
            ),
            ZoneFactory.create_zone(
                upper=3275.50,
                lower=3274.50,
                zone_type=ZoneType.SUPPORT,
                strength=0.85
            ),
            ZoneFactory.create_zone(
                upper=3276.50,
                lower=3273.50,
                zone_type=ZoneType.SUPPORT,
                strength=0.6
            )
        ]
        
        score = scorer.calculate_score(pattern, zones, {})
        
        # 最も強いゾーンが考慮されるはず
        assert score.zone_strength_score >= 80.0
        assert "zones_nearby" in score.details
        assert score.details["zones_nearby"] == 3
    
    def test_zone_touch_count_bonus(self, scorer):
        """ゾーンタッチ回数ボーナス"""
        pattern = SignalFactory.create_pattern_signal()
        pattern.entry_point = Decimal("3270.00")
        
        # 異なるタッチ回数のゾーン
        zone_low_touch = ZoneFactory.create_zone(
            upper=3271.00,
            lower=3269.00,
            strength=0.7,
            touch_count=2
        )
        
        zone_high_touch = ZoneFactory.create_zone(
            upper=3271.00,
            lower=3269.00,
            strength=0.7,
            touch_count=8
        )
        
        score_low = scorer.calculate_score(pattern, [zone_low_touch], {})
        score_high = scorer.calculate_score(pattern, [zone_high_touch], {})
        
        # タッチ回数が多い方が高スコア
        assert score_high.total_score > score_low.total_score
    
    def test_inactive_zone_handling(self, scorer):
        """非アクティブゾーンの処理"""
        pattern = SignalFactory.create_pattern_signal()
        pattern.entry_point = Decimal("3270.00")
        
        zones = [
            Zone(
                id="inactive_zone",
                symbol="XAUUSD",
                upper_bound=Decimal("3271.00"),
                lower_bound=Decimal("3269.00"),
                zone_type=ZoneType.SUPPORT,
                strength=0.9,
                touch_count=5,
                status=ZoneStatus.INACTIVE,  # 非アクティブ
                created_at=datetime.now(timezone.utc),
                last_touched=datetime.now(timezone.utc)
            )
        ]
        
        score = scorer.calculate_score(pattern, zones, {})
        
        # 非アクティブゾーンは無視される
        assert score.total_score < 50.0
    
    def test_score_normalization(self, scorer):
        """スコアの正規化テスト"""
        pattern = SignalFactory.create_pattern_signal()
        
        # 様々な条件でテスト
        test_cases = [
            (Decimal("3270.00"), 3271.00, 3269.00, 0.9),  # ゾーン内
            (Decimal("3272.00"), 3271.00, 3269.00, 0.5),  # ゾーン外近接
            (Decimal("3280.00"), 3271.00, 3269.00, 0.3),  # 遠い
        ]
        
        for entry_price, zone_upper, zone_lower, zone_strength in test_cases:
            pattern.entry_point = entry_price
            zones = [ZoneFactory.create_zone(
                upper=zone_upper,
                lower=zone_lower,
                strength=zone_strength
            )]
            
            score = scorer.calculate_score(pattern, zones, {})
            
            # スコアは0-100の範囲内
            assert 0 <= score.total_score <= 100
            assert 0 <= score.zone_proximity_score <= 100
            assert 0 <= score.zone_strength_score <= 100
    
    def test_edge_cases(self, scorer):
        """エッジケースのテスト"""
        pattern = SignalFactory.create_pattern_signal()
        
        # 空のゾーンリスト
        score = scorer.calculate_score(pattern, [], {})
        assert score.total_score == 0.0
        
        # Noneのゾーンリスト
        score = scorer.calculate_score(pattern, None, {})
        assert score.total_score == 0.0