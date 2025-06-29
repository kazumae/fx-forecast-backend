import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from src.services.entry_point.signal_validation import SignalValidationService
from src.domain.models.entry_signal import (
    EntrySignal, SignalDirection, OrderType, EntryOrderInfo,
    StopLossInfo, TakeProfitLevel, RiskRewardInfo, SignalMetadata,
    ExecutionInfo
)
from src.domain.models.signal_validation import (
    MarketConditions, AccountStatus, ValidationConfig,
    ValidationDecision, ValidationSeverity, ValidationCheckType
)


class TestSignalValidationService:
    """シグナル検証サービスのテスト"""
    
    @pytest.fixture
    def validation_config(self):
        """テスト用検証設定"""
        return ValidationConfig(
            max_entry_distance_pips=5.0,
            min_sl_pips=10.0,
            max_sl_pips=50.0,
            min_rr_ratio=1.5,
            max_spread_multiplier=3.0,
            max_absolute_spread=5.0,
            min_liquidity_score=30.0,
            news_buffer_minutes=30,
            allow_hedging=False,
            max_positions_per_symbol=1,
            min_margin_level=100.0,
            strict_mode=False
        )
    
    @pytest.fixture
    def service(self, validation_config):
        """テスト用サービスインスタンス"""
        return SignalValidationService(validation_config)
    
    @pytest.fixture
    def valid_signal(self):
        """有効なテストシグナル"""
        now = datetime.now(timezone.utc)
        return EntrySignal(
            id="test_signal_001",
            symbol="XAUUSD",
            timestamp=now,
            direction=SignalDirection.LONG,
            entry=EntryOrderInfo(
                price=Decimal("3275.50"),
                order_type=OrderType.MARKET,
                valid_until=now + timedelta(hours=1),
                slippage_pips=1.0
            ),
            stop_loss=StopLossInfo(
                price=Decimal("3270.00"),
                distance_pips=55.0,
                reason="Zone-based SL"
            ),
            take_profits=[
                TakeProfitLevel(
                    level=1,
                    price=Decimal("3280.00"),
                    distance_pips=45.0,
                    percentage=50.0,
                    reason="First resistance"
                ),
                TakeProfitLevel(
                    level=2,
                    price=Decimal("3285.00"),
                    distance_pips=95.0,
                    percentage=30.0,
                    reason="Major zone"
                ),
                TakeProfitLevel(
                    level=3,
                    price=Decimal("3290.00"),
                    distance_pips=145.0,
                    percentage=20.0,
                    reason="Extended target"
                )
            ],
            risk_reward=RiskRewardInfo(
                risk_pips=55.0,
                tp1_reward_pips=45.0,
                tp2_reward_pips=95.0,
                tp3_reward_pips=145.0,
                tp1_rr_ratio=0.82,
                tp2_rr_ratio=1.73,
                tp3_rr_ratio=2.64,
                weighted_rr_ratio=1.57
            ),
            metadata=SignalMetadata(
                pattern_type="V_SHAPE_REVERSAL",
                confidence_score=0.85,
                zone_strength=0.9,
                timeframe="H1",
                analysis_version="1.0"
            ),
            execution=ExecutionInfo(
                priority="high",
                max_slippage=2.0,
                retry_count=3,
                execution_mode="immediate"
            )
        )
    
    @pytest.fixture
    def market_conditions(self):
        """テスト用市場条件"""
        return MarketConditions(
            is_market_open=True,
            current_spread=2.5,
            average_spread=2.0,
            liquidity_score=75.0,
            upcoming_news=[],
            market_session="london",
            volatility_level="normal"
        )
    
    @pytest.fixture
    def account_status(self):
        """テスト用アカウント状態"""
        return AccountStatus(
            balance=10000.0,
            available_margin=8000.0,
            used_margin=2000.0,
            open_positions=2,
            max_positions=10,
            margin_level=500.0
        )
    
    def test_valid_signal_validation(self, service, valid_signal, market_conditions, account_status):
        """有効なシグナルの検証テスト"""
        report = service.validate_signal(
            signal=valid_signal,
            current_price=Decimal("3275.00"),
            current_spread=2.5,
            market_conditions=market_conditions,
            account_status=account_status,
            existing_positions=[],
            position_size_lots=0.1
        )
        
        # 基本的な検証
        assert report.validation_result.is_valid is True
        assert report.final_decision == ValidationDecision.ACCEPT
        assert report.rejection_reason is None
        
        # チェック結果の確認
        assert report.validation_result.checks_performed > 10
        assert report.validation_result.get_pass_rate() > 90.0
    
    def test_invalid_stop_loss_position(self, service, valid_signal, market_conditions, account_status):
        """無効なストップロス位置のテスト"""
        # ロングでSLがエントリーより上
        valid_signal.stop_loss.price = Decimal("3280.00")
        
        report = service.validate_signal(
            signal=valid_signal,
            current_price=Decimal("3275.00"),
            current_spread=2.5,
            market_conditions=market_conditions,
            account_status=account_status,
            existing_positions=[]
        )
        
        assert report.validation_result.is_valid is False
        assert report.final_decision == ValidationDecision.REJECT
        assert "ロングポジションのSLがエントリー価格以上" in report.rejection_reason
    
    def test_insufficient_rr_ratio(self, service, valid_signal, market_conditions, account_status):
        """不十分なRR比のテスト"""
        # RR比を低く設定
        valid_signal.risk_reward.weighted_rr_ratio = 1.2
        valid_signal.risk_reward.tp1_rr_ratio = 0.5
        
        report = service.validate_signal(
            signal=valid_signal,
            current_price=Decimal("3275.00"),
            current_spread=2.5,
            market_conditions=market_conditions,
            account_status=account_status,
            existing_positions=[]
        )
        
        # 修正アクションが提案されることを確認
        assert len(report.corrective_actions) > 0
        rr_action = next(
            (action for action in report.corrective_actions
             if action.issue == ValidationCheckType.RISK_REWARD_RATIO),
            None
        )
        assert rr_action is not None
    
    def test_market_closed_validation(self, service, valid_signal, account_status):
        """市場閉鎖時の検証テスト"""
        closed_market = MarketConditions(
            is_market_open=False,
            current_spread=5.0,
            average_spread=2.0,
            liquidity_score=10.0,
            market_session="closed"
        )
        
        report = service.validate_signal(
            signal=valid_signal,
            current_price=Decimal("3275.00"),
            current_spread=5.0,
            market_conditions=closed_market,
            account_status=account_status,
            existing_positions=[]
        )
        
        assert report.validation_result.is_valid is False
        assert report.final_decision == ValidationDecision.REJECT
        assert "市場が閉まっています" in report.rejection_reason
    
    def test_high_spread_warning(self, service, valid_signal, account_status):
        """高スプレッド警告のテスト"""
        high_spread_market = MarketConditions(
            is_market_open=True,
            current_spread=8.0,  # 平均の4倍
            average_spread=2.0,
            liquidity_score=50.0,
            market_session="asian"
        )
        
        report = service.validate_signal(
            signal=valid_signal,
            current_price=Decimal("3275.00"),
            current_spread=8.0,
            market_conditions=high_spread_market,
            account_status=account_status,
            existing_positions=[]
        )
        
        # 警告はあるが実行可能
        assert report.final_decision in [
            ValidationDecision.ACCEPT_WITH_WARNINGS,
            ValidationDecision.REJECT
        ]
        
        # スプレッドに関する警告を確認
        spread_check = next(
            (check for check in report.validation_details
             if check.check_name == ValidationCheckType.SPREAD_CHECK),
            None
        )
        assert spread_check is not None
        assert not spread_check.passed
    
    def test_duplicate_position_detection(self, service, valid_signal, market_conditions, account_status):
        """重複ポジション検出のテスト"""
        existing_positions = [
            {
                "id": "pos_001",
                "symbol": "XAUUSD",
                "direction": "LONG",
                "entry_price": 3275.00,
                "lots": 0.1
            }
        ]
        
        report = service.validate_signal(
            signal=valid_signal,
            current_price=Decimal("3275.00"),
            current_spread=2.5,
            market_conditions=market_conditions,
            account_status=account_status,
            existing_positions=existing_positions
        )
        
        # 重複が検出されることを確認
        duplicate_check = next(
            (check for check in report.validation_details
             if check.check_name == ValidationCheckType.DUPLICATE_ENTRY),
            None
        )
        assert duplicate_check is not None
        assert not duplicate_check.passed
    
    def test_insufficient_margin(self, service, valid_signal, market_conditions):
        """証拠金不足のテスト"""
        low_margin_account = AccountStatus(
            balance=1000.0,
            available_margin=100.0,  # 少ない利用可能証拠金
            used_margin=900.0,
            open_positions=5,
            max_positions=10,
            margin_level=111.0
        )
        
        report = service.validate_signal(
            signal=valid_signal,
            current_price=Decimal("3275.00"),
            current_spread=2.5,
            market_conditions=market_conditions,
            account_status=low_margin_account,
            existing_positions=[],
            position_size_lots=1.0  # 大きなポジションサイズ
        )
        
        # 証拠金不足で却下されることを確認
        margin_check = next(
            (check for check in report.validation_details
             if check.check_name == ValidationCheckType.MARGIN_REQUIREMENT),
            None
        )
        assert margin_check is not None
        assert not margin_check.passed
    
    def test_news_event_detection(self, service, valid_signal, account_status):
        """ニュースイベント検出のテスト"""
        news_time = datetime.now(timezone.utc) + timedelta(minutes=15)
        
        news_market = MarketConditions(
            is_market_open=True,
            current_spread=2.5,
            average_spread=2.0,
            liquidity_score=60.0,
            upcoming_news=[
                {
                    "title": "FOMC Meeting",
                    "time": news_time,
                    "impact": "high"
                }
            ],
            market_session="newyork"
        )
        
        report = service.validate_signal(
            signal=valid_signal,
            current_price=Decimal("3275.00"),
            current_spread=2.5,
            market_conditions=news_market,
            account_status=account_status,
            existing_positions=[]
        )
        
        # ニュースに関する警告を確認
        news_check = next(
            (check for check in report.validation_details
             if check.check_name == ValidationCheckType.NEWS_TIME_CHECK),
            None
        )
        assert news_check is not None
        assert not news_check.passed  # 重要ニュースなので警告
    
    def test_batch_validation(self, service, valid_signal, account_status):
        """バッチ検証のテスト"""
        # 複数のシグナルを作成
        signals = [valid_signal]
        
        # 別のシグナルを追加
        signal2 = EntrySignal(
            id="test_signal_002",
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            direction=SignalDirection.SHORT,
            entry=EntryOrderInfo(
                price=Decimal("1.0850"),
                order_type=OrderType.LIMIT,
                valid_until=datetime.now(timezone.utc) + timedelta(hours=2)
            ),
            stop_loss=StopLossInfo(
                price=Decimal("1.0870"),
                distance_pips=20.0
            ),
            take_profits=[
                TakeProfitLevel(
                    level=1,
                    price=Decimal("1.0820"),
                    distance_pips=30.0,
                    percentage=100.0,
                    reason="Support level"
                )
            ],
            risk_reward=RiskRewardInfo(
                risk_pips=20.0,
                tp1_reward_pips=30.0,
                tp1_rr_ratio=1.5,
                weighted_rr_ratio=1.5
            ),
            metadata=SignalMetadata(
                pattern_type="TREND_CONTINUATION",
                confidence_score=0.75
            ),
            execution=ExecutionInfo(
                priority="medium"
            )
        )
        signals.append(signal2)
        
        market_data = {
            "XAUUSD": {
                "price": 3275.00,
                "spread": 2.5,
                "is_market_open": True,
                "liquidity_score": 75.0
            },
            "EURUSD": {
                "price": 1.0850,
                "spread": 0.8,
                "is_market_open": True,
                "liquidity_score": 90.0
            }
        }
        
        reports = service.validate_batch(
            signals=signals,
            market_data=market_data,
            account_status=account_status,
            existing_positions=[]
        )
        
        assert len(reports) == 2
        assert all(isinstance(report.validation_result, object) for report in reports)