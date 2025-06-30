"""負荷テストツール"""
import asyncio
import time
import statistics
from datetime import datetime, timezone
from typing import List, Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import gc

from src.domain.models.performance import (
    LoadTestResult, ResourceUsage
)
from src.services.performance.performance_analyzer import PerformanceAnalyzer


class LoadTester:
    """負荷テストツール"""
    
    def __init__(self):
        self.results = []
        self.resource_timeline = []
        self.process = psutil.Process()
        
    async def run_load_test(
        self,
        test_name: str,
        test_function: Callable,
        concurrent_users: int = 10,
        duration_seconds: float = 60.0,
        ramp_up_seconds: float = 5.0
    ) -> LoadTestResult:
        """負荷テストを実行"""
        print(f"負荷テスト '{test_name}' を開始...")
        print(f"同時ユーザー数: {concurrent_users}")
        print(f"テスト期間: {duration_seconds}秒")
        
        # メモリリーク検出用の初期状態
        gc.collect()
        initial_memory = self.process.memory_info().rss / 1024 / 1024
        
        # 結果記録
        request_results = []
        start_time = time.time()
        
        # リソース監視タスク
        monitor_task = asyncio.create_task(
            self._monitor_resources(duration_seconds)
        )
        
        # 負荷生成
        try:
            # ランプアップ
            if ramp_up_seconds > 0:
                await self._ramp_up(
                    test_function,
                    concurrent_users,
                    ramp_up_seconds,
                    request_results
                )
            
            # メイン負荷テスト
            remaining_time = duration_seconds - ramp_up_seconds
            if remaining_time > 0:
                await self._run_concurrent_load(
                    test_function,
                    concurrent_users,
                    remaining_time,
                    request_results
                )
                
        finally:
            # リソース監視停止
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        
        # 結果集計
        end_time = time.time()
        actual_duration = end_time - start_time
        
        # メモリリーク検出
        gc.collect()
        final_memory = self.process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        memory_leak_detected = memory_increase > 100  # 100MB以上の増加
        
        # 統計計算
        successful_requests = [r for r in request_results if r["success"]]
        failed_requests = [r for r in request_results if not r["success"]]
        
        response_times = [r["response_time"] for r in successful_requests]
        
        # エラー分類
        error_breakdown = {}
        for req in failed_requests:
            error_type = req.get("error_type", "Unknown")
            error_breakdown[error_type] = error_breakdown.get(error_type, 0) + 1
        
        return LoadTestResult(
            test_name=test_name,
            duration_seconds=actual_duration,
            concurrent_users=concurrent_users,
            total_requests=len(request_results),
            successful_requests=len(successful_requests),
            failed_requests=len(failed_requests),
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            requests_per_second=len(request_results) / actual_duration,
            memory_leak_detected=memory_leak_detected,
            error_breakdown=error_breakdown,
            resource_usage_timeline=self.resource_timeline.copy()
        )
    
    async def _ramp_up(
        self,
        test_function: Callable,
        target_users: int,
        ramp_up_seconds: float,
        results: List[Dict[str, Any]]
    ):
        """段階的にユーザー数を増やす"""
        steps = min(target_users, 10)  # 最大10ステップ
        step_duration = ramp_up_seconds / steps
        users_per_step = target_users // steps
        
        current_users = 0
        tasks = []
        
        for step in range(steps):
            # 新規ユーザー追加
            new_users = users_per_step
            if step == steps - 1:  # 最後のステップで端数調整
                new_users = target_users - current_users
            
            # 新規タスク作成
            for _ in range(new_users):
                task = asyncio.create_task(
                    self._run_user_session(test_function, results, ramp_up_seconds)
                )
                tasks.append(task)
            
            current_users += new_users
            
            # 次のステップまで待機
            if step < steps - 1:
                await asyncio.sleep(step_duration)
        
        # 全タスクの完了を待つ
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _run_concurrent_load(
        self,
        test_function: Callable,
        concurrent_users: int,
        duration_seconds: float,
        results: List[Dict[str, Any]]
    ):
        """同時実行負荷を生成"""
        tasks = []
        
        # 全ユーザーのタスクを作成
        for _ in range(concurrent_users):
            task = asyncio.create_task(
                self._run_user_session(test_function, results, duration_seconds)
            )
            tasks.append(task)
        
        # 全タスクの完了を待つ
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _run_user_session(
        self,
        test_function: Callable,
        results: List[Dict[str, Any]],
        duration_seconds: float
    ):
        """単一ユーザーセッションを実行"""
        session_start = time.time()
        
        while time.time() - session_start < duration_seconds:
            request_start = time.time()
            success = False
            error_type = None
            error_message = None
            
            try:
                # テスト関数実行
                if asyncio.iscoroutinefunction(test_function):
                    await test_function()
                else:
                    await asyncio.get_event_loop().run_in_executor(
                        None, test_function
                    )
                success = True
                
            except Exception as e:
                error_type = type(e).__name__
                error_message = str(e)
            
            request_end = time.time()
            
            # 結果記録
            results.append({
                "timestamp": datetime.now(timezone.utc),
                "success": success,
                "response_time": (request_end - request_start) * 1000,  # ミリ秒
                "error_type": error_type,
                "error_message": error_message
            })
            
            # 短い待機（連続リクエストを避ける）
            await asyncio.sleep(0.1)
    
    async def _monitor_resources(self, duration_seconds: float):
        """リソース使用状況を監視"""
        interval = min(1.0, duration_seconds / 100)  # 最大100サンプル
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            try:
                # リソース情報取得
                memory_info = self.process.memory_info()
                cpu_percent = self.process.cpu_percent()
                
                # ネットワークI/O
                try:
                    net_io = psutil.net_io_counters()
                except:
                    net_io = None
                
                # 記録
                snapshot = ResourceUsage(
                    timestamp=datetime.now(timezone.utc),
                    cpu_percent=cpu_percent,
                    memory_mb=memory_info.rss / 1024 / 1024,
                    memory_percent=self.process.memory_percent(),
                    thread_count=self.process.num_threads(),
                    file_descriptors=len(self.process.open_files()),
                    io_read_mb=0,  # 簡略化
                    io_write_mb=0,
                    network_sent_mb=net_io.bytes_sent / 1024 / 1024 if net_io else 0,
                    network_recv_mb=net_io.bytes_recv / 1024 / 1024 if net_io else 0
                )
                
                self.resource_timeline.append(snapshot)
                
            except Exception:
                pass  # 監視エラーは無視
            
            await asyncio.sleep(interval)
    
    def stress_test_memory(self, size_mb: int = 100, duration_seconds: float = 10):
        """メモリストレステスト"""
        print(f"メモリストレステスト: {size_mb}MB を {duration_seconds}秒間")
        
        # 大きなデータ構造を作成
        data = []
        chunk_size = 1024 * 1024  # 1MB
        chunks = size_mb
        
        start_time = time.time()
        
        try:
            for i in range(chunks):
                # 1MBのデータを追加
                data.append(b'x' * chunk_size)
                
                if time.time() - start_time > duration_seconds:
                    break
            
            # メモリ使用量確認
            memory_used = self.process.memory_info().rss / 1024 / 1024
            print(f"メモリ使用量: {memory_used:.1f}MB")
            
        finally:
            # クリーンアップ
            data.clear()
            gc.collect()
    
    async def stress_test_cpu(self, duration_seconds: float = 10, threads: int = 4):
        """CPUストレステスト"""
        print(f"CPUストレステスト: {threads}スレッドで {duration_seconds}秒間")
        
        def cpu_intensive_task():
            """CPU集約的なタスク"""
            end_time = time.time() + duration_seconds / threads
            result = 0
            
            while time.time() < end_time:
                # 計算負荷
                for i in range(10000):
                    result += i ** 2
                    result = result % 1000000
            
            return result
        
        # 並列実行
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [
                executor.submit(cpu_intensive_task)
                for _ in range(threads)
            ]
            
            # 完了待ち
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"CPUテストエラー: {e}")
        
        # CPU使用率確認
        cpu_percent = self.process.cpu_percent()
        print(f"CPU使用率: {cpu_percent:.1f}%")
    
    def analyze_results(self, result: LoadTestResult) -> Dict[str, Any]:
        """負荷テスト結果を分析"""
        analysis = {
            "summary": {
                "test_name": result.test_name,
                "duration": result.duration_seconds,
                "total_requests": result.total_requests,
                "success_rate": (result.successful_requests / result.total_requests * 100)
                               if result.total_requests > 0 else 0,
                "avg_rps": result.requests_per_second
            },
            "performance": {
                "avg_response_time": result.avg_response_time,
                "max_response_time": result.max_response_time,
                "throughput": result.requests_per_second
            },
            "reliability": {
                "error_rate": (result.failed_requests / result.total_requests * 100)
                             if result.total_requests > 0 else 0,
                "error_breakdown": result.error_breakdown,
                "memory_leak": result.memory_leak_detected
            },
            "resource_usage": {
                "peak_memory": max(r.memory_mb for r in result.resource_usage_timeline)
                              if result.resource_usage_timeline else 0,
                "avg_cpu": statistics.mean(r.cpu_percent for r in result.resource_usage_timeline)
                          if result.resource_usage_timeline else 0
            }
        }
        
        # パフォーマンス評価
        if result.avg_response_time < 100:  # 100ms以下
            analysis["assessment"] = "優秀"
        elif result.avg_response_time < 500:  # 500ms以下
            analysis["assessment"] = "良好"
        elif result.avg_response_time < 1000:  # 1秒以下
            analysis["assessment"] = "許容範囲"
        else:
            analysis["assessment"] = "要改善"
        
        return analysis