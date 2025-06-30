"""パフォーマンス分析のテスト"""
import pytest
import time
import asyncio
from datetime import datetime, timezone

from src.services.performance import PerformanceAnalyzer
from src.domain.models.performance import (
    PerformanceStatus, ImpactLevel, BottleneckType
)


class TestPerformanceAnalyzer:
    """パフォーマンス分析のテスト"""
    
    def test_initialization(self):
        """初期化テスト"""
        analyzer = PerformanceAnalyzer(target_time_ms=500.0)
        
        assert analyzer.target_time_ms == 500.0
        assert len(analyzer.metrics) == 0
        assert len(analyzer.db_queries) == 0
        assert len(analyzer.resource_snapshots) == 0
    
    def test_measure_context_manager(self):
        """計測コンテキストマネージャーのテスト"""
        analyzer = PerformanceAnalyzer()
        
        # 計測実行
        with analyzer.measure("test_module") as ctx:
            time.sleep(0.1)  # 100ms
            assert ctx["module"] == "test_module"
            assert "thread_id" in ctx
        
        # 結果確認
        assert "test_module" in analyzer.metrics
        assert len(analyzer.metrics["test_module"]) == 1
        
        measurement = analyzer.metrics["test_module"][0]
        assert measurement["time"] >= 100.0  # 最低100ms
        assert "memory_delta" in measurement
        assert "cpu_usage" in measurement
    
    def test_multiple_measurements(self):
        """複数回計測のテスト"""
        analyzer = PerformanceAnalyzer()
        
        # 同じモジュールを複数回計測
        for i in range(3):
            with analyzer.measure("repeated_module"):
                time.sleep(0.05)
        
        assert len(analyzer.metrics["repeated_module"]) == 3
        
        # 異なるモジュール
        with analyzer.measure("other_module"):
            time.sleep(0.05)
        
        assert len(analyzer.metrics["other_module"]) == 1
    
    def test_record_db_query(self):
        """DBクエリ記録のテスト"""
        analyzer = PerformanceAnalyzer()
        
        # クエリ記録
        analyzer.record_db_query(
            "SELECT * FROM users WHERE id = ?",
            45.6,
            rows_affected=1
        )
        
        assert len(analyzer.db_queries) == 1
        query = analyzer.db_queries[0]
        assert query["query"] == "SELECT * FROM users WHERE id = ?"
        assert query["time"] == 45.6
        assert query["rows_affected"] == 1
        assert isinstance(query["timestamp"], datetime)
    
    def test_capture_resource_snapshot(self):
        """リソーススナップショットのテスト"""
        analyzer = PerformanceAnalyzer()
        
        snapshot = analyzer.capture_resource_snapshot()
        
        assert snapshot.cpu_percent >= 0
        assert snapshot.memory_mb > 0
        assert snapshot.thread_count > 0
        assert isinstance(snapshot.timestamp, datetime)
        
        assert len(analyzer.resource_snapshots) == 1
    
    def test_analyze_performance_status(self):
        """パフォーマンスステータス判定のテスト"""
        # PASS判定
        analyzer = PerformanceAnalyzer(target_time_ms=1000.0)
        with analyzer.measure("fast_module"):
            time.sleep(0.5)  # 500ms
        
        result = analyzer.analyze()
        assert result.summary.performance_status == PerformanceStatus.PASS
        assert result.summary.total_execution_time < 1000.0
        
        # WARNING判定
        analyzer = PerformanceAnalyzer(target_time_ms=500.0)
        with analyzer.measure("medium_module"):
            time.sleep(0.55)  # 550ms
        
        result = analyzer.analyze()
        assert result.summary.performance_status == PerformanceStatus.WARNING
        
        # FAIL判定
        analyzer = PerformanceAnalyzer(target_time_ms=300.0)
        with analyzer.measure("slow_module"):
            time.sleep(0.5)  # 500ms
        
        result = analyzer.analyze()
        assert result.summary.performance_status == PerformanceStatus.FAIL
    
    def test_module_breakdown_analysis(self):
        """モジュール別分析のテスト"""
        analyzer = PerformanceAnalyzer()
        
        # 複数モジュールの計測
        with analyzer.measure("module_a"):
            time.sleep(0.1)
        
        with analyzer.measure("module_b"):
            time.sleep(0.2)
        
        with analyzer.measure("module_a"):
            time.sleep(0.05)
        
        result = analyzer.analyze()
        
        # モジュール分析確認
        assert len(result.module_breakdown) == 2
        
        # 実行時間順にソートされているか確認
        assert result.module_breakdown[0].name == "module_b"
        assert result.module_breakdown[1].name == "module_a"
        
        # module_aの統計確認
        module_a = next(m for m in result.module_breakdown if m.name == "module_a")
        assert module_a.calls == 2
        assert module_a.total_time >= 150.0  # 100ms + 50ms
        assert module_a.avg_time >= 75.0
    
    def test_bottleneck_detection(self):
        """ボトルネック検出のテスト"""
        analyzer = PerformanceAnalyzer()
        
        # DBボトルネック
        analyzer.record_db_query("SELECT * FROM large_table", 300.0)
        analyzer.record_db_query("SELECT * FROM another_table", 250.0)
        
        # アルゴリズムボトルネック
        with analyzer.measure("heavy_algorithm"):
            time.sleep(0.4)  # 400ms
        
        with analyzer.measure("light_algorithm"):
            time.sleep(0.05)  # 50ms
        
        result = analyzer.analyze()
        
        # ボトルネック確認
        assert len(result.bottlenecks) >= 2
        
        # DBボトルネック
        db_bottleneck = next(
            b for b in result.bottlenecks 
            if b.type == BottleneckType.DATABASE
        )
        assert db_bottleneck.time_cost == 550.0  # 300 + 250
        assert db_bottleneck.impact in [ImpactLevel.HIGH, ImpactLevel.MEDIUM]
        
        # アルゴリズムボトルネック
        algo_bottleneck = next(
            b for b in result.bottlenecks
            if b.type == BottleneckType.ALGORITHM
        )
        assert "heavy_algorithm" in algo_bottleneck.affected_modules
    
    def test_optimization_recommendations(self):
        """最適化推奨事項生成のテスト"""
        analyzer = PerformanceAnalyzer()
        
        # ボトルネック作成
        analyzer.record_db_query("SLOW QUERY", 500.0)
        
        with analyzer.measure("slow_module"):
            time.sleep(0.3)
        
        result = analyzer.analyze()
        
        # 推奨事項確認
        assert len(result.optimization_recommendations) > 0
        
        # DB最適化推奨
        db_recommendation = next(
            r for r in result.optimization_recommendations
            if "データベース" in r.action
        )
        assert db_recommendation.priority == 1
        assert db_recommendation.effort in ["low", "medium", "high"]
        assert len(db_recommendation.risks) > 0
    
    def test_percentile_calculation(self):
        """パーセンタイル計算のテスト"""
        analyzer = PerformanceAnalyzer()
        
        # 様々な実行時間で計測
        times = [0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.2]
        for t in times:
            with analyzer.measure("test"):
                time.sleep(t)
        
        result = analyzer.analyze()
        
        # パーセンタイル確認
        assert result.summary.latency_p50 > 0
        assert result.summary.latency_p95 > result.summary.latency_p50
        assert result.summary.latency_p99 >= result.summary.latency_p95
    
    def test_throughput_calculation(self):
        """スループット計算のテスト"""
        analyzer = PerformanceAnalyzer()
        
        # 高速な処理を複数回実行
        for _ in range(10):
            with analyzer.measure("fast_operation"):
                time.sleep(0.01)  # 10ms
        
        result = analyzer.analyze()
        
        # スループット確認（約100 req/s）
        assert result.summary.throughput > 50  # 実行時間のばらつきを考慮
    
    def test_reset(self):
        """リセット機能のテスト"""
        analyzer = PerformanceAnalyzer()
        
        # データ追加
        with analyzer.measure("test"):
            pass
        analyzer.record_db_query("SELECT 1", 1.0)
        analyzer.capture_resource_snapshot()
        
        # リセット前の確認
        assert len(analyzer.metrics) > 0
        assert len(analyzer.db_queries) > 0
        assert len(analyzer.resource_snapshots) > 0
        
        # リセット
        analyzer.reset()
        
        # リセット後の確認
        assert len(analyzer.metrics) == 0
        assert len(analyzer.db_queries) == 0
        assert len(analyzer.resource_snapshots) == 0
    
    @pytest.mark.asyncio
    async def test_async_measurement(self):
        """非同期関数の計測テスト"""
        analyzer = PerformanceAnalyzer()
        
        async def async_operation():
            await asyncio.sleep(0.1)
        
        # 非同期関数の計測
        with analyzer.measure("async_operation"):
            await async_operation()
        
        assert "async_operation" in analyzer.metrics
        measurement = analyzer.metrics["async_operation"][0]
        assert measurement["time"] >= 100.0