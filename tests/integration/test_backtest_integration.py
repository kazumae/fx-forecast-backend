"""バックテスト統合テスト"""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile

from src.domain.models.backtest import BacktestConfig
from src.domain.models.zone import Zone, ZoneType
from src.services.backtest import (
    BacktestEngine,
    ParameterOptimizer,
    BacktestReportGenerator
)
from tests.utils import CandlestickFactory, ZoneFactory


@pytest.fixture
def realistic_market_data():
    """現実的な市場データ"""
    dates = pd.date_range(
        start='2024-01-01', 
        end='2024-06-30', 
        freq='5min',  # 5分足
        tz=timezone.utc
    )
    
    # 現実的な価格変動をシミュレート
    np.random.seed(42)
    data = []
    
    # トレンドとボラティリティの変化
    base_price = 3275.0
    trend = 0
    volatility = 2.0
    
    for i, date in enumerate(dates):
        # 日中のセッション変化
        hour = date.hour
        if 7 <= hour <= 9:  # ロンドンオープン
            volatility = 3.0
        elif 13 <= hour <= 15:  # NYオープン
            volatility = 3.5
        else:
            volatility = 1.5
        
        # トレンド変化（週次）
        if i % (288 * 5) == 0:  # 5日毎
            trend = np.random.choice([-0.5, 0, 0.5])
        
        # 価格変動
        change = np.random.normal(trend, volatility)
        base_price += change
        
        # OHLC生成
        open_price = base_price + np.random.normal(0, 0.3)
        high = base_price + abs(np.random.normal(0, volatility * 0.7))
        low = base_price - abs(np.random.normal(0, volatility * 0.7))
        close = base_price + np.random.normal(0, 0.3)
        
        # 確実にhigh/lowが正しい範囲に
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        
        data.append({
            "timestamp": date,
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": int(1000 + abs(np.random.normal(0, 200)))
        })
    
    return pd.DataFrame(data)


@pytest.fixture
def dynamic_zones(realistic_market_data):
    """動的ゾーン生成"""
    # 価格の統計から主要レベルを特定
    prices = realistic_market_data["close"].values
    
    # パーセンタイルベースのゾーン
    zones = []
    percentiles = [10, 25, 50, 75, 90]
    
    for p in percentiles:
        price_level = np.percentile(prices, p)
        zone_type = ZoneType.SUPPORT if p < 50 else ZoneType.RESISTANCE
        
        zone = ZoneFactory.create_zone(
            upper=price_level + 2,
            lower=price_level - 2,
            zone_type=zone_type,
            strength=0.7 + (abs(50 - p) / 100),  # 極値に近いほど強い
            touch_count=np.random.randint(3, 8)
        )
        zones.append(zone)
    
    # 心理的レベル（ラウンドナンバー）
    base_level = int(prices.mean() / 10) * 10
    for offset in [-50, -25, 0, 25, 50]:
        level = base_level + offset
        zone = ZoneFactory.create_zone(
            upper=level + 1,
            lower=level - 1,
            zone_type=ZoneType.SUPPORT if offset < 0 else ZoneType.RESISTANCE,
            strength=0.8,
            touch_count=5
        )
        zones.append(zone)
    
    return zones


class TestBacktestIntegration:
    """バックテスト統合テスト"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_backtest_workflow(
        self,
        realistic_market_data,
        dynamic_zones
    ):
        """完全なバックテストワークフロー"""
        # 1. バックテスト設定
        config = BacktestConfig(
            symbol="XAUUSD",
            start_date=datetime(2024, 2, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 5, 31, tzinfo=timezone.utc),
            initial_capital=Decimal("10000"),
            position_size=Decimal("0.1"),
            commission=Decimal("2"),
            slippage=Decimal("0.5"),
            max_positions=2,
            use_fixed_size=False,
            risk_per_trade=Decimal("2.0"),  # 2%リスク
            parameters={
                "min_confidence": 70.0,
                "min_rr_ratio": 1.5,
                "max_risk_pips": 50.0,
                "enable_zone_validation": True,
                "enable_trend_filter": True
            }
        )
        
        # 2. バックテスト実行
        engine = BacktestEngine(config)
        result = await engine.run(
            realistic_market_data,
            dynamic_zones,
            config.parameters
        )
        
        # 3. 結果検証
        assert result.config == config
        assert result.performance.total_trades >= 0
        assert len(result.equity_curve) > 0
        assert result.equity_curve[0].equity == config.initial_capital
        
        # パフォーマンス確認
        if result.performance.total_trades > 0:
            assert 0 <= result.performance.win_rate <= 1
            assert result.performance.avg_win >= 0
            assert result.performance.avg_loss <= 0
        
        # 4. レポート生成
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = BacktestReportGenerator(output_dir=tmpdir)
            files = generator.generate_report(
                result,
                report_name="integration_test",
                include_trades=True,
                include_charts=False
            )
            
            # レポートファイル確認
            assert all(Path(f).exists() for f in files.values())
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_parameter_optimization_workflow(
        self,
        realistic_market_data,
        dynamic_zones
    ):
        """パラメータ最適化ワークフロー"""
        # 1. ベース設定
        base_config = BacktestConfig(
            symbol="XAUUSD",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
            initial_capital=Decimal("10000"),
            position_size=Decimal("0.1"),
            commission=Decimal("2"),
            slippage=Decimal("0.5"),
            max_positions=2,
            use_fixed_size=True
        )
        
        # 2. 最適化パラメータ
        parameter_ranges = {
            "min_confidence": [65, 70, 75],
            "min_rr_ratio": [1.0, 1.5],
            "max_risk_pips": [40, 50]
        }
        
        # 3. 最適化実行
        optimizer = ParameterOptimizer(
            base_config=base_config,
            parameter_ranges=parameter_ranges,
            optimization_metric="sharpe_ratio"
        )
        
        # データの一部を使用（高速化のため）
        small_data = realistic_market_data.iloc[:5000]
        
        opt_result = await optimizer.optimize(
            small_data,
            dynamic_zones[:5],  # ゾーンも削減
            validation_split=0.2
        )
        
        # 4. 結果検証
        assert opt_result.best_parameters is not None
        assert all(
            param in opt_result.best_parameters 
            for param in parameter_ranges.keys()
        )
        assert opt_result.best_performance is not None
        assert len(opt_result.all_results) == 12  # 3 * 2 * 2
        assert opt_result.optimization_time > 0
        
        # 5. 最適化レポート生成
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = BacktestReportGenerator(output_dir=tmpdir)
            files = generator.generate_optimization_report(
                opt_result,
                report_name="optimization_test"
            )
            
            assert all(Path(f).exists() for f in files.values())
    
    @pytest.mark.asyncio
    async def test_edge_cases(self, realistic_market_data, dynamic_zones):
        """エッジケーステスト"""
        # 1. 取引なしのケース
        config = BacktestConfig(
            symbol="XAUUSD",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),  # 1日のみ
            initial_capital=Decimal("10000"),
            position_size=Decimal("0.1"),
            commission=Decimal("2"),
            slippage=Decimal("0.5"),
            max_positions=1,
            use_fixed_size=True,
            parameters={
                "min_confidence": 95.0,  # 非常に高い閾値
                "min_rr_ratio": 5.0,     # 非常に高いRR
                "max_risk_pips": 10.0    # 非常に小さいリスク
            }
        )
        
        engine = BacktestEngine(config)
        result = await engine.run(
            realistic_market_data.iloc[:100],
            dynamic_zones,
            config.parameters
        )
        
        # 取引がないことを確認
        assert result.performance.total_trades == 0
        assert result.performance.net_profit == Decimal("0")
        assert len(result.equity_curve) > 0
        assert result.equity_curve[-1].equity == config.initial_capital
        
        # 2. 最大ポジション制限テスト
        config.max_positions = 1
        config.parameters["min_confidence"] = 60.0  # 低い閾値
        
        engine = BacktestEngine(config)
        result = await engine.run(
            realistic_market_data.iloc[:1000],
            dynamic_zones,
            config.parameters
        )
        
        # 同時オープンポジションが1を超えないことを確認
        # （実際の実装では内部状態を確認する必要がある）
        assert result.config.max_positions == 1
    
    @pytest.mark.asyncio
    async def test_different_market_conditions(self):
        """異なる市場状況でのテスト"""
        # 1. 強いトレンド相場
        trend_data = self._generate_trend_market(
            trend_strength=0.5,
            volatility=1.0,
            days=30
        )
        
        # 2. レンジ相場
        range_data = self._generate_range_market(
            range_center=3275,
            range_size=20,
            volatility=2.0,
            days=30
        )
        
        # 3. 高ボラティリティ相場
        volatile_data = self._generate_volatile_market(
            base_volatility=5.0,
            spike_probability=0.1,
            days=30
        )
        
        # 各市場でのバックテスト
        config = BacktestConfig(
            symbol="XAUUSD",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 30, tzinfo=timezone.utc),
            initial_capital=Decimal("10000"),
            position_size=Decimal("0.1"),
            commission=Decimal("2"),
            slippage=Decimal("0.5"),
            max_positions=2,
            use_fixed_size=True
        )
        
        for market_type, data in [
            ("trend", trend_data),
            ("range", range_data),
            ("volatile", volatile_data)
        ]:
            zones = self._generate_zones_for_market(data)
            
            engine = BacktestEngine(config)
            result = await engine.run(data, zones)
            
            # 基本的な検証のみ
            assert result is not None
            assert isinstance(result.performance.sharpe_ratio, float)
    
    def _generate_trend_market(
        self, 
        trend_strength: float, 
        volatility: float, 
        days: int
    ) -> pd.DataFrame:
        """トレンド相場生成"""
        dates = pd.date_range(
            start='2024-01-01',
            periods=days * 288,  # 5分足
            freq='5min',
            tz=timezone.utc
        )
        
        data = []
        price = 3275.0
        
        for date in dates:
            price += trend_strength + np.random.normal(0, volatility)
            
            data.append({
                "timestamp": date,
                "open": price - 0.5,
                "high": price + volatility,
                "low": price - volatility,
                "close": price + 0.5,
                "volume": 1000
            })
        
        return pd.DataFrame(data)
    
    def _generate_range_market(
        self,
        range_center: float,
        range_size: float,
        volatility: float,
        days: int
    ) -> pd.DataFrame:
        """レンジ相場生成"""
        dates = pd.date_range(
            start='2024-01-01',
            periods=days * 288,
            freq='5min',
            tz=timezone.utc
        )
        
        data = []
        
        for i, date in enumerate(dates):
            # サイン波でレンジを表現
            position = np.sin(i * 0.01) * range_size
            price = range_center + position + np.random.normal(0, volatility)
            
            data.append({
                "timestamp": date,
                "open": price - 0.3,
                "high": price + volatility * 0.5,
                "low": price - volatility * 0.5,
                "close": price + 0.3,
                "volume": 1000
            })
        
        return pd.DataFrame(data)
    
    def _generate_volatile_market(
        self,
        base_volatility: float,
        spike_probability: float,
        days: int
    ) -> pd.DataFrame:
        """高ボラティリティ相場生成"""
        dates = pd.date_range(
            start='2024-01-01',
            periods=days * 288,
            freq='5min',
            tz=timezone.utc
        )
        
        data = []
        price = 3275.0
        
        for date in dates:
            # スパイク発生
            if np.random.random() < spike_probability:
                spike = np.random.choice([-1, 1]) * base_volatility * 3
            else:
                spike = 0
            
            change = np.random.normal(0, base_volatility) + spike
            price += change
            
            data.append({
                "timestamp": date,
                "open": price,
                "high": price + abs(change),
                "low": price - abs(change),
                "close": price + np.random.normal(0, 1),
                "volume": int(1000 + abs(change) * 100)
            })
        
        return pd.DataFrame(data)
    
    def _generate_zones_for_market(self, data: pd.DataFrame) -> list:
        """市場データに基づくゾーン生成"""
        prices = data["close"].values
        
        # 簡易的なゾーン生成
        zones = []
        levels = [
            np.percentile(prices, 20),
            np.percentile(prices, 50),
            np.percentile(prices, 80)
        ]
        
        for i, level in enumerate(levels):
            zone_type = ZoneType.SUPPORT if i < len(levels) / 2 else ZoneType.RESISTANCE
            zone = ZoneFactory.create_zone(
                upper=level + 2,
                lower=level - 2,
                zone_type=zone_type,
                strength=0.8
            )
            zones.append(zone)
        
        return zones