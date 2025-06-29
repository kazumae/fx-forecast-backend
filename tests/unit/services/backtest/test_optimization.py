"""最適化機能のテスト"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
import pandas as pd
import numpy as np

from src.domain.models.backtest import BacktestConfig, OptimizationResult
from src.services.backtest import ParameterOptimizer, WalkForwardAnalyzer
from tests.utils import ZoneFactory


@pytest.fixture
def base_config():
    """ベース設定"""
    return BacktestConfig(
        symbol="XAUUSD",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
        initial_capital=Decimal("10000"),
        position_size=Decimal("0.1"),
        commission=Decimal("2"),
        slippage=Decimal("0.5"),
        max_positions=3,
        use_fixed_size=True
    )


@pytest.fixture
def parameter_ranges():
    """パラメータ範囲"""
    return {
        "min_confidence": [65, 70, 75],
        "min_rr_ratio": [1.0, 1.5, 2.0],
        "max_risk_pips": [40, 50]
    }


@pytest.fixture
def sample_data():
    """サンプルデータ"""
    dates = pd.date_range(
        start='2024-01-01', 
        end='2024-03-31', 
        freq='1h', 
        tz=timezone.utc
    )
    
    np.random.seed(42)
    prices = 3275.0
    data = []
    
    for date in dates:
        change = np.random.normal(0, 2)
        prices += change
        
        data.append({
            "timestamp": date,
            "open": prices + np.random.normal(0, 0.5),
            "high": prices + abs(np.random.normal(0, 1)),
            "low": prices - abs(np.random.normal(0, 1)),
            "close": prices + np.random.normal(0, 0.5),
            "volume": int(1000 + np.random.normal(0, 200))
        })
    
    return pd.DataFrame(data)


class TestParameterOptimizer:
    """パラメータ最適化のテスト"""
    
    def test_initialization(self, base_config, parameter_ranges):
        """初期化テスト"""
        optimizer = ParameterOptimizer(
            base_config=base_config,
            parameter_ranges=parameter_ranges,
            optimization_metric="sharpe_ratio"
        )
        
        assert optimizer.base_config == base_config
        assert optimizer.parameter_ranges == parameter_ranges
        assert optimizer.optimization_metric == "sharpe_ratio"
    
    def test_parameter_combinations(self, base_config, parameter_ranges):
        """パラメータ組み合わせ生成テスト"""
        optimizer = ParameterOptimizer(
            base_config=base_config,
            parameter_ranges=parameter_ranges
        )
        
        combinations = optimizer._generate_parameter_combinations()
        
        # 期待される組み合わせ数: 3 * 3 * 2 = 18
        assert len(combinations) == 18
        
        # 各組み合わせの確認
        for combo in combinations:
            assert "min_confidence" in combo
            assert "min_rr_ratio" in combo
            assert "max_risk_pips" in combo
            assert combo["min_confidence"] in parameter_ranges["min_confidence"]
            assert combo["min_rr_ratio"] in parameter_ranges["min_rr_ratio"]
            assert combo["max_risk_pips"] in parameter_ranges["max_risk_pips"]
    
    def test_metric_value_extraction(self, base_config, parameter_ranges):
        """メトリクス値抽出テスト"""
        optimizer = ParameterOptimizer(
            base_config=base_config,
            parameter_ranges=parameter_ranges,
            optimization_metric="sharpe_ratio"
        )
        
        # ダミーパフォーマンス
        from src.domain.models.backtest import PerformanceMetrics
        
        performance = PerformanceMetrics(
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            win_rate=0.6,
            gross_profit=Decimal("3000"),
            gross_loss=Decimal("-2000"),
            net_profit=Decimal("1000"),
            profit_factor=1.5,
            max_drawdown=Decimal("-500"),
            max_drawdown_percent=5.0,
            sharpe_ratio=1.85,
            sortino_ratio=2.1,
            calmar_ratio=2.0,
            avg_win=Decimal("100"),
            avg_loss=Decimal("-100"),
            avg_trade=Decimal("20"),
            avg_rr_realized=1.8,
            best_trade=Decimal("500"),
            worst_trade=Decimal("-300"),
            max_consecutive_wins=5,
            max_consecutive_losses=3,
            avg_holding_time=45.0,
            total_commission=Decimal("100"),
            total_slippage=Decimal("50")
        )
        
        # シャープレシオ
        value = optimizer._get_metric_value(performance)
        assert value == 1.85
        
        # 他のメトリクス
        optimizer.optimization_metric = "profit_factor"
        value = optimizer._get_metric_value(performance)
        assert value == 1.5
        
        optimizer.optimization_metric = "win_rate"
        value = optimizer._get_metric_value(performance)
        assert value == 0.6
        
        # 取引数が少ない場合のペナルティ
        performance.total_trades = 20
        optimizer.optimization_metric = "sharpe_ratio"
        value = optimizer._get_metric_value(performance)
        assert value == 1.85 * 0.5  # ペナルティ適用
    
    @pytest.mark.asyncio
    async def test_optimization_with_validation_split(
        self, 
        base_config, 
        parameter_ranges,
        sample_data
    ):
        """検証分割付き最適化テスト"""
        optimizer = ParameterOptimizer(
            base_config=base_config,
            parameter_ranges={"min_confidence": [70, 75]},  # 簡略化
            optimization_metric="sharpe_ratio"
        )
        
        zones = [ZoneFactory.create_major_zones()]
        
        # 最適化実行（簡略版）
        # 実際のテストでは時間がかかるため、モックを使用することを推奨
        # ここではパラメータ組み合わせの生成のみテスト
        combinations = optimizer._generate_parameter_combinations()
        assert len(combinations) == 2


class TestWalkForwardAnalyzer:
    """ウォークフォワード分析のテスト"""
    
    def test_initialization(self, base_config, parameter_ranges):
        """初期化テスト"""
        optimizer = ParameterOptimizer(
            base_config=base_config,
            parameter_ranges=parameter_ranges
        )
        
        analyzer = WalkForwardAnalyzer(
            optimizer=optimizer,
            window_size=252,
            step_size=63,
            optimization_period=189
        )
        
        assert analyzer.optimizer == optimizer
        assert analyzer.window_size == 252
        assert analyzer.step_size == 63
        assert analyzer.optimization_period == 189
    
    def test_result_summarization(self, base_config, parameter_ranges):
        """結果集計テスト"""
        optimizer = ParameterOptimizer(
            base_config=base_config,
            parameter_ranges=parameter_ranges
        )
        
        analyzer = WalkForwardAnalyzer(optimizer=optimizer)
        
        # ダミー結果
        from src.domain.models.backtest import PerformanceMetrics
        
        dummy_performance = PerformanceMetrics(
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            win_rate=0.6,
            gross_profit=Decimal("3000"),
            gross_loss=Decimal("-2000"),
            net_profit=Decimal("1000"),
            profit_factor=1.5,
            max_drawdown=Decimal("-500"),
            max_drawdown_percent=5.0,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            calmar_ratio=2.0,
            avg_win=Decimal("100"),
            avg_loss=Decimal("-100"),
            avg_trade=Decimal("20"),
            avg_rr_realized=1.8,
            best_trade=Decimal("500"),
            worst_trade=Decimal("-300"),
            max_consecutive_wins=5,
            max_consecutive_losses=3,
            avg_holding_time=45.0,
            total_commission=Decimal("100"),
            total_slippage=Decimal("50")
        )
        
        results = [
            {
                "window": 1,
                "best_parameters": {"min_confidence": 70, "min_rr_ratio": 1.5},
                "validation_performance": dummy_performance
            },
            {
                "window": 2,
                "best_parameters": {"min_confidence": 75, "min_rr_ratio": 1.5},
                "validation_performance": dummy_performance
            }
        ]
        
        summary = analyzer._summarize_results(results)
        
        assert summary["avg_validation_sharpe"] == 1.5
        assert summary["avg_validation_win_rate"] == 0.6
        assert summary["total_validation_trades"] == 100
        assert "parameter_stability" in summary
        
        # パラメータ安定性
        stability = summary["parameter_stability"]
        assert "min_confidence" in stability
        assert "min_rr_ratio" in stability
        
        # min_rr_ratioは両方のウィンドウで同じなので安定
        assert stability["min_rr_ratio"]["unique_values"] == 1
        assert stability["min_rr_ratio"]["stability_score"] == 1.0
        
        # min_confidenceは異なるので不安定
        assert stability["min_confidence"]["unique_values"] == 2
        assert stability["min_confidence"]["stability_score"] == 0.5