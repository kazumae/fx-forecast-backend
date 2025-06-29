"""バックテストエンジンのテスト"""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pandas as pd
import numpy as np

from src.domain.models.backtest import (
    BacktestConfig, BacktestResult, BacktestTrade,
    TradeStatus, ExitReason
)
from src.domain.models.zone import Zone, ZoneType
from src.services.backtest import BacktestEngine
from tests.utils import CandlestickFactory, ZoneFactory


@pytest.fixture
def backtest_config():
    """バックテスト設定"""
    return BacktestConfig(
        symbol="XAUUSD",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
        initial_capital=Decimal("10000"),
        position_size=Decimal("0.1"),
        commission=Decimal("2"),
        slippage=Decimal("0.5"),
        max_positions=3,
        use_fixed_size=True,
        parameters={
            "min_confidence": 70.0,
            "min_rr_ratio": 1.5,
            "max_risk_pips": 50.0
        }
    )


@pytest.fixture
def sample_market_data():
    """サンプル市場データ"""
    dates = pd.date_range(
        start='2024-01-01', 
        end='2024-01-31', 
        freq='1h', 
        tz=timezone.utc
    )
    
    # ランダムウォークで価格生成
    np.random.seed(42)
    prices = 3275.0
    data = []
    
    for date in dates:
        change = np.random.normal(0, 2)
        prices += change
        
        high = prices + abs(np.random.normal(0, 1))
        low = prices - abs(np.random.normal(0, 1))
        open_price = prices + np.random.normal(0, 0.5)
        close_price = prices + np.random.normal(0, 0.5)
        
        data.append({
            "timestamp": date,
            "open": open_price,
            "high": max(high, open_price, close_price),
            "low": min(low, open_price, close_price),
            "close": close_price,
            "volume": int(1000 + np.random.normal(0, 200))
        })
    
    return pd.DataFrame(data)


@pytest.fixture
def sample_zones():
    """サンプルゾーン"""
    return [
        ZoneFactory.create_zone(
            upper=3280.0,
            lower=3278.0,
            zone_type=ZoneType.RESISTANCE,
            strength=0.9
        ),
        ZoneFactory.create_zone(
            upper=3270.0,
            lower=3268.0,
            zone_type=ZoneType.SUPPORT,
            strength=0.85
        )
    ]


class TestBacktestEngine:
    """バックテストエンジンのテスト"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, backtest_config):
        """初期化テスト"""
        engine = BacktestEngine(backtest_config)
        
        assert engine.config == backtest_config
        assert engine.current_equity == backtest_config.initial_capital
        assert engine.open_positions == []
        assert engine.closed_trades == []
        assert engine.max_equity == backtest_config.initial_capital
    
    @pytest.mark.asyncio
    async def test_position_size_calculation(self, backtest_config):
        """ポジションサイズ計算テスト"""
        engine = BacktestEngine(backtest_config)
        
        # ダミーシグナル作成
        from src.domain.models.entry_signal import (
            EntrySignal, SignalDirection, EntryOrderInfo,
            StopLossInfo, RiskRewardInfo, SignalMetadata,
            ExecutionInfo, OrderType
        )
        
        signal = EntrySignal(
            id="test_signal",
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            direction=SignalDirection.LONG,
            entry=EntryOrderInfo(
                price=Decimal("3275.50"),
                order_type=OrderType.MARKET,
                valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
                slippage_pips=1.0
            ),
            stop_loss=StopLossInfo(
                price=Decimal("3270.00"),
                distance_pips=55.0,
                reason="Zone-based SL"
            ),
            take_profits=[],
            risk_reward=RiskRewardInfo(
                risk_pips=55.0,
                tp1_reward_pips=110.0,
                tp1_rr_ratio=2.0,
                weighted_rr_ratio=2.0
            ),
            metadata=SignalMetadata(
                pattern_type="V_SHAPE_REVERSAL",
                confidence_score=0.85,
                zone_strength=0.9,
                timeframe="1m",
                analysis_version="1.0"
            ),
            execution=ExecutionInfo(
                priority="high",
                max_slippage=2.0,
                retry_count=3,
                execution_mode="immediate"
            )
        )
        
        # 固定サイズ
        size = engine._calculate_position_size(signal)
        assert size == Decimal("0.1")
        
        # リスクベースサイジング
        engine.config.use_fixed_size = False
        engine.config.risk_per_trade = Decimal("2.0")  # 2%リスク
        size = engine._calculate_position_size(signal)
        expected_size = (engine.current_equity * Decimal("0.02")) / Decimal("55.0")
        assert abs(size - expected_size) < Decimal("0.01")
    
    @pytest.mark.asyncio
    async def test_equity_curve_update(self, backtest_config):
        """エクイティカーブ更新テスト"""
        engine = BacktestEngine(backtest_config)
        
        # 初期状態
        assert len(engine.equity_curve) == 0
        
        # 更新
        timestamp = datetime.now(timezone.utc)
        engine._update_equity_curve(timestamp)
        
        assert len(engine.equity_curve) == 1
        assert engine.equity_curve[0].timestamp == timestamp
        assert engine.equity_curve[0].equity == engine.current_equity
        assert engine.equity_curve[0].drawdown == Decimal("0")
        
        # 損失後の更新
        engine.current_equity -= Decimal("100")
        engine._update_equity_curve(timestamp + timedelta(minutes=1))
        
        assert len(engine.equity_curve) == 2
        assert engine.equity_curve[1].drawdown == Decimal("100")
    
    @pytest.mark.asyncio
    async def test_trade_execution(self, backtest_config):
        """取引実行テスト"""
        engine = BacktestEngine(backtest_config)
        
        # ダミーシグナル
        from tests.utils import SignalFactory
        signal = SignalFactory.create_entry_signal(
            entry_price=3275.50,
            sl_price=3270.00,
            tp_prices=[3280.00, 3285.00]
        )
        
        # 実行
        timestamp = datetime.now(timezone.utc)
        trade = await engine._execute_signal(signal, timestamp)
        
        assert trade is not None
        assert trade.status == TradeStatus.OPEN
        assert trade.entry_time == timestamp
        assert trade.size == backtest_config.position_size
        assert len(engine.open_positions) == 1
        
        # スリッページ確認
        expected_price = signal.entry.price + Decimal("0.005")  # 0.5 pips
        assert trade.entry_price == expected_price
    
    @pytest.mark.asyncio
    async def test_position_management_stop_loss(self, backtest_config):
        """ストップロス管理テスト"""
        engine = BacktestEngine(backtest_config)
        
        # オープンポジション追加
        trade = BacktestTrade(
            id="test_trade",
            entry_time=datetime.now(timezone.utc),
            exit_time=None,
            symbol="XAUUSD",
            direction="long",
            entry_price=Decimal("3275.00"),
            exit_price=None,
            size=Decimal("0.1"),
            pnl=None,
            pnl_percentage=None,
            pattern="V_SHAPE_REVERSAL",
            entry_score=0.85,
            exit_reason=None,
            status=TradeStatus.OPEN,
            metadata={
                "stop_loss": 3270.00,
                "take_profits": [{"level": 1, "price": 3280.00}]
            }
        )
        engine.open_positions.append(trade)
        
        # SL到達
        context = {
            "current_price": Decimal("3269.50")  # SL以下
        }
        
        await engine._manage_positions(context, datetime.now(timezone.utc))
        
        assert len(engine.open_positions) == 0
        assert len(engine.closed_trades) == 1
        assert engine.closed_trades[0].exit_reason == ExitReason.STOP_LOSS
    
    @pytest.mark.asyncio
    async def test_position_management_take_profit(self, backtest_config):
        """テイクプロフィット管理テスト"""
        engine = BacktestEngine(backtest_config)
        
        # オープンポジション追加
        trade = BacktestTrade(
            id="test_trade",
            entry_time=datetime.now(timezone.utc),
            exit_time=None,
            symbol="XAUUSD",
            direction="long",
            entry_price=Decimal("3275.00"),
            exit_price=None,
            size=Decimal("0.1"),
            pnl=None,
            pnl_percentage=None,
            pattern="V_SHAPE_REVERSAL",
            entry_score=0.85,
            exit_reason=None,
            status=TradeStatus.OPEN,
            metadata={
                "stop_loss": 3270.00,
                "take_profits": [{"level": 1, "price": 3280.00}]
            }
        )
        engine.open_positions.append(trade)
        
        # TP到達
        context = {
            "current_price": Decimal("3280.50")  # TP以上
        }
        
        await engine._manage_positions(context, datetime.now(timezone.utc))
        
        assert len(engine.open_positions) == 0
        assert len(engine.closed_trades) == 1
        assert engine.closed_trades[0].exit_reason == ExitReason.TAKE_PROFIT
        assert engine.closed_trades[0].pnl > 0
    
    @pytest.mark.asyncio
    async def test_performance_metrics_calculation(self, backtest_config):
        """パフォーマンスメトリクス計算テスト"""
        engine = BacktestEngine(backtest_config)
        
        # ダミー取引追加
        base_time = datetime.now(timezone.utc)
        trades = [
            # 勝ち取引
            BacktestTrade(
                id="trade1",
                entry_time=base_time,
                exit_time=base_time + timedelta(hours=1),
                symbol="XAUUSD",
                direction="long",
                entry_price=Decimal("3275.00"),
                exit_price=Decimal("3280.00"),
                size=Decimal("0.1"),
                pnl=Decimal("50.00"),
                pnl_percentage=Decimal("0.15"),
                pattern="V_SHAPE_REVERSAL",
                entry_score=0.85,
                exit_reason=ExitReason.TAKE_PROFIT,
                status=TradeStatus.CLOSED,
                metadata={"stop_loss": 3270.00}
            ),
            # 負け取引
            BacktestTrade(
                id="trade2",
                entry_time=base_time + timedelta(hours=2),
                exit_time=base_time + timedelta(hours=3),
                symbol="XAUUSD",
                direction="short",
                entry_price=Decimal("3285.00"),
                exit_price=Decimal("3290.00"),
                size=Decimal("0.1"),
                pnl=Decimal("-50.00"),
                pnl_percentage=Decimal("-0.17"),
                pattern="EMA_SQUEEZE",
                entry_score=0.75,
                exit_reason=ExitReason.STOP_LOSS,
                status=TradeStatus.CLOSED,
                metadata={"stop_loss": 3290.00}
            )
        ]
        
        engine.closed_trades = trades
        engine.max_consecutive_wins = 1
        engine.max_consecutive_losses = 1
        
        metrics = engine._calculate_performance_metrics()
        
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == 0.5
        assert metrics.gross_profit == Decimal("50.00")
        assert metrics.gross_loss == Decimal("-50.00")
        assert metrics.net_profit == Decimal("0.00")
        assert metrics.avg_win == Decimal("50.00")
        assert metrics.avg_loss == Decimal("-50.00")
    
    @pytest.mark.asyncio
    async def test_pattern_analysis(self, backtest_config):
        """パターン分析テスト"""
        engine = BacktestEngine(backtest_config)
        
        # ダミー取引追加
        base_time = datetime.now(timezone.utc)
        engine.closed_trades = [
            BacktestTrade(
                id=f"trade{i}",
                entry_time=base_time + timedelta(hours=i),
                exit_time=base_time + timedelta(hours=i+1),
                symbol="XAUUSD",
                direction="long",
                entry_price=Decimal("3275.00"),
                exit_price=Decimal("3280.00") if i % 2 == 0 else Decimal("3270.00"),
                size=Decimal("0.1"),
                pnl=Decimal("50.00") if i % 2 == 0 else Decimal("-50.00"),
                pnl_percentage=Decimal("0.15") if i % 2 == 0 else Decimal("-0.15"),
                pattern="V_SHAPE_REVERSAL" if i < 2 else "EMA_SQUEEZE",
                entry_score=0.85,
                exit_reason=ExitReason.TAKE_PROFIT if i % 2 == 0 else ExitReason.STOP_LOSS,
                status=TradeStatus.CLOSED,
                metadata={}
            )
            for i in range(4)
        ]
        
        pattern_analysis = engine._analyze_patterns()
        
        assert len(pattern_analysis) == 2
        
        # V_SHAPE_REVERSALの確認
        v_shape = next(p for p in pattern_analysis if p.pattern_type == "V_SHAPE_REVERSAL")
        assert v_shape.count == 2
        assert v_shape.win_rate == 0.5
        
        # EMA_SQUEEZEの確認
        ema = next(p for p in pattern_analysis if p.pattern_type == "EMA_SQUEEZE")
        assert ema.count == 2
        assert ema.win_rate == 0.5
    
    @pytest.mark.asyncio
    async def test_full_backtest_run(
        self, 
        backtest_config, 
        sample_market_data, 
        sample_zones
    ):
        """完全なバックテスト実行テスト"""
        engine = BacktestEngine(backtest_config)
        
        # 市場コンテキスト
        market_context = {
            "min_confidence": 70.0,
            "min_rr_ratio": 1.5,
            "enable_zone_validation": True
        }
        
        # バックテスト実行
        result = await engine.run(
            sample_market_data,
            sample_zones,
            market_context
        )
        
        assert isinstance(result, BacktestResult)
        assert result.config == backtest_config
        assert result.performance is not None
        assert isinstance(result.trades, list)
        assert isinstance(result.pattern_analysis, list)
        assert isinstance(result.time_analysis, list)
        assert len(result.equity_curve) > 0
        assert isinstance(result.monthly_returns, dict)
        assert isinstance(result.summary, dict)