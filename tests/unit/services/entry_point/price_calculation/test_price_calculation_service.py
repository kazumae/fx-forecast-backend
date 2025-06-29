import pytest
from decimal import Decimal
from datetime import datetime, timezone
from src.services.entry_point.price_calculation import (
    PriceCalculationService,
    StopLossCalculator,
    TakeProfitCalculator,
    RiskRewardValidator,
    SpecialCaseHandler
)
from src.domain.models.entry_signal import SignalDirection
from src.domain.models.price_calculation import (
    PriceCalculationInput, CalculationMethod, AdjustmentType
)


class TestPriceCalculationService:
    """価格計算サービスのテスト"""
    
    @pytest.fixture
    def service(self):
        """テスト用サービスインスタンス"""
        config = {
            "min_sl_pips": 10.0,
            "max_sl_pips": 50.0,
            "min_rr_ratio": 1.5,
            "stop_loss": {
                "min_sl_pips": 10.0,
                "max_sl_pips": 50.0,
                "atr_multiplier": 1.5,
                "zone_buffer_pips": 2.0
            },
            "take_profit": {
                "default_tp_ratios": [1.0, 1.5, 2.5],
                "tp_percentages": [50, 30, 20],
                "min_tp_distance_pips": 5.0
            },
            "risk_reward": {
                "min_rr_ratio": 1.5,
                "target_rr_ratio": 2.0
            },
            "special_cases": {
                "volatility_thresholds": {"low": 10.0, "normal": 20.0, "high": 30.0},
                "news_factor": 1.5
            }
        }
        return PriceCalculationService(config)
    
    @pytest.fixture
    def sample_market_data(self):
        """サンプル市場データ"""
        return {
            "symbol": "XAUUSD",
            "volatility_level": "normal",
            "market_session": "london",
            "news_impact": False,
            "existing_positions": [],
            "swing_points": [
                {"price": 3270.00, "type": "low", "strength": 3},
                {"price": 3280.00, "type": "high", "strength": 4}
            ],
            "nearby_zones": [
                {
                    "id": "zone_1",
                    "price": 3282.00,
                    "type": "resistance",
                    "class": "A",
                    "strength": 0.8
                },
                {
                    "id": "zone_2",
                    "price": 3268.00,
                    "type": "support",
                    "class": "B",
                    "strength": 0.6
                }
            ]
        }
    
    def test_calculate_price_levels_long(self, service, sample_market_data):
        """ロングポジションの価格計算テスト"""
        entry_price = Decimal("3275.50")
        pattern_type = "V_SHAPE_REVERSAL"
        direction = SignalDirection.LONG
        current_atr = 15.0
        zone_info = {
            "price": 3275.00,
            "type": "support",
            "class": "A",
            "id": "zone_main"
        }
        
        result = service.calculate_price_levels(
            entry_price=entry_price,
            pattern_type=pattern_type,
            direction=direction,
            current_atr=current_atr,
            zone_info=zone_info,
            market_data=sample_market_data
        )
        
        # 基本的な検証
        assert result.stop_loss is not None
        assert len(result.take_profits) > 0
        assert result.risk_reward_analysis is not None
        assert result.adjustments is not None
        
        # SLがエントリーより下にあることを確認
        assert result.stop_loss.price < entry_price
        
        # TPがエントリーより上にあることを確認
        for tp in result.take_profits:
            assert tp.price > entry_price
        
        # RR比の検証
        assert result.risk_reward_analysis.rr_ratio_tp1 > 0
        assert result.risk_reward_analysis.meets_minimum is not None
    
    def test_calculate_price_levels_short(self, service, sample_market_data):
        """ショートポジションの価格計算テスト"""
        entry_price = Decimal("3280.00")
        pattern_type = "FALSE_BREAKOUT"
        direction = SignalDirection.SHORT
        current_atr = 18.0
        zone_info = {
            "price": 3282.00,
            "type": "resistance",
            "class": "A",
            "id": "zone_main"
        }
        
        result = service.calculate_price_levels(
            entry_price=entry_price,
            pattern_type=pattern_type,
            direction=direction,
            current_atr=current_atr,
            zone_info=zone_info,
            market_data=sample_market_data
        )
        
        # ショートの場合の検証
        assert result.stop_loss.price > entry_price
        for tp in result.take_profits:
            assert tp.price < entry_price
    
    def test_rr_ratio_adjustment(self, service):
        """RR比調整のテスト"""
        entry_price = Decimal("3275.00")
        pattern_type = "EMA_SQUEEZE"
        direction = SignalDirection.LONG
        current_atr = 12.0
        zone_info = {"price": 3275.00, "type": "support", "class": "B"}
        
        # 小さなATRで計算（RR比が不足する可能性）
        result = service.calculate_price_levels(
            entry_price=entry_price,
            pattern_type=pattern_type,
            direction=direction,
            current_atr=current_atr,
            zone_info=zone_info
        )
        
        # 調整後もRR比が改善されていることを確認
        if not result.risk_reward_analysis.meets_minimum:
            assert result.risk_reward_analysis.recommended_adjustment is not None
    
    def test_volatility_adjustment(self, service, sample_market_data):
        """ボラティリティ調整のテスト"""
        entry_price = Decimal("3275.00")
        pattern_type = "TREND_CONTINUATION"
        direction = SignalDirection.LONG
        zone_info = {"price": 3275.00, "type": "support", "class": "A"}
        
        # 高ボラティリティ
        high_vol_result = service.calculate_price_levels(
            entry_price=entry_price,
            pattern_type=pattern_type,
            direction=direction,
            current_atr=35.0,  # 高ATR
            zone_info=zone_info,
            market_data=sample_market_data
        )
        
        # 低ボラティリティ
        low_vol_result = service.calculate_price_levels(
            entry_price=entry_price,
            pattern_type=pattern_type,
            direction=direction,
            current_atr=8.0,  # 低ATR
            zone_info=zone_info,
            market_data=sample_market_data
        )
        
        # 高ボラティリティ時の方がSL距離が大きいことを確認
        assert high_vol_result.stop_loss.distance_pips > low_vol_result.stop_loss.distance_pips
    
    def test_news_impact_adjustment(self, service, sample_market_data):
        """ニュースインパクト調整のテスト"""
        entry_price = Decimal("3275.00")
        pattern_type = "V_SHAPE_REVERSAL"
        direction = SignalDirection.LONG
        current_atr = 15.0
        zone_info = {"price": 3275.00, "type": "support", "class": "A"}
        
        # ニュースあり
        news_data = sample_market_data.copy()
        news_data["news_impact"] = True
        news_data["news_events"] = [
            {"title": "FOMC Meeting", "time": datetime.now(timezone.utc)}
        ]
        
        news_result = service.calculate_price_levels(
            entry_price=entry_price,
            pattern_type=pattern_type,
            direction=direction,
            current_atr=current_atr,
            zone_info=zone_info,
            market_data=news_data
        )
        
        # ニュースなし
        no_news_result = service.calculate_price_levels(
            entry_price=entry_price,
            pattern_type=pattern_type,
            direction=direction,
            current_atr=current_atr,
            zone_info=zone_info,
            market_data=sample_market_data
        )
        
        # ニュース時の調整係数が適用されていることを確認
        assert news_result.adjustments.news_factor > 1.0
        assert no_news_result.adjustments.news_factor == 1.0
    
    def test_validate_price_levels(self, service):
        """価格レベル検証のテスト"""
        entry_price = Decimal("3275.00")
        
        # 有効なロングポジション
        valid_long = service.validate_price_levels(
            entry_price=entry_price,
            stop_loss_price=Decimal("3270.00"),
            take_profit_prices=[Decimal("3280.00"), Decimal("3285.00")],
            direction=SignalDirection.LONG
        )
        assert valid_long["is_valid"] is True
        assert len(valid_long["errors"]) == 0
        
        # 無効なロングポジション（SLが高すぎる）
        invalid_long = service.validate_price_levels(
            entry_price=entry_price,
            stop_loss_price=Decimal("3280.00"),  # エントリーより上
            take_profit_prices=[Decimal("3285.00")],
            direction=SignalDirection.LONG
        )
        assert invalid_long["is_valid"] is False
        assert len(invalid_long["errors"]) > 0
    
    def test_suggest_improvements(self, service):
        """改善提案のテスト"""
        from src.domain.models.price_calculation import StopLossCalculation, TakeProfitLevel
        
        entry_price = Decimal("3275.00")
        
        # 現在の設定（改善の余地あり）
        current_sl = StopLossCalculation(
            price=Decimal("3265.00"),
            distance_pips=100.0,  # 大きすぎるSL
            calculation_method=CalculationMethod.FIXED_PIPS,
            details="Fixed 100 pips"
        )
        
        current_tps = [
            TakeProfitLevel(
                level=1,
                price=Decimal("3280.00"),
                distance_pips=50.0,
                percentage=100.0,
                reason="Single TP"
            )
        ]
        
        suggestions = service.suggest_improvements(
            current_sl=current_sl,
            current_tps=current_tps,
            entry_price=entry_price,
            direction=SignalDirection.LONG,
            pattern_type="V_SHAPE_REVERSAL",
            current_atr=15.0
        )
        
        # SLに関する提案があることを確認
        assert len(suggestions["sl_suggestions"]) > 0
        # 複数TPの提案があることを確認
        assert len(suggestions["tp_suggestions"]) > 0
    
    def test_multiple_tp_levels(self, service, sample_market_data):
        """複数TPレベルのテスト"""
        entry_price = Decimal("3275.00")
        pattern_type = "TREND_CONTINUATION"
        direction = SignalDirection.LONG
        current_atr = 20.0
        zone_info = {"price": 3275.00, "type": "support", "class": "A"}
        
        result = service.calculate_price_levels(
            entry_price=entry_price,
            pattern_type=pattern_type,
            direction=direction,
            current_atr=current_atr,
            zone_info=zone_info,
            market_data=sample_market_data
        )
        
        # 複数のTPが設定されていることを確認
        assert len(result.take_profits) >= 2
        
        # TPの割合の合計が100%であることを確認
        total_percentage = sum(tp.percentage for tp in result.take_profits)
        assert abs(total_percentage - 100.0) < 0.01
        
        # TPが段階的に遠くなっていることを確認
        for i in range(1, len(result.take_profits)):
            assert result.take_profits[i].distance_pips > result.take_profits[i-1].distance_pips


class TestStopLossCalculator:
    """ストップロス計算器のテスト"""
    
    @pytest.fixture
    def calculator(self):
        config = {
            "min_sl_pips": 10.0,
            "max_sl_pips": 50.0,
            "atr_multiplier": 1.5,
            "zone_buffer_pips": 2.0
        }
        return StopLossCalculator(config)
    
    def test_zone_based_calculation(self, calculator):
        """ゾーンベースSL計算のテスト"""
        input_data = PriceCalculationInput(
            entry_price=Decimal("3275.00"),
            pattern_type="EMA_SQUEEZE",
            current_atr=15.0,
            zone_info={
                "price": 3270.00,
                "type": "support",
                "class": "A",
                "id": "zone_1"
            }
        )
        
        result = calculator.calculate_stop_loss(
            input_data, SignalDirection.LONG
        )
        
        assert result.calculation_method == CalculationMethod.ZONE_BASED
        assert result.zone_reference == "zone_1"
        assert result.price < input_data.entry_price
    
    def test_swing_based_calculation(self, calculator):
        """スイングベースSL計算のテスト"""
        input_data = PriceCalculationInput(
            entry_price=Decimal("3275.00"),
            pattern_type="V_SHAPE_REVERSAL",
            current_atr=15.0,
            zone_info={"price": 3275.00, "type": "support"}
        )
        
        swing_points = [
            {"price": 3270.00, "type": "low", "strength": 3},
            {"price": 3280.00, "type": "high", "strength": 4}
        ]
        
        result = calculator.calculate_stop_loss(
            input_data, SignalDirection.LONG, swing_points
        )
        
        # スイングローの下にSLが設定されることを確認
        assert result.price < Decimal("3270.00")
        assert "スイング" in result.details


class TestRiskRewardValidator:
    """リスクリワード検証器のテスト"""
    
    @pytest.fixture
    def validator(self):
        config = {
            "min_rr_ratio": 1.5,
            "target_rr_ratio": 2.0,
            "max_sl_adjustment": 0.8,
            "max_tp_adjustment": 1.5
        }
        return RiskRewardValidator(config)
    
    def test_rr_analysis(self, validator):
        """RR分析のテスト"""
        from src.domain.models.price_calculation import StopLossCalculation, TakeProfitLevel
        
        stop_loss = StopLossCalculation(
            price=Decimal("3270.00"),
            distance_pips=50.0,
            calculation_method=CalculationMethod.ATR_BASED,
            details="ATR based"
        )
        
        take_profits = [
            TakeProfitLevel(
                level=1,
                price=Decimal("3280.00"),
                distance_pips=50.0,
                percentage=50.0,
                reason="TP1"
            ),
            TakeProfitLevel(
                level=2,
                price=Decimal("3290.00"),
                distance_pips=150.0,
                percentage=50.0,
                reason="TP2"
            )
        ]
        
        analysis = validator.validate_and_analyze(
            stop_loss, take_profits, Decimal("3275.00"), SignalDirection.LONG
        )
        
        assert analysis.risk_amount == 50.0
        assert analysis.reward_tp1 == 50.0
        assert analysis.rr_ratio_tp1 == 1.0
        # 加重平均: (1.0 * 0.5) + (3.0 * 0.5) = 2.0
        assert analysis.rr_ratio_weighted == 2.0
        assert analysis.meets_minimum is True