import pytest
from datetime import datetime
from dataclasses import dataclass
from unittest.mock import Mock
from src.services.entry_point.zone_multiplier_service import ZoneMultiplierService
from src.domain.models.zone_multiplier import MultiplierConfig


@dataclass
class MockZoneInfo:
    """テスト用のゾーン情報モック"""
    price: float
    role_history: list
    reaction_count: int = 5


@dataclass  
class MockEMAInfo:
    """テスト用のEMA情報モック"""
    period: int
    value: float


class TestZoneMultiplierService:
    """ゾーン掛け算サービスのテストスイート"""
    
    def setup_method(self):
        """各テストの前に実行される初期化"""
        self.config = MultiplierConfig()
        self.service = ZoneMultiplierService(self.config)
    
    def test_power_zone_detection_with_ema_overlap(self):
        """パワーゾーン検出 - EMA重なりパターン"""
        # テストデータ準備
        target_zone = MockZoneInfo(price=2.03450, role_history=["support"])  # より現実的な価格
        ema_200 = MockEMAInfo(period=200, value=2.03449)  # 1pip以内  
        ema_values = [ema_200]
        nearby_zones = []
        market_data = {}
        
        # 分析実行
        result = self.service.analyze_zone_multiplier_effects(
            target_zone=target_zone,
            nearby_zones=nearby_zones,
            ema_values=ema_values,
            market_data=market_data,
            original_zone_score=20.0
        )
        
        # 検証
        assert result["zone_analysis"]["is_power_zone"] is True
        assert result["zone_analysis"]["power_level"] >= 1  # WEAK以上
        assert result["score_multipliers"]["final_multiplier"] > 1.0
        assert len(result["zone_analysis"]["components"]) >= 1
        
        # EMAコンポーネントの確認
        ema_component = next(
            (c for c in result["zone_analysis"]["components"] 
             if c["type"] == "ema_overlap"), None
        )
        assert ema_component is not None
        assert ema_component["details"]["ema_period"] == 200
    
    def test_zone_cluster_detection(self):
        """パワーゾーン検出 - ゾーンクラスターパターン"""
        # クラスター形成のテストデータ（50pips以内に3つ以上）
        target_zone = MockZoneInfo(price=2.03450, role_history=["support"])
        nearby_zones = [
            MockZoneInfo(price=2.03420, role_history=["resistance"]),  # 30pips
            MockZoneInfo(price=2.03480, role_history=["support"]),     # 30pips
            MockZoneInfo(price=2.03410, role_history=["resistance"]),  # 40pips
        ]
        ema_values = []
        market_data = {}
        
        result = self.service.analyze_zone_multiplier_effects(
            target_zone=target_zone,
            nearby_zones=nearby_zones,
            ema_values=ema_values,
            market_data=market_data,
            original_zone_score=20.0
        )
        
        # クラスター検出の確認
        assert result["zone_analysis"]["is_power_zone"] is True
        cluster_component = next(
            (c for c in result["zone_analysis"]["components"] 
             if c["type"] == "zone_cluster"), None
        )
        assert cluster_component is not None
        assert cluster_component["details"]["zone_count"] >= 3
    
    def test_role_reversal_detection(self):
        """パワーゾーン検出 - 役割転換パターン"""
        # 複数回の役割転換履歴を持つゾーン
        target_zone = MockZoneInfo(
            price=2034.50, 
            role_history=["support", "resistance", "support", "resistance", "support"]
        )
        nearby_zones = []
        ema_values = []
        market_data = {}
        
        result = self.service.analyze_zone_multiplier_effects(
            target_zone=target_zone,
            nearby_zones=nearby_zones,
            ema_values=ema_values,
            market_data=market_data,
            original_zone_score=20.0
        )
        
        # 役割転換検出の確認
        assert result["zone_analysis"]["is_power_zone"] is True
        reversal_component = next(
            (c for c in result["zone_analysis"]["components"] 
             if c["type"] == "role_reversal"), None
        )
        assert reversal_component is not None
        assert reversal_component["details"]["role_changes"] >= 2
    
    def test_regular_zone_analysis(self):
        """レギュラーゾーン分析 - パワーゾーンコンポーネントなし"""
        # 特別な特徴のない単独ゾーン
        target_zone = MockZoneInfo(price=2034.50, role_history=["support"])
        nearby_zones = [MockZoneInfo(price=2020.00, role_history=["resistance"])]  # 遠いゾーン
        ema_values = [MockEMAInfo(period=200, value=2020.00)]  # 遠いEMA
        market_data = {}
        
        result = self.service.analyze_zone_multiplier_effects(
            target_zone=target_zone,
            nearby_zones=nearby_zones,
            ema_values=ema_values,
            market_data=market_data,
            original_zone_score=20.0
        )
        
        # レギュラーゾーンの確認
        assert result["zone_analysis"]["is_power_zone"] is False
        assert result["zone_analysis"]["power_level"] == 0
        assert result["score_multipliers"]["final_multiplier"] == 1.0
        assert result["execution_priority"]["immediate_execution"] is False
    
    def test_quick_power_zone_check(self):
        """クイックパワーゾーン判定テスト"""
        # EMA重なりあり
        target_zone = MockZoneInfo(price=2.03450, role_history=["support"])
        ema_values = [MockEMAInfo(period=200, value=2.03449)]  # 1pip以内
        
        is_power_zone = self.service.quick_power_zone_check(target_zone, ema_values)
        assert is_power_zone is True
        
        # 役割転換あり
        target_zone_reversal = MockZoneInfo(
            price=2.03450, 
            role_history=["support", "resistance", "support"]
        )
        ema_values_far = [MockEMAInfo(period=200, value=2.02000)]  # 遠いEMA
        
        is_power_zone_reversal = self.service.quick_power_zone_check(target_zone_reversal, ema_values_far)
        assert is_power_zone_reversal is True
        
        # 条件なし
        regular_zone = MockZoneInfo(price=2.03450, role_history=["support"])
        is_regular = self.service.quick_power_zone_check(regular_zone, ema_values_far)
        assert is_regular is False
    
    def test_execution_parameters_extraction(self):
        """実行パラメータ抽出テスト"""
        # パワーゾーン分析結果のモック
        analysis_result = {
            "zone_analysis": {"is_power_zone": True, "power_level": 4},
            "execution_priority": {
                "final_priority": 18,
                "immediate_execution": True,
                "weight_multiplier": 2.0,
                "execution_privileges": {"bypass_correlation": True}
            },
            "risk_reward_enhancement": {
                "optimized_sl_distance": 14.0,
                "optimized_tp_distance": 90.0
            },
            "overall_confidence": 0.85
        }
        
        params = self.service.get_execution_parameters(analysis_result)
        
        assert params["should_execute"] is True
        assert params["execution_priority"] == 18
        assert params["immediate_execution"] is True
        assert params["weight_multiplier"] == 2.0
        assert params["enhanced_sl_distance"] == 14.0
        assert params["enhanced_tp_distance"] == 90.0
        assert params["confidence_level"] == 0.85
        assert params["position_size_multiplier"] > 1.0
    
    def test_summary_report_generation(self):
        """サマリーレポート生成テスト"""
        # パワーゾーン結果
        power_zone_result = {
            "zone_analysis": {"is_power_zone": True, "power_level": 3},
            "score_multipliers": {"final_multiplier": 2.5},
            "execution_priority": {"immediate_execution": True, "weight_multiplier": 2.0},
            "risk_reward_enhancement": {"enhanced_rr": 3.2}
        }
        
        summary = self.service.generate_summary_report(power_zone_result)
        assert "パワーゾーン検出" in summary
        assert "2.50x乗数適用" in summary
        assert "即時実行フラグ" in summary
        assert "2倍重み付け" in summary
        assert "RR比 3.2" in summary
        
        # レギュラーゾーン結果
        regular_zone_result = {
            "zone_analysis": {"is_power_zone": False, "power_level": 0},
            "score_multipliers": {"final_multiplier": 1.0}
        }
        
        regular_summary = self.service.generate_summary_report(regular_zone_result)
        assert regular_summary == "レギュラーゾーン: 標準的なエントリー条件を適用"
    
    def test_maximum_multiplier_cap(self):
        """最大乗数制限テスト"""
        # 極端なパワーゾーン条件
        target_zone = MockZoneInfo(
            price=2.03450, 
            role_history=["support", "resistance", "support", "resistance", "support"]
        )
        nearby_zones = [
            MockZoneInfo(price=2.03425, role_history=["resistance"]),  # 25pips
            MockZoneInfo(price=2.03475, role_history=["support"]),     # 25pips
            MockZoneInfo(price=2.03415, role_history=["resistance"]),  # 35pips
            MockZoneInfo(price=2.03485, role_history=["support"])      # 35pips
        ]
        ema_values = [MockEMAInfo(period=200, value=2.03448)]  # EMA重なり
        market_data = {}
        
        result = self.service.analyze_zone_multiplier_effects(
            target_zone=target_zone,
            nearby_zones=nearby_zones,
            ema_values=ema_values,
            market_data=market_data,
            original_zone_score=20.0
        )
        
        # 3.0倍上限の確認
        assert result["score_multipliers"]["final_multiplier"] <= 3.0
        # 複数のコンポーネントが検出されることを確認
        assert len(result["zone_analysis"]["components"]) >= 2
        if result["score_multipliers"]["final_multiplier"] >= 3.0:
            assert result["score_multipliers"]["capped_at_maximum"] is True
    
    def test_immediate_execution_flag(self):
        """即時実行フラグテスト"""
        # 乗数2.5x以上で即時実行
        target_zone = MockZoneInfo(
            price=2034.50,
            role_history=["support", "resistance", "support"]
        )
        nearby_zones = [
            MockZoneInfo(price=2034.30, role_history=["resistance"]),
            MockZoneInfo(price=2034.70, role_history=["support"]),
            MockZoneInfo(price=2034.20, role_history=["resistance"])
        ]
        ema_values = [MockEMAInfo(period=200, value=2034.51)]
        market_data = {}
        
        result = self.service.analyze_zone_multiplier_effects(
            target_zone=target_zone,
            nearby_zones=nearby_zones,
            ema_values=ema_values,
            market_data=market_data,
            original_zone_score=20.0
        )
        
        # 即時実行条件の確認
        if result["score_multipliers"]["final_multiplier"] >= 2.5:
            assert result["execution_priority"]["immediate_execution"] is True
        else:
            assert result["execution_priority"]["immediate_execution"] is False
    
    def test_risk_reward_optimization(self):
        """リスクリワード最適化テスト"""
        target_zone = MockZoneInfo(price=2.03450, role_history=["support"])
        nearby_zones = [
            MockZoneInfo(price=2.04000, role_history=["resistance"], reaction_count=5)  # メジャーゾーン
        ]
        ema_values = [MockEMAInfo(period=200, value=2.03448)]  # パワーゾーンを作成
        market_data = {}
        
        result = self.service.analyze_zone_multiplier_effects(
            target_zone=target_zone,
            nearby_zones=nearby_zones,
            ema_values=ema_values,
            market_data=market_data,
            original_zone_score=20.0,
            entry_price=2.03450,
            trade_direction="long"
        )
        
        # RR最適化の確認
        rr_enhancement = result.get("risk_reward_enhancement")
        if rr_enhancement:
            # パワーゾーンの場合、enhanced_rrは元のRRより大きいはず
            if result["zone_analysis"]["is_power_zone"]:
                assert rr_enhancement["enhanced_rr"] > rr_enhancement["original_rr"]
            assert float(rr_enhancement["sl_reduction"].rstrip('%')) >= 0
            assert float(rr_enhancement["tp_extension"].rstrip('%')) >= 0