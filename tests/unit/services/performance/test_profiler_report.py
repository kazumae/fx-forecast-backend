"""プロファイラーレポート生成のテスト"""
import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from src.services.performance import ProfilerReportGenerator
from src.domain.models.performance import (
    PerformanceStatus, ImpactLevel, BottleneckType,
    ModuleMetrics, ResourceUsage, Bottleneck,
    OptimizationRecommendation, PerformanceSummary,
    PerformanceAnalysisResult, LoadTestResult
)


@pytest.fixture
def sample_performance_result():
    """サンプルパフォーマンス分析結果"""
    summary = PerformanceSummary(
        timestamp=datetime.now(timezone.utc),
        total_execution_time=823.5,
        target_time=1000.0,
        performance_status=PerformanceStatus.PASS,
        throughput=15.5,
        latency_p50=45.0,
        latency_p95=120.0,
        latency_p99=180.0,
        error_rate=0.02
    )
    
    module_breakdown = [
        ModuleMetrics(
            name="pattern_detection",
            total_time=245.3,
            calls=4,
            avg_time=61.3,
            max_time=89.2,
            min_time=45.1,
            percentage=29.8,
            memory_delta=12.5
        ),
        ModuleMetrics(
            name="database_access",
            total_time=289.4,
            calls=12,
            avg_time=24.1,
            max_time=45.6,
            min_time=18.2,
            percentage=35.1,
            memory_delta=5.3
        )
    ]
    
    resource_usage = ResourceUsage(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=45.2,
        memory_mb=256.4,
        memory_percent=15.8,
        thread_count=8,
        file_descriptors=42,
        io_read_mb=125.6,
        io_write_mb=89.3,
        network_sent_mb=12.4,
        network_recv_mb=15.8
    )
    
    bottlenecks = [
        Bottleneck(
            type=BottleneckType.DATABASE,
            description="データベースクエリの実行時間が長い",
            impact=ImpactLevel.HIGH,
            time_cost=289.4,
            occurrence_count=12,
            suggestion="インデックスの追加とクエリ最適化",
            affected_modules=["database_access"]
        )
    ]
    
    recommendations = [
        OptimizationRecommendation(
            priority=1,
            action="データベースクエリの最適化",
            expected_improvement="150ms削減",
            effort="medium",
            implementation="複合インデックスの作成",
            risks=["インデックス作成時の一時的なパフォーマンス低下"],
            dependencies=["データベース管理者の協力"],
            estimated_hours=8.0
        )
    ]
    
    return PerformanceAnalysisResult(
        summary=summary,
        module_breakdown=module_breakdown,
        resource_usage=resource_usage,
        database_metrics=None,
        bottlenecks=bottlenecks,
        optimization_recommendations=recommendations
    )


@pytest.fixture
def sample_load_test_result():
    """サンプル負荷テスト結果"""
    return LoadTestResult(
        test_name="エントリーポイント判定負荷テスト",
        duration_seconds=30.0,
        concurrent_users=10,
        total_requests=500,
        successful_requests=480,
        failed_requests=20,
        avg_response_time=65.5,
        max_response_time=250.0,
        requests_per_second=16.7,
        memory_leak_detected=False,
        error_breakdown={"TimeoutError": 15, "ValueError": 5},
        resource_usage_timeline=[
            ResourceUsage(
                timestamp=datetime.now(timezone.utc),
                cpu_percent=35.0,
                memory_mb=180.0,
                memory_percent=12.0,
                thread_count=10,
                file_descriptors=50,
                io_read_mb=0,
                io_write_mb=0,
                network_sent_mb=1.0,
                network_recv_mb=1.2
            )
        ]
    )


class TestProfilerReportGenerator:
    """プロファイラーレポート生成のテスト"""
    
    def test_initialization(self):
        """初期化テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ProfilerReportGenerator(output_dir=tmpdir)
            assert Path(tmpdir).exists()
    
    def test_generate_performance_report(self, sample_performance_result):
        """パフォーマンスレポート生成テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ProfilerReportGenerator(output_dir=tmpdir)
            
            # レポート生成
            files = generator.generate_performance_report(
                sample_performance_result,
                report_name="test_report",
                include_charts=False  # チャート生成をスキップ
            )
            
            # ファイル存在確認
            assert "json_report" in files
            assert "html_report" in files
            assert "recommendations" in files
            
            # JSONレポート確認
            json_path = Path(files["json_report"])
            assert json_path.exists()
            
            with open(json_path, "r") as f:
                data = json.load(f)
                assert data["performance_summary"]["total_execution_time"] == 823.5
                assert data["performance_summary"]["performance_status"] == "PASS"
                assert len(data["module_breakdown"]) == 2
                assert len(data["bottlenecks"]) == 1
    
    def test_generate_load_test_report(self, sample_load_test_result):
        """負荷テストレポート生成テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ProfilerReportGenerator(output_dir=tmpdir)
            
            # 分析結果
            analysis = {
                "summary": {
                    "success_rate": 96.0,
                    "avg_rps": 16.7
                },
                "assessment": "優秀"
            }
            
            # レポート生成
            files = generator.generate_load_test_report(
                sample_load_test_result,
                analysis,
                report_name="load_test_report"
            )
            
            # ファイル存在確認
            assert "summary" in files
            
            # サマリー確認
            summary_path = Path(files["summary"])
            assert summary_path.exists()
            
            with open(summary_path, "r") as f:
                data = json.load(f)
                assert data["test_name"] == "エントリーポイント判定負荷テスト"
                assert data["results"]["total_requests"] == 500
                assert data["results"]["successful_requests"] == 480
                assert data["analysis"]["assessment"] == "優秀"
    
    def test_html_report_generation(self, sample_performance_result):
        """HTMLレポート生成テスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ProfilerReportGenerator(output_dir=tmpdir)
            
            # レポート生成
            files = generator.generate_performance_report(
                sample_performance_result,
                report_name="html_test",
                include_charts=False
            )
            
            # HTML確認
            html_path = Path(files["html_report"])
            assert html_path.exists()
            
            content = html_path.read_text(encoding="utf-8")
            assert "<html" in content
            assert "PASS" in content
            assert "823.5ms" in content
            assert "データベースクエリの実行時間が長い" in content
    
    def test_recommendations_report(self, sample_performance_result):
        """最適化推奨事項レポートテスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ProfilerReportGenerator(output_dir=tmpdir)
            
            # レポート生成
            files = generator.generate_performance_report(
                sample_performance_result,
                report_name="recommendations_test",
                include_charts=False
            )
            
            # 推奨事項確認
            rec_path = Path(files["recommendations"])
            assert rec_path.exists()
            
            content = rec_path.read_text(encoding="utf-8")
            assert "# パフォーマンス最適化推奨事項" in content
            assert "データベースクエリの最適化" in content
            assert "150ms削減" in content
            assert "複合インデックスの作成" in content
    
    def test_performance_result_to_dict(self, sample_performance_result):
        """パフォーマンス結果の辞書変換テスト"""
        result_dict = sample_performance_result.to_dict()
        
        # 構造確認
        assert "performance_summary" in result_dict
        assert "module_breakdown" in result_dict
        assert "resource_usage" in result_dict
        assert "bottlenecks" in result_dict
        assert "optimization_recommendations" in result_dict
        
        # 値確認
        assert result_dict["performance_summary"]["total_execution_time"] == 823.5
        assert len(result_dict["module_breakdown"]) == 2
        assert result_dict["module_breakdown"][0]["module"] == "pattern_detection"
        assert result_dict["bottlenecks"][0]["type"] == "database"
    
    def test_empty_bottlenecks(self):
        """ボトルネックなしの場合のテスト"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ProfilerReportGenerator(output_dir=tmpdir)
            
            # ボトルネックなしの結果
            result = PerformanceAnalysisResult(
                summary=PerformanceSummary(
                    timestamp=datetime.now(timezone.utc),
                    total_execution_time=500.0,
                    target_time=1000.0,
                    performance_status=PerformanceStatus.PASS,
                    throughput=20.0,
                    latency_p50=25.0,
                    latency_p95=45.0,
                    latency_p99=60.0,
                    error_rate=0.0
                ),
                module_breakdown=[],
                resource_usage=ResourceUsage(
                    timestamp=datetime.now(timezone.utc),
                    cpu_percent=25.0,
                    memory_mb=128.0,
                    memory_percent=8.0,
                    thread_count=4,
                    file_descriptors=20,
                    io_read_mb=10.0,
                    io_write_mb=5.0,
                    network_sent_mb=1.0,
                    network_recv_mb=1.0
                ),
                database_metrics=None,
                bottlenecks=[],
                optimization_recommendations=[]
            )
            
            # レポート生成（エラーが発生しないことを確認）
            files = generator.generate_performance_report(
                result,
                report_name="no_bottlenecks",
                include_charts=False
            )
            
            assert len(files) > 0