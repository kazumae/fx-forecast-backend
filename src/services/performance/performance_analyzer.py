"""パフォーマンス分析サービス"""
import time
import psutil
import statistics
import tracemalloc
from contextlib import contextmanager
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable
import asyncio
import threading
import cProfile
import pstats
import io
from decimal import Decimal

from src.domain.models.performance import (
    PerformanceStatus, ImpactLevel, BottleneckType,
    ModuleMetrics, DatabaseMetrics, ResourceUsage,
    Bottleneck, OptimizationRecommendation,
    PerformanceSummary, PerformanceAnalysisResult
)


class PerformanceAnalyzer:
    """パフォーマンス分析器"""
    
    def __init__(self, target_time_ms: float = 1000.0):
        """
        Args:
            target_time_ms: 目標実行時間（ミリ秒）
        """
        self.target_time_ms = target_time_ms
        self.metrics = defaultdict(list)
        self.db_queries = []
        self.resource_snapshots = []
        self.start_time = None
        self.process = psutil.Process()
        
        # プロファイラー
        self.profiler = None
        self.memory_tracking = False
        
    @contextmanager
    def measure(self, module_name: str, metadata: Optional[Dict[str, Any]] = None):
        """実行時間とリソース使用量を計測"""
        # 開始時のリソース状態
        start_time = time.perf_counter()
        start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        start_cpu = self.process.cpu_percent()
        
        # メタデータ
        context = {
            "module": module_name,
            "metadata": metadata or {},
            "thread_id": threading.current_thread().ident,
            "start_time": datetime.now(timezone.utc)
        }
        
        try:
            yield context
        finally:
            # 終了時の計測
            end_time = time.perf_counter()
            end_memory = self.process.memory_info().rss / 1024 / 1024
            
            # メトリクス記録
            elapsed_ms = (end_time - start_time) * 1000
            memory_delta = end_memory - start_memory
            
            self.metrics[module_name].append({
                "time": elapsed_ms,
                "memory_delta": memory_delta,
                "cpu_usage": self.process.cpu_percent() - start_cpu,
                "context": context
            })
    
    def record_db_query(self, query: str, execution_time: float, rows_affected: int = 0):
        """データベースクエリを記録"""
        self.db_queries.append({
            "query": query,
            "time": execution_time,
            "rows_affected": rows_affected,
            "timestamp": datetime.now(timezone.utc)
        })
    
    def start_profiling(self):
        """詳細プロファイリング開始"""
        self.profiler = cProfile.Profile()
        self.profiler.enable()
        
        # メモリトラッキング
        if not self.memory_tracking:
            tracemalloc.start()
            self.memory_tracking = True
    
    def stop_profiling(self) -> Dict[str, Any]:
        """プロファイリング停止と結果取得"""
        if self.profiler:
            self.profiler.disable()
            
            # プロファイル結果を文字列で取得
            s = io.StringIO()
            ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
            ps.print_stats(50)  # 上位50件
            profile_output = s.getvalue()
            
            self.profiler = None
            return {"profile": profile_output}
        
        return {}
    
    def capture_resource_snapshot(self):
        """現在のリソース使用状況をキャプチャ"""
        memory_info = self.process.memory_info()
        io_counters = self.process.io_counters()
        
        try:
            net_io = psutil.net_io_counters()
        except:
            net_io = None
        
        snapshot = ResourceUsage(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=self.process.cpu_percent(),
            memory_mb=memory_info.rss / 1024 / 1024,
            memory_percent=self.process.memory_percent(),
            thread_count=self.process.num_threads(),
            file_descriptors=len(self.process.open_files()),
            io_read_mb=io_counters.read_bytes / 1024 / 1024,
            io_write_mb=io_counters.write_bytes / 1024 / 1024,
            network_sent_mb=net_io.bytes_sent / 1024 / 1024 if net_io else 0,
            network_recv_mb=net_io.bytes_recv / 1024 / 1024 if net_io else 0
        )
        
        self.resource_snapshots.append(snapshot)
        return snapshot
    
    def analyze(self) -> PerformanceAnalysisResult:
        """収集したメトリクスを分析"""
        # 全体の実行時間
        total_time = sum(
            sum(m["time"] for m in measurements)
            for measurements in self.metrics.values()
        )
        
        # パフォーマンスステータス判定
        if total_time <= self.target_time_ms:
            status = PerformanceStatus.PASS
        elif total_time <= self.target_time_ms * 1.2:
            status = PerformanceStatus.WARNING
        else:
            status = PerformanceStatus.FAIL
        
        # モジュール別分析
        module_breakdown = self._analyze_modules()
        
        # リソース使用量
        resource_usage = self._analyze_resource_usage()
        
        # データベース分析
        database_metrics = self._analyze_database() if self.db_queries else None
        
        # ボトルネック検出
        bottlenecks = self._detect_bottlenecks(module_breakdown, database_metrics)
        
        # 最適化推奨事項
        recommendations = self._generate_recommendations(bottlenecks)
        
        # サマリー作成
        summary = PerformanceSummary(
            timestamp=datetime.now(timezone.utc),
            total_execution_time=total_time,
            target_time=self.target_time_ms,
            performance_status=status,
            throughput=self._calculate_throughput(),
            latency_p50=self._calculate_percentile(50),
            latency_p95=self._calculate_percentile(95),
            latency_p99=self._calculate_percentile(99),
            error_rate=0.0  # TODO: エラー率の実装
        )
        
        return PerformanceAnalysisResult(
            summary=summary,
            module_breakdown=module_breakdown,
            resource_usage=resource_usage,
            database_metrics=database_metrics,
            bottlenecks=bottlenecks,
            optimization_recommendations=recommendations
        )
    
    def _analyze_modules(self) -> List[ModuleMetrics]:
        """モジュール別メトリクスを分析"""
        total_time = sum(
            sum(m["time"] for m in measurements)
            for measurements in self.metrics.values()
        )
        
        module_metrics = []
        
        for module_name, measurements in self.metrics.items():
            if not measurements:
                continue
            
            times = [m["time"] for m in measurements]
            module_total = sum(times)
            
            metrics = ModuleMetrics(
                name=module_name,
                total_time=module_total,
                calls=len(measurements),
                avg_time=statistics.mean(times),
                max_time=max(times),
                min_time=min(times),
                percentage=(module_total / total_time * 100) if total_time > 0 else 0,
                memory_delta=sum(m["memory_delta"] for m in measurements)
            )
            
            module_metrics.append(metrics)
        
        # 実行時間順にソート
        module_metrics.sort(key=lambda x: x.total_time, reverse=True)
        
        return module_metrics
    
    def _analyze_resource_usage(self) -> ResourceUsage:
        """リソース使用量を分析"""
        if self.resource_snapshots:
            # 最大値を使用
            peak_memory = max(s.memory_mb for s in self.resource_snapshots)
            peak_cpu = max(s.cpu_percent for s in self.resource_snapshots)
            
            latest = self.resource_snapshots[-1]
            
            return ResourceUsage(
                timestamp=latest.timestamp,
                cpu_percent=peak_cpu,
                memory_mb=peak_memory,
                memory_percent=latest.memory_percent,
                thread_count=latest.thread_count,
                file_descriptors=latest.file_descriptors,
                io_read_mb=latest.io_read_mb,
                io_write_mb=latest.io_write_mb,
                network_sent_mb=latest.network_sent_mb,
                network_recv_mb=latest.network_recv_mb
            )
        else:
            # 現在の状態を返す
            return self.capture_resource_snapshot()
    
    def _analyze_database(self) -> DatabaseMetrics:
        """データベースメトリクスを分析"""
        if not self.db_queries:
            return None
        
        query_times = [q["time"] for q in self.db_queries]
        total_time = sum(query_times)
        
        # 最も遅いクエリ
        slowest_queries = sorted(
            self.db_queries,
            key=lambda x: x["time"],
            reverse=True
        )[:5]
        
        return DatabaseMetrics(
            total_queries=len(self.db_queries),
            total_time=total_time,
            avg_query_time=statistics.mean(query_times),
            slowest_queries=[
                {
                    "sql": q["query"][:100] + "..." if len(q["query"]) > 100 else q["query"],
                    "time": q["time"]
                }
                for q in slowest_queries
            ],
            connection_pool_stats={},  # TODO: 実装
            cache_hit_rate=0.0  # TODO: 実装
        )
    
    def _detect_bottlenecks(
        self,
        modules: List[ModuleMetrics],
        db_metrics: Optional[DatabaseMetrics]
    ) -> List[Bottleneck]:
        """ボトルネックを検出"""
        bottlenecks = []
        
        # データベースボトルネック
        if db_metrics and db_metrics.total_time > 200:  # 200ms以上
            bottlenecks.append(Bottleneck(
                type=BottleneckType.DATABASE,
                description="データベースクエリの実行時間が長い",
                impact=ImpactLevel.HIGH if db_metrics.total_time > 500 else ImpactLevel.MEDIUM,
                time_cost=db_metrics.total_time,
                occurrence_count=db_metrics.total_queries,
                suggestion="インデックスの追加、クエリ最適化、またはキャッシュの導入を検討",
                affected_modules=["database"]
            ))
        
        # アルゴリズムボトルネック
        for module in modules[:3]:  # 上位3モジュール
            if module.percentage > 30:  # 30%以上の時間を消費
                bottlenecks.append(Bottleneck(
                    type=BottleneckType.ALGORITHM,
                    description=f"{module.name}の処理時間が全体の{module.percentage:.1f}%を占める",
                    impact=ImpactLevel.HIGH if module.percentage > 50 else ImpactLevel.MEDIUM,
                    time_cost=module.total_time,
                    occurrence_count=module.calls,
                    suggestion="アルゴリズムの最適化または並列処理の導入を検討",
                    affected_modules=[module.name]
                ))
        
        # メモリボトルネック
        if self.resource_snapshots:
            peak_memory = max(s.memory_mb for s in self.resource_snapshots)
            if peak_memory > 512:  # 512MB以上
                bottlenecks.append(Bottleneck(
                    type=BottleneckType.MEMORY,
                    description=f"メモリ使用量が{peak_memory:.0f}MBに達している",
                    impact=ImpactLevel.MEDIUM,
                    time_cost=0,
                    occurrence_count=1,
                    suggestion="データ構造の最適化またはストリーミング処理の導入を検討",
                    affected_modules=[]
                ))
        
        return bottlenecks
    
    def _generate_recommendations(
        self,
        bottlenecks: List[Bottleneck]
    ) -> List[OptimizationRecommendation]:
        """最適化推奨事項を生成"""
        recommendations = []
        priority = 1
        
        for bottleneck in bottlenecks:
            if bottleneck.type == BottleneckType.DATABASE:
                recommendations.append(OptimizationRecommendation(
                    priority=priority,
                    action="データベースクエリの最適化",
                    expected_improvement=f"{bottleneck.time_cost * 0.5:.0f}ms削減",
                    effort="medium",
                    implementation="複合インデックスの作成とクエリプランの分析",
                    risks=["インデックス作成時の一時的なパフォーマンス低下"],
                    dependencies=["データベース管理者の協力"],
                    estimated_hours=8.0
                ))
                priority += 1
            
            elif bottleneck.type == BottleneckType.ALGORITHM:
                recommendations.append(OptimizationRecommendation(
                    priority=priority,
                    action=f"{bottleneck.affected_modules[0]}の並列化",
                    expected_improvement=f"{bottleneck.time_cost * 0.3:.0f}ms削減",
                    effort="high",
                    implementation="asyncio/ThreadPoolExecutorによる並列処理",
                    risks=["並行性バグの可能性", "デバッグの複雑化"],
                    dependencies=["並列処理可能なアルゴリズムの設計"],
                    estimated_hours=16.0
                ))
                priority += 1
            
            elif bottleneck.type == BottleneckType.MEMORY:
                recommendations.append(OptimizationRecommendation(
                    priority=priority,
                    action="メモリ使用量の削減",
                    expected_improvement="メモリ使用量50%削減",
                    effort="medium",
                    implementation="ジェネレータとストリーミング処理の活用",
                    risks=["コードの複雑化"],
                    dependencies=["データフロー設計の見直し"],
                    estimated_hours=12.0
                ))
                priority += 1
        
        # キャッシング推奨
        if any(b.type == BottleneckType.DATABASE for b in bottlenecks):
            recommendations.append(OptimizationRecommendation(
                priority=priority,
                action="結果キャッシュの導入",
                expected_improvement="繰り返しクエリの削減",
                effort="low",
                implementation="Redis/メモリキャッシュの導入",
                risks=["キャッシュ無効化の複雑性"],
                dependencies=["キャッシュインフラの準備"],
                estimated_hours=6.0
            ))
        
        return recommendations
    
    def _calculate_throughput(self) -> float:
        """スループットを計算"""
        if not self.metrics:
            return 0.0
        
        # 総実行回数
        total_calls = sum(len(m) for m in self.metrics.values())
        
        # 総実行時間（秒）
        total_time_seconds = sum(
            sum(m["time"] for m in measurements) / 1000
            for measurements in self.metrics.values()
        )
        
        return total_calls / total_time_seconds if total_time_seconds > 0 else 0.0
    
    def _calculate_percentile(self, percentile: int) -> float:
        """レイテンシのパーセンタイルを計算"""
        all_times = []
        for measurements in self.metrics.values():
            all_times.extend(m["time"] for m in measurements)
        
        if not all_times:
            return 0.0
        
        sorted_times = sorted(all_times)
        index = int(len(sorted_times) * percentile / 100)
        
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def reset(self):
        """メトリクスをリセット"""
        self.metrics.clear()
        self.db_queries.clear()
        self.resource_snapshots.clear()
        
        if self.memory_tracking:
            tracemalloc.stop()
            self.memory_tracking = False