"""パフォーマンス分析統合テスト"""
import pytest
import asyncio
import tempfile
from pathlib import Path

from src.services.performance import (
    PerformanceAnalyzer,
    LoadTester,
    ProfilerReportGenerator
)
from src.domain.models.performance import PerformanceStatus


class TestPerformanceIntegration:
    """パフォーマンス分析統合テスト"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_performance_analysis_workflow(self):
        """完全なパフォーマンス分析ワークフロー"""
        # 1. パフォーマンス分析器の準備
        analyzer = PerformanceAnalyzer(target_time_ms=500.0)
        
        # 2. 複雑な処理のシミュレーション
        async def complex_operation():
            # パターン検出シミュレーション
            with analyzer.measure("pattern_detection"):
                await asyncio.sleep(0.15)  # 150ms
                
                # サブモジュール
                with analyzer.measure("v_shape_detection"):
                    await asyncio.sleep(0.05)
            
            # データベースアクセス
            with analyzer.measure("database_access"):
                await asyncio.sleep(0.1)  # 100ms
                analyzer.record_db_query(
                    "SELECT * FROM candlesticks WHERE symbol = ?",
                    85.5,
                    rows_affected=100
                )
            
            # エントリー評価
            with analyzer.measure("entry_evaluation"):
                await asyncio.sleep(0.08)  # 80ms
            
            # シグナル生成
            with analyzer.measure("signal_generation"):
                await asyncio.sleep(0.06)  # 60ms
        
        # 3. 複数回実行
        for _ in range(3):
            await complex_operation()
            analyzer.capture_resource_snapshot()
        
        # 4. 分析実行
        result = analyzer.analyze()
        
        # 5. 結果検証
        assert result.summary.performance_status in [
            PerformanceStatus.PASS,
            PerformanceStatus.WARNING
        ]
        assert result.summary.total_execution_time > 0
        assert len(result.module_breakdown) >= 4
        assert len(result.bottlenecks) > 0
        assert len(result.optimization_recommendations) > 0
        
        # 6. レポート生成
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ProfilerReportGenerator(output_dir=tmpdir)
            files = generator.generate_performance_report(
                result,
                include_charts=False
            )
            
            # レポートファイル確認
            assert all(Path(f).exists() for f in files.values())
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_load_test_with_analysis(self):
        """負荷テストと分析の統合テスト"""
        # 1. 負荷テスター準備
        load_tester = LoadTester()
        
        # 2. パフォーマンス分析器付きテスト関数
        analyzer = PerformanceAnalyzer()
        
        async def test_function():
            with analyzer.measure("test_operation"):
                # 変動する処理時間
                import random
                delay = random.uniform(0.02, 0.08)
                await asyncio.sleep(delay)
                
                # たまにエラー
                if random.random() < 0.1:
                    raise ValueError("Random error")
        
        # 3. 負荷テスト実行
        result = await load_tester.run_load_test(
            test_name="統合負荷テスト",
            test_function=test_function,
            concurrent_users=5,
            duration_seconds=3.0,
            ramp_up_seconds=1.0
        )
        
        # 4. 結果分析
        analysis = load_tester.analyze_results(result)
        
        # 5. 検証
        assert result.total_requests > 0
        assert result.successful_requests > 0
        assert 0 <= analysis["summary"]["success_rate"] <= 100
        assert result.avg_response_time > 20.0  # 最低20ms
        assert len(result.resource_usage_timeline) > 0
        
        # 6. パフォーマンス分析結果
        perf_result = analyzer.analyze()
        assert len(perf_result.module_breakdown) > 0
        
        # 7. 統合レポート生成
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ProfilerReportGenerator(output_dir=tmpdir)
            
            # 負荷テストレポート
            load_files = generator.generate_load_test_report(
                result,
                analysis
            )
            
            # パフォーマンスレポート
            perf_files = generator.generate_performance_report(
                perf_result,
                include_charts=False
            )
            
            assert len(load_files) > 0
            assert len(perf_files) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bottleneck_detection_and_optimization(self):
        """ボトルネック検出と最適化シミュレーション"""
        # 1. 初回分析（ボトルネックあり）
        analyzer = PerformanceAnalyzer(target_time_ms=300.0)
        
        # ボトルネックのある処理
        async def bottlenecked_operation():
            # DBボトルネック
            with analyzer.measure("database_heavy"):
                await asyncio.sleep(0.2)  # 200ms
                for i in range(5):
                    analyzer.record_db_query(
                        f"SELECT * FROM table_{i}",
                        40.0
                    )
            
            # 軽い処理
            with analyzer.measure("light_processing"):
                await asyncio.sleep(0.01)
        
        # 実行
        await bottlenecked_operation()
        initial_result = analyzer.analyze()
        
        # ボトルネック確認
        assert initial_result.summary.performance_status == PerformanceStatus.FAIL
        assert len(initial_result.bottlenecks) > 0
        
        db_bottleneck = next(
            b for b in initial_result.bottlenecks
            if b.type.value == "database"
        )
        assert db_bottleneck is not None
        
        # 2. 最適化後の分析（改善版）
        analyzer.reset()
        
        # 最適化された処理
        async def optimized_operation():
            # キャッシュを使用（DBアクセス削減）
            with analyzer.measure("database_cached"):
                await asyncio.sleep(0.05)  # 50ms（キャッシュヒット）
                analyzer.record_db_query(
                    "SELECT * FROM cache",
                    5.0
                )
            
            with analyzer.measure("light_processing"):
                await asyncio.sleep(0.01)
        
        # 実行
        await optimized_operation()
        optimized_result = analyzer.analyze()
        
        # 改善確認
        assert optimized_result.summary.performance_status == PerformanceStatus.PASS
        assert (
            optimized_result.summary.total_execution_time <
            initial_result.summary.total_execution_time * 0.5
        )
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_memory_leak_detection_workflow(self):
        """メモリリーク検出ワークフロー"""
        load_tester = LoadTester()
        
        # メモリリークをシミュレート
        leaked_data = []
        
        async def leaky_function():
            # メモリを徐々に消費
            leaked_data.append([0] * 10000)  # 約80KB
            await asyncio.sleep(0.01)
        
        # 負荷テスト実行
        result = await load_tester.run_load_test(
            test_name="メモリリークテスト",
            test_function=leaky_function,
            concurrent_users=2,
            duration_seconds=2.0,
            ramp_up_seconds=0.0
        )
        
        # メモリ使用量の増加確認
        if len(result.resource_usage_timeline) > 2:
            initial_memory = result.resource_usage_timeline[0].memory_mb
            final_memory = result.resource_usage_timeline[-1].memory_mb
            memory_increase = final_memory - initial_memory
            
            # メモリが増加していることを確認
            assert memory_increase > 0
        
        # クリーンアップ
        leaked_data.clear()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_analysis(self):
        """並行処理のパフォーマンス分析"""
        analyzer = PerformanceAnalyzer()
        
        # 並行処理タスク
        async def concurrent_task(task_id: int):
            with analyzer.measure(f"task_{task_id}"):
                await asyncio.sleep(0.05)
        
        # 並行実行
        with analyzer.measure("concurrent_execution"):
            tasks = [
                concurrent_task(i)
                for i in range(5)
            ]
            await asyncio.gather(*tasks)
        
        # 分析
        result = analyzer.analyze()
        
        # 並行処理の効果確認
        concurrent_module = next(
            m for m in result.module_breakdown
            if m.name == "concurrent_execution"
        )
        
        # 並行実行時間は個別タスクの合計より短いはず
        individual_sum = sum(
            m.total_time for m in result.module_breakdown
            if m.name.startswith("task_")
        )
        
        assert concurrent_module.total_time < individual_sum