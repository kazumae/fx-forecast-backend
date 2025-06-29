"""バックテスト最適化"""
import asyncio
import itertools
import time
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ProcessPoolExecutor
import pandas as pd

from src.domain.models.backtest import (
    BacktestConfig, BacktestResult, OptimizationResult,
    PerformanceMetrics
)
from src.services.backtest.backtest_engine import BacktestEngine


class ParameterOptimizer:
    """パラメータ最適化"""
    
    def __init__(
        self,
        base_config: BacktestConfig,
        parameter_ranges: Dict[str, List[Any]],
        optimization_metric: str = "sharpe_ratio",
        n_jobs: int = -1
    ):
        """
        Args:
            base_config: ベースとなるバックテスト設定
            parameter_ranges: 最適化するパラメータと値の範囲
                例: {
                    "min_confidence": [60, 65, 70, 75, 80],
                    "min_rr_ratio": [1.0, 1.5, 2.0, 2.5],
                    "max_risk_pips": [30, 40, 50, 60]
                }
            optimization_metric: 最適化の評価指標
            n_jobs: 並列実行数（-1で全CPU使用）
        """
        self.base_config = base_config
        self.parameter_ranges = parameter_ranges
        self.optimization_metric = optimization_metric
        self.n_jobs = n_jobs if n_jobs > 0 else None
        
    async def optimize(
        self,
        data: pd.DataFrame,
        zones: List[Any],
        market_context: Optional[Dict[str, Any]] = None,
        validation_split: float = 0.2
    ) -> OptimizationResult:
        """パラメータ最適化を実行"""
        start_time = time.time()
        
        # データ分割（ウォークフォワード分析用）
        split_index = int(len(data) * (1 - validation_split))
        train_data = data.iloc[:split_index]
        validation_data = data.iloc[split_index:] if validation_split > 0 else None
        
        # パラメータ組み合わせ生成
        param_combinations = self._generate_parameter_combinations()
        total_combinations = len(param_combinations)
        
        print(f"最適化開始: {total_combinations}個の組み合わせをテスト")
        
        # グリッドサーチ実行
        all_results = []
        best_result = None
        best_metric = float('-inf')
        
        # バッチ処理
        batch_size = 10
        for i in range(0, total_combinations, batch_size):
            batch = param_combinations[i:i+batch_size]
            batch_results = await self._run_batch(
                batch,
                train_data,
                zones,
                market_context
            )
            
            # 結果評価
            for params, result in batch_results:
                metric_value = self._get_metric_value(result.performance)
                all_results.append({
                    "parameters": params,
                    "performance": result.performance,
                    "metric_value": metric_value
                })
                
                if metric_value > best_metric:
                    best_metric = metric_value
                    best_result = result
                    best_parameters = params
            
            # 進捗表示
            progress = min(i + batch_size, total_combinations)
            print(f"進捗: {progress}/{total_combinations} ({progress/total_combinations*100:.1f}%)")
        
        # 検証データでの確認
        if validation_data is not None and best_parameters:
            print("検証データでのバックテスト実行中...")
            validation_result = await self._run_single_backtest(
                best_parameters,
                validation_data,
                zones,
                market_context
            )
            validation_metric = self._get_metric_value(validation_result.performance)
            print(f"検証データでの{self.optimization_metric}: {validation_metric:.3f}")
        
        # 最適化時間
        optimization_time = time.time() - start_time
        
        return OptimizationResult(
            best_parameters=best_parameters,
            best_performance=best_result.performance,
            all_results=sorted(all_results, key=lambda x: x["metric_value"], reverse=True),
            optimization_time=optimization_time
        )
    
    def _generate_parameter_combinations(self) -> List[Dict[str, Any]]:
        """パラメータの組み合わせを生成"""
        param_names = list(self.parameter_ranges.keys())
        param_values = [self.parameter_ranges[name] for name in param_names]
        
        combinations = []
        for values in itertools.product(*param_values):
            param_dict = dict(zip(param_names, values))
            combinations.append(param_dict)
        
        return combinations
    
    async def _run_batch(
        self,
        param_batch: List[Dict[str, Any]],
        data: pd.DataFrame,
        zones: List[Any],
        market_context: Optional[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], BacktestResult]]:
        """バッチ実行"""
        tasks = []
        for params in param_batch:
            task = self._run_single_backtest(params, data, zones, market_context)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return list(zip(param_batch, results))
    
    async def _run_single_backtest(
        self,
        parameters: Dict[str, Any],
        data: pd.DataFrame,
        zones: List[Any],
        market_context: Optional[Dict[str, Any]]
    ) -> BacktestResult:
        """単一のバックテストを実行"""
        # 設定作成
        config = BacktestConfig(
            symbol=self.base_config.symbol,
            start_date=self.base_config.start_date,
            end_date=self.base_config.end_date,
            initial_capital=self.base_config.initial_capital,
            position_size=self.base_config.position_size,
            commission=self.base_config.commission,
            slippage=self.base_config.slippage,
            max_positions=self.base_config.max_positions,
            use_fixed_size=self.base_config.use_fixed_size,
            risk_per_trade=self.base_config.risk_per_trade,
            parameters=parameters
        )
        
        # コンテキスト更新
        if market_context:
            updated_context = market_context.copy()
            updated_context.update(parameters)
        else:
            updated_context = parameters
        
        # バックテスト実行
        engine = BacktestEngine(config)
        result = await engine.run(data, zones, updated_context)
        
        return result
    
    def _get_metric_value(self, performance: PerformanceMetrics) -> float:
        """評価指標の値を取得"""
        metric_map = {
            "sharpe_ratio": performance.sharpe_ratio,
            "profit_factor": performance.profit_factor,
            "win_rate": performance.win_rate,
            "net_profit": float(performance.net_profit),
            "max_drawdown": -float(performance.max_drawdown_percent),
            "avg_rr_realized": performance.avg_rr_realized,
            "calmar_ratio": performance.calmar_ratio,
            "sortino_ratio": performance.sortino_ratio
        }
        
        value = metric_map.get(self.optimization_metric, 0)
        
        # 最小取引数フィルター
        if performance.total_trades < 30:
            value *= 0.5  # ペナルティ
        
        return value


class WalkForwardAnalyzer:
    """ウォークフォワード分析"""
    
    def __init__(
        self,
        optimizer: ParameterOptimizer,
        window_size: int = 252,  # 取引日数
        step_size: int = 63,     # 3ヶ月
        optimization_period: int = 189  # 9ヶ月
    ):
        self.optimizer = optimizer
        self.window_size = window_size
        self.step_size = step_size
        self.optimization_period = optimization_period
        
    async def analyze(
        self,
        data: pd.DataFrame,
        zones: List[Any],
        market_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """ウォークフォワード分析を実行"""
        results = []
        data_length = len(data)
        
        # ウィンドウをスライド
        start_idx = 0
        while start_idx + self.window_size <= data_length:
            # 最適化期間
            opt_end_idx = start_idx + self.optimization_period
            opt_data = data.iloc[start_idx:opt_end_idx]
            
            # 検証期間
            val_start_idx = opt_end_idx
            val_end_idx = start_idx + self.window_size
            val_data = data.iloc[val_start_idx:val_end_idx]
            
            if len(val_data) < 20:  # 最小検証期間
                break
            
            print(f"\nウィンドウ {len(results)+1}:")
            print(f"最適化期間: {opt_data.index[0]} - {opt_data.index[-1]}")
            print(f"検証期間: {val_data.index[0]} - {val_data.index[-1]}")
            
            # 最適化実行
            opt_result = await self.optimizer.optimize(
                opt_data,
                zones,
                market_context,
                validation_split=0  # ウォークフォワードでは使用しない
            )
            
            # 検証期間でのバックテスト
            val_result = await self.optimizer._run_single_backtest(
                opt_result.best_parameters,
                val_data,
                zones,
                market_context
            )
            
            results.append({
                "window": len(results) + 1,
                "optimization_period": {
                    "start": opt_data.index[0],
                    "end": opt_data.index[-1]
                },
                "validation_period": {
                    "start": val_data.index[0],
                    "end": val_data.index[-1]
                },
                "best_parameters": opt_result.best_parameters,
                "optimization_performance": opt_result.best_performance,
                "validation_performance": val_result.performance
            })
            
            # 次のウィンドウへ
            start_idx += self.step_size
        
        # 結果集計
        summary = self._summarize_results(results)
        
        return {
            "windows": results,
            "summary": summary
        }
    
    def _summarize_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """結果を集計"""
        if not results:
            return {}
        
        # 検証期間のパフォーマンス集計
        val_performances = [r["validation_performance"] for r in results]
        
        avg_sharpe = sum(p.sharpe_ratio for p in val_performances) / len(val_performances)
        avg_win_rate = sum(p.win_rate for p in val_performances) / len(val_performances)
        total_trades = sum(p.total_trades for p in val_performances)
        
        # パラメータの安定性分析
        param_stability = {}
        all_params = [r["best_parameters"] for r in results]
        
        if all_params:
            for key in all_params[0].keys():
                values = [p[key] for p in all_params]
                unique_values = len(set(values))
                param_stability[key] = {
                    "unique_values": unique_values,
                    "stability_score": 1 - (unique_values - 1) / len(values)
                }
        
        return {
            "avg_validation_sharpe": avg_sharpe,
            "avg_validation_win_rate": avg_win_rate,
            "total_validation_trades": total_trades,
            "parameter_stability": param_stability,
            "consistent_parameters": {
                k: v for k, v in param_stability.items()
                if v["stability_score"] > 0.7
            }
        }