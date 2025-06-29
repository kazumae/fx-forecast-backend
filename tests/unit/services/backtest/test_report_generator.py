"""レポート生成のテスト"""
import pytest
import json
import pandas as pd
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import tempfile

from src.domain.models.backtest import (
    BacktestConfig, BacktestResult, BacktestTrade,
    PerformanceMetrics, PatternPerformance, TimeAnalysis,
    EquityPoint, TradeStatus, ExitReason,
    OptimizationResult
)
from src.services.backtest import BacktestReportGenerator


@pytest.fixture
def sample_backtest_result():
    """サンプルバックテスト結果"""
    config = BacktestConfig(
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
    
    trades = [
        BacktestTrade(
            id="bt_001",
            entry_time=datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc),
            exit_time=datetime(2024, 1, 2, 11, 45, tzinfo=timezone.utc),
            symbol="XAUUSD",
            direction="long",
            entry_price=Decimal("3275.30"),
            exit_price=Decimal("3281.50"),
            size=Decimal("0.1"),
            pnl=Decimal("62.00"),
            pnl_percentage=Decimal("0.19"),
            pattern="V_SHAPE_REVERSAL",
            entry_score=0.78,
            exit_reason=ExitReason.TAKE_PROFIT,
            status=TradeStatus.CLOSED
        )
    ]
    
    pattern_analysis = [
        PatternPerformance(
            pattern_type="V_SHAPE_REVERSAL",
            count=25,
            win_rate=0.64,
            avg_profit=Decimal("45.00"),
            total_profit=Decimal("1125.00"),
            avg_holding_time=42.0,
            best_trade=Decimal("200.00"),
            worst_trade=Decimal("-150.00")
        ),
        PatternPerformance(
            pattern_type="EMA_SQUEEZE",
            count=25,
            win_rate=0.56,
            avg_profit=Decimal("-5.00"),
            total_profit=Decimal("-125.00"),
            avg_holding_time=48.0,
            best_trade=Decimal("300.00"),
            worst_trade=Decimal("-150.00")
        )
    ]
    
    time_analysis = [
        TimeAnalysis(hour=9, trade_count=10, win_rate=0.7, avg_profit=Decimal("30.00")),
        TimeAnalysis(hour=14, trade_count=15, win_rate=0.6, avg_profit=Decimal("20.00")),
        TimeAnalysis(hour=20, trade_count=8, win_rate=0.5, avg_profit=Decimal("-10.00"))
    ]
    
    equity_curve = [
        EquityPoint(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            equity=Decimal("10000"),
            drawdown=Decimal("0"),
            trade_count=0
        ),
        EquityPoint(
            timestamp=datetime(2024, 1, 31, tzinfo=timezone.utc),
            equity=Decimal("10500"),
            drawdown=Decimal("100"),
            trade_count=20
        ),
        EquityPoint(
            timestamp=datetime(2024, 3, 31, tzinfo=timezone.utc),
            equity=Decimal("11000"),
            drawdown=Decimal("0"),
            trade_count=50
        )
    ]
    
    monthly_returns = {
        "2024-01": Decimal("5.0"),
        "2024-02": Decimal("2.5"),
        "2024-03": Decimal("2.5")
    }
    
    summary = {
        "total_days": 90,
        "trading_days": 65,
        "avg_trades_per_day": 0.77,
        "final_equity": 11000.0,
        "total_return": 10.0,
        "best_month": "2024-01",
        "worst_month": "2024-02"
    }
    
    return BacktestResult(
        config=config,
        performance=performance,
        trades=trades,
        pattern_analysis=pattern_analysis,
        time_analysis=time_analysis,
        equity_curve=equity_curve,
        monthly_returns=monthly_returns,
        summary=summary
    )


class TestBacktestReportGenerator:
    """レポート生成のテスト"""
    
    def test_initialization(self):
        """初期化テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = BacktestReportGenerator(output_dir=tmpdir)
            assert Path(tmpdir).exists()
    
    def test_summary_save(self, sample_backtest_result):
        """サマリー保存テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = BacktestReportGenerator(output_dir=tmpdir)
            
            summary_path = Path(tmpdir) / "test_summary.json"
            generator._save_summary(sample_backtest_result, summary_path)
            
            assert summary_path.exists()
            
            with open(summary_path, "r") as f:
                data = json.load(f)
                assert "config" in data
                assert "performance" in data
                assert data["performance"]["total_trades"] == 50
                assert data["performance"]["win_rate"] == 0.6
    
    def test_performance_metrics_save(self, sample_backtest_result):
        """パフォーマンスメトリクス保存テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = BacktestReportGenerator(output_dir=tmpdir)
            
            metrics_path = Path(tmpdir) / "test_metrics.csv"
            generator._save_performance_metrics(sample_backtest_result, metrics_path)
            
            assert metrics_path.exists()
            
            df = pd.read_csv(metrics_path, encoding="utf-8-sig", index_col=0)
            assert "総取引数" in df.index
            assert df.loc["総取引数", "値"] == "50"
            assert "勝率" in df.index
            assert "60.00%" in str(df.loc["勝率", "値"])
    
    def test_trades_save(self, sample_backtest_result):
        """取引履歴保存テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = BacktestReportGenerator(output_dir=tmpdir)
            
            trades_path = Path(tmpdir) / "test_trades.csv"
            generator._save_trades(sample_backtest_result, trades_path)
            
            assert trades_path.exists()
            
            df = pd.read_csv(trades_path, encoding="utf-8-sig")
            assert len(df) == 1
            assert df.iloc[0]["ID"] == "bt_001"
            assert df.iloc[0]["方向"] == "long"
            assert df.iloc[0]["損益"] == 62.0
    
    def test_pattern_analysis_save(self, sample_backtest_result):
        """パターン分析保存テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = BacktestReportGenerator(output_dir=tmpdir)
            
            pattern_path = Path(tmpdir) / "test_patterns.csv"
            generator._save_pattern_analysis(sample_backtest_result, pattern_path)
            
            assert pattern_path.exists()
            
            df = pd.read_csv(pattern_path, encoding="utf-8-sig")
            assert len(df) == 2
            assert df.iloc[0]["パターン"] == "V_SHAPE_REVERSAL"
            assert df.iloc[0]["取引数"] == 25
            assert "64.00%" in str(df.iloc[0]["勝率"])
    
    def test_time_analysis_save(self, sample_backtest_result):
        """時間分析保存テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = BacktestReportGenerator(output_dir=tmpdir)
            
            time_path = Path(tmpdir) / "test_time.csv"
            generator._save_time_analysis(sample_backtest_result, time_path)
            
            assert time_path.exists()
            
            df = pd.read_csv(time_path, encoding="utf-8-sig")
            assert len(df) == 3
            assert df.iloc[0]["時間"] == "09:00"
            assert df.iloc[0]["取引数"] == 10
    
    def test_generate_full_report(self, sample_backtest_result):
        """完全レポート生成テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = BacktestReportGenerator(output_dir=tmpdir)
            
            generated_files = generator.generate_report(
                sample_backtest_result,
                report_name="test_report",
                include_trades=True,
                include_charts=False  # チャート生成はスキップ（matplotlib依存）
            )
            
            assert "summary" in generated_files
            assert "metrics" in generated_files
            assert "trades" in generated_files
            assert "pattern_analysis" in generated_files
            assert "time_analysis" in generated_files
            assert "html_report" in generated_files
            
            # ファイル存在確認
            for file_path in generated_files.values():
                assert Path(file_path).exists()
    
    def test_optimization_report(self):
        """最適化レポート生成テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = BacktestReportGenerator(output_dir=tmpdir)
            
            # ダミー最適化結果
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
            
            opt_result = OptimizationResult(
                best_parameters={"min_confidence": 70, "min_rr_ratio": 1.5},
                best_performance=performance,
                all_results=[
                    {
                        "parameters": {"min_confidence": 70, "min_rr_ratio": 1.5},
                        "performance": performance,
                        "metric_value": 1.85
                    },
                    {
                        "parameters": {"min_confidence": 75, "min_rr_ratio": 2.0},
                        "performance": performance,
                        "metric_value": 1.70
                    }
                ],
                optimization_time=3600.0
            )
            
            generated_files = generator.generate_optimization_report(
                opt_result,
                report_name="test_optimization"
            )
            
            assert "summary" in generated_files
            assert "top10" in generated_files
            
            # サマリー確認
            with open(generated_files["summary"], "r") as f:
                data = json.load(f)
                assert data["best_parameters"]["min_confidence"] == 70
                assert data["optimization_time"] == 3600.0
                assert data["total_combinations"] == 2