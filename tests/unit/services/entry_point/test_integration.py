"""エントリーポイント判定の統合テスト"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from src.services.entry_point.signal_generation import EntrySignalGenerator
from src.services.entry_point.price_calculation import PriceCalculationService
from src.services.entry_point.signal_validation import SignalValidationService
from src.domain.models.entry_signal import SignalDirection
from src.domain.models.signal_validation import (
    MarketConditions, AccountStatus, ValidationDecision
)
from tests.utils import SignalFactory, ZoneFactory


class TestEntryPointIntegration:
    """エントリーポイント判定の統合テスト"""
    
    @pytest.fixture
    def signal_generator(self):
        """シグナル生成器"""
        return EntrySignalGenerator()
    
    @pytest.fixture
    def price_calculator(self):
        """価格計算サービス"""
        return PriceCalculationService()
    
    @pytest.fixture
    def signal_validator(self):
        """シグナル検証サービス"""
        return SignalValidationService()
    
    def test_complete_signal_flow(self, signal_generator, price_calculator, signal_validator):
        """完全なシグナルフロー（生成→価格計算→検証）"""
        # 1. テストデータ準備
        pattern_signal = SignalFactory.create_pattern_signal()
        zones = ZoneFactory.create_major_zones()
        
        # 2. エントリーシグナル生成
        entry_signals = signal_generator.generate(
            pattern_signals=[pattern_signal],
            scoring_results=[{
                "pattern_id": "test_001",
                "total_score": 85.0,
                "confidence": 85.0,
                "recommendation": "STRONG_ENTRY"
            }],
            priority_results=[{
                "priority": "high",
                "rank": 1,
                "score": 85.0
            }],
            market_data={
                "current_price": Decimal("3275.50"),
                "spread": 2.5,
                "zones": zones
            }
        )
        
        assert len(entry_signals) > 0
        signal = entry_signals[0]
        
        # 3. 価格レベル計算
        price_result = price_calculator.calculate_price_levels(
            entry_price=signal.entry.price,
            pattern_type=signal.metadata.pattern_type,
            direction=signal.direction,
            current_atr=15.0,
            zone_info={
                "price": float(signal.entry.price),
                "type": "support",
                "class": "A"
            },
            market_data={
                "symbol": signal.symbol,
                "volatility_level": "normal",
                "nearby_zones": zones
            }
        )
        
        # 価格計算結果でシグナルを更新
        signal.stop_loss.price = price_result.stop_loss.price
        signal.stop_loss.distance_pips = price_result.stop_loss.distance_pips
        signal.take_profits = price_result.take_profits
        
        # 4. シグナル検証
        market_conditions = MarketConditions(
            is_market_open=True,
            current_spread=2.5,
            average_spread=2.0,
            liquidity_score=75.0
        )
        
        account_status = AccountStatus(
            balance=10000.0,
            available_margin=8000.0,
            used_margin=2000.0,
            open_positions=2,
            max_positions=10,
            margin_level=500.0
        )
        
        validation_report = signal_validator.validate_signal(
            signal=signal,
            current_price=Decimal("3275.50"),
            current_spread=2.5,
            market_conditions=market_conditions,
            account_status=account_status,
            existing_positions=[]
        )
        
        # 検証結果の確認
        assert validation_report.final_decision in [
            ValidationDecision.ACCEPT,
            ValidationDecision.ACCEPT_WITH_WARNINGS
        ]
        assert validation_report.validation_result.get_pass_rate() > 80.0
    
    def test_high_risk_signal_rejection(self, signal_generator, price_calculator, signal_validator):
        """高リスクシグナルの却下テスト"""
        # リスクの高いシグナルを生成
        signal = SignalFactory.create_entry_signal(
            entry_price=3275.00,
            sl_price=3265.00,  # 大きなSL距離（100pips）
            tp_prices=[3280.00]  # 小さなTP距離（50pips）
        )
        
        # RR比が悪い
        signal.risk_reward.weighted_rr_ratio = 0.5
        
        market_conditions = MarketConditions(
            is_market_open=True,
            current_spread=2.0,
            average_spread=2.0,
            liquidity_score=80.0
        )
        
        account_status = AccountStatus(
            balance=10000.0,
            available_margin=8000.0,
            used_margin=2000.0,
            open_positions=0,
            max_positions=10,
            margin_level=500.0
        )
        
        validation_report = signal_validator.validate_signal(
            signal=signal,
            current_price=Decimal("3275.00"),
            current_spread=2.0,
            market_conditions=market_conditions,
            account_status=account_status,
            existing_positions=[]
        )
        
        # RR比不足で却下されるはず
        assert validation_report.final_decision == ValidationDecision.REJECT
        assert "risk_reward_ratio" in str(validation_report.rejection_reason).lower()
    
    def test_market_closed_handling(self, signal_validator):
        """市場閉鎖時の処理テスト"""
        signal = SignalFactory.create_entry_signal()
        
        # 市場が閉まっている
        market_conditions = MarketConditions(
            is_market_open=False,
            current_spread=10.0,  # 高スプレッド
            average_spread=2.0,
            liquidity_score=10.0  # 低流動性
        )
        
        account_status = AccountStatus(
            balance=10000.0,
            available_margin=8000.0,
            used_margin=2000.0,
            open_positions=0,
            max_positions=10,
            margin_level=500.0
        )
        
        validation_report = signal_validator.validate_signal(
            signal=signal,
            current_price=Decimal("3275.00"),
            current_spread=10.0,
            market_conditions=market_conditions,
            account_status=account_status,
            existing_positions=[]
        )
        
        # 市場閉鎖で却下
        assert validation_report.final_decision == ValidationDecision.REJECT
        assert "市場が閉まっています" in validation_report.rejection_reason
    
    def test_position_limit_check(self, signal_validator):
        """ポジション数制限チェック"""
        signal = SignalFactory.create_entry_signal()
        
        market_conditions = MarketConditions(
            is_market_open=True,
            current_spread=2.0,
            average_spread=2.0,
            liquidity_score=80.0
        )
        
        # 最大ポジション数に達している
        account_status = AccountStatus(
            balance=10000.0,
            available_margin=8000.0,
            used_margin=2000.0,
            open_positions=10,  # 最大数
            max_positions=10,
            margin_level=500.0
        )
        
        validation_report = signal_validator.validate_signal(
            signal=signal,
            current_price=Decimal("3275.00"),
            current_spread=2.0,
            market_conditions=market_conditions,
            account_status=account_status,
            existing_positions=[]
        )
        
        # ポジション数制限で却下
        assert validation_report.final_decision == ValidationDecision.REJECT
        assert "最大ポジション数" in validation_report.rejection_reason
    
    def test_news_event_warning(self, signal_validator):
        """ニュースイベント警告テスト"""
        signal = SignalFactory.create_entry_signal()
        
        # 15分後に重要ニュース
        news_time = datetime.now(timezone.utc) + timedelta(minutes=15)
        
        market_conditions = MarketConditions(
            is_market_open=True,
            current_spread=2.0,
            average_spread=2.0,
            liquidity_score=80.0,
            upcoming_news=[{
                "title": "FOMC Meeting Minutes",
                "time": news_time,
                "impact": "high"
            }]
        )
        
        account_status = AccountStatus(
            balance=10000.0,
            available_margin=8000.0,
            used_margin=2000.0,
            open_positions=0,
            max_positions=10,
            margin_level=500.0
        )
        
        validation_report = signal_validator.validate_signal(
            signal=signal,
            current_price=Decimal("3275.00"),
            current_spread=2.0,
            market_conditions=market_conditions,
            account_status=account_status,
            existing_positions=[]
        )
        
        # ニュース警告付きで承認
        assert validation_report.final_decision == ValidationDecision.ACCEPT_WITH_WARNINGS
        assert len(validation_report.warnings) > 0
        assert any("news" in warning.lower() for warning in validation_report.warnings)
    
    def test_corrective_action_generation(self, price_calculator):
        """修正アクション生成テスト"""
        # RR比が不足する価格設定
        result = price_calculator.calculate_price_levels(
            entry_price=Decimal("3275.00"),
            pattern_type="V_SHAPE_REVERSAL",
            direction=SignalDirection.LONG,
            current_atr=10.0,  # 低ATR
            zone_info={
                "price": 3275.00,
                "type": "support",
                "class": "B"
            }
        )
        
        # RR比が最小要件を満たすよう調整されているはず
        assert result.risk_reward_analysis.meets_minimum
        assert result.risk_reward_analysis.weighted_rr_ratio >= 1.5
        
        # 調整が記録されているはず
        if result.adjustments.final_multiplier != 1.0:
            assert len(result.adjustments.adjustment_reasons) > 0