"""負荷テストツールのテスト"""
import pytest
import asyncio
import time

from src.services.performance import LoadTester
from src.domain.models.performance import LoadTestResult


class TestLoadTester:
    """負荷テストツールのテスト"""
    
    def test_initialization(self):
        """初期化テスト"""
        tester = LoadTester()
        
        assert tester.results == []
        assert tester.resource_timeline == []
        assert tester.process is not None
    
    @pytest.mark.asyncio
    async def test_simple_load_test(self):
        """シンプルな負荷テスト"""
        tester = LoadTester()
        
        # テスト関数
        call_count = 0
        async def test_function():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # 10ms
        
        # 負荷テスト実行
        result = await tester.run_load_test(
            test_name="simple_test",
            test_function=test_function,
            concurrent_users=2,
            duration_seconds=1.0,
            ramp_up_seconds=0.0
        )
        
        # 結果確認
        assert isinstance(result, LoadTestResult)
        assert result.test_name == "simple_test"
        assert result.concurrent_users == 2
        assert result.total_requests > 0
        assert result.successful_requests == result.total_requests
        assert result.failed_requests == 0
        assert result.avg_response_time > 10.0  # 最低10ms
        assert result.requests_per_second > 0
        assert call_count > 0
    
    @pytest.mark.asyncio
    async def test_load_test_with_errors(self):
        """エラーを含む負荷テスト"""
        tester = LoadTester()
        
        # エラーを発生させるテスト関数
        error_count = 0
        async def test_function():
            nonlocal error_count
            error_count += 1
            if error_count % 3 == 0:  # 3回に1回エラー
                raise ValueError("Test error")
            await asyncio.sleep(0.01)
        
        # 負荷テスト実行
        result = await tester.run_load_test(
            test_name="error_test",
            test_function=test_function,
            concurrent_users=1,
            duration_seconds=0.5,
            ramp_up_seconds=0.0
        )
        
        # 結果確認
        assert result.failed_requests > 0
        assert result.successful_requests > 0
        assert "ValueError" in result.error_breakdown
        assert result.error_breakdown["ValueError"] == result.failed_requests
    
    @pytest.mark.asyncio
    async def test_ramp_up(self):
        """ランプアップテスト"""
        tester = LoadTester()
        
        # 同時実行数を記録
        max_concurrent = 0
        current_concurrent = 0
        
        async def test_function():
            nonlocal max_concurrent, current_concurrent
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.05)
            current_concurrent -= 1
        
        # 負荷テスト実行
        result = await tester.run_load_test(
            test_name="ramp_up_test",
            test_function=test_function,
            concurrent_users=5,
            duration_seconds=2.0,
            ramp_up_seconds=1.0
        )
        
        # 結果確認
        assert result.total_requests > 0
        assert max_concurrent <= 5  # 最大同時実行数
    
    @pytest.mark.asyncio
    async def test_memory_leak_detection(self):
        """メモリリーク検出テスト"""
        tester = LoadTester()
        
        # メモリを保持するテスト関数
        data_holder = []
        
        async def test_function():
            # 小さなメモリリークをシミュレート
            data_holder.append(b'x' * 1024)  # 1KB
            await asyncio.sleep(0.01)
        
        # 負荷テスト実行
        result = await tester.run_load_test(
            test_name="memory_test",
            test_function=test_function,
            concurrent_users=1,
            duration_seconds=0.5,
            ramp_up_seconds=0.0
        )
        
        # 結果確認
        assert isinstance(result.memory_leak_detected, bool)
        
        # クリーンアップ
        data_holder.clear()
    
    @pytest.mark.asyncio
    async def test_resource_monitoring(self):
        """リソース監視テスト"""
        tester = LoadTester()
        
        async def test_function():
            await asyncio.sleep(0.01)
        
        # 負荷テスト実行
        result = await tester.run_load_test(
            test_name="resource_test",
            test_function=test_function,
            concurrent_users=1,
            duration_seconds=0.5,
            ramp_up_seconds=0.0
        )
        
        # リソース使用状況確認
        assert len(result.resource_usage_timeline) > 0
        
        for resource in result.resource_usage_timeline:
            assert resource.cpu_percent >= 0
            assert resource.memory_mb > 0
            assert resource.thread_count > 0
    
    def test_stress_test_memory(self):
        """メモリストレステスト"""
        tester = LoadTester()
        
        # 短時間のメモリストレステスト
        tester.stress_test_memory(size_mb=10, duration_seconds=0.1)
        
        # エラーが発生しないことを確認
        assert True
    
    @pytest.mark.asyncio
    async def test_stress_test_cpu(self):
        """CPUストレステスト"""
        tester = LoadTester()
        
        # 短時間のCPUストレステスト
        await tester.stress_test_cpu(duration_seconds=0.1, threads=2)
        
        # エラーが発生しないことを確認
        assert True
    
    def test_analyze_results(self):
        """結果分析テスト"""
        tester = LoadTester()
        
        # ダミー結果作成
        result = LoadTestResult(
            test_name="analysis_test",
            duration_seconds=10.0,
            concurrent_users=5,
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            avg_response_time=50.0,
            max_response_time=200.0,
            requests_per_second=10.0,
            memory_leak_detected=False,
            error_breakdown={"TimeoutError": 3, "ConnectionError": 2},
            resource_usage_timeline=[]
        )
        
        # 分析実行
        analysis = tester.analyze_results(result)
        
        # 分析結果確認
        assert analysis["summary"]["success_rate"] == 95.0
        assert analysis["performance"]["avg_response_time"] == 50.0
        assert analysis["reliability"]["error_rate"] == 5.0
        assert analysis["assessment"] == "優秀"  # 50ms < 100ms
    
    @pytest.mark.asyncio
    async def test_sync_function_support(self):
        """同期関数のサポートテスト"""
        tester = LoadTester()
        
        # 同期関数
        def sync_test_function():
            time.sleep(0.01)
        
        # 負荷テスト実行
        result = await tester.run_load_test(
            test_name="sync_test",
            test_function=sync_test_function,
            concurrent_users=1,
            duration_seconds=0.5,
            ramp_up_seconds=0.0
        )
        
        # 結果確認
        assert result.total_requests > 0
        assert result.successful_requests > 0