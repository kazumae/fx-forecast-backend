"""パフォーマンス分析関連のドメインモデル"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum


class PerformanceStatus(Enum):
    """パフォーマンスステータス"""
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class ImpactLevel(Enum):
    """影響度レベル"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BottleneckType(Enum):
    """ボトルネックタイプ"""
    DATABASE = "database"
    ALGORITHM = "algorithm"
    IO = "io"
    NETWORK = "network"
    MEMORY = "memory"
    CPU = "cpu"


@dataclass
class ModuleMetrics:
    """モジュールメトリクス"""
    name: str
    total_time: float  # ミリ秒
    calls: int
    avg_time: float
    max_time: float
    min_time: float
    percentage: float
    memory_delta: float  # MB
    sub_modules: List['ModuleMetrics'] = field(default_factory=list)
    
    @property
    def time_per_call(self) -> float:
        """1回あたりの実行時間"""
        return self.total_time / self.calls if self.calls > 0 else 0.0


@dataclass
class DatabaseMetrics:
    """データベースメトリクス"""
    total_queries: int
    total_time: float  # ミリ秒
    avg_query_time: float
    slowest_queries: List[Dict[str, Any]]
    connection_pool_stats: Dict[str, Any]
    cache_hit_rate: float


@dataclass
class ResourceUsage:
    """リソース使用量"""
    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    thread_count: int
    file_descriptors: int
    io_read_mb: float
    io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float


@dataclass
class Bottleneck:
    """ボトルネック"""
    type: BottleneckType
    description: str
    impact: ImpactLevel
    time_cost: float  # ミリ秒
    occurrence_count: int
    suggestion: str
    affected_modules: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationRecommendation:
    """最適化推奨事項"""
    priority: int
    action: str
    expected_improvement: str
    effort: str  # low, medium, high
    implementation: str
    risks: List[str]
    dependencies: List[str]
    estimated_hours: float


@dataclass
class PerformanceSummary:
    """パフォーマンスサマリー"""
    timestamp: datetime
    total_execution_time: float  # ミリ秒
    target_time: float
    performance_status: PerformanceStatus
    throughput: float  # 処理数/秒
    latency_p50: float
    latency_p95: float
    latency_p99: float
    error_rate: float


@dataclass
class PerformanceAnalysisResult:
    """パフォーマンス分析結果"""
    summary: PerformanceSummary
    module_breakdown: List[ModuleMetrics]
    resource_usage: ResourceUsage
    database_metrics: Optional[DatabaseMetrics]
    bottlenecks: List[Bottleneck]
    optimization_recommendations: List[OptimizationRecommendation]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "performance_summary": {
                "total_execution_time": self.summary.total_execution_time,
                "target_time": self.summary.target_time,
                "performance_status": self.summary.performance_status.value,
                "timestamp": self.summary.timestamp.isoformat(),
                "throughput": self.summary.throughput,
                "latency_p50": self.summary.latency_p50,
                "latency_p95": self.summary.latency_p95,
                "latency_p99": self.summary.latency_p99
            },
            "module_breakdown": [
                self._module_to_dict(module) for module in self.module_breakdown
            ],
            "resource_usage": {
                "peak_memory_mb": self.resource_usage.memory_mb,
                "avg_memory_mb": self.resource_usage.memory_mb,  # 簡略化
                "cpu_usage_percent": self.resource_usage.cpu_percent,
                "thread_count": self.resource_usage.thread_count
            },
            "bottlenecks": [
                {
                    "type": b.type.value,
                    "description": b.description,
                    "impact": b.impact.value,
                    "time_cost": b.time_cost,
                    "suggestion": b.suggestion
                }
                for b in self.bottlenecks
            ],
            "optimization_recommendations": [
                {
                    "priority": r.priority,
                    "action": r.action,
                    "expected_improvement": r.expected_improvement,
                    "effort": r.effort,
                    "implementation": r.implementation
                }
                for r in self.optimization_recommendations
            ]
        }
    
    def _module_to_dict(self, module: ModuleMetrics) -> Dict[str, Any]:
        """モジュールメトリクスを辞書に変換"""
        result = {
            "module": module.name,
            "total_time": module.total_time,
            "percentage": module.percentage,
            "calls": module.calls,
            "avg_time": module.avg_time
        }
        
        if module.sub_modules:
            result["sub_modules"] = [
                {
                    "name": sub.name,
                    "time": sub.total_time,
                    "calls": sub.calls
                }
                for sub in module.sub_modules
            ]
        
        return result


@dataclass
class LoadTestResult:
    """負荷テスト結果"""
    test_name: str
    duration_seconds: float
    concurrent_users: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    max_response_time: float
    requests_per_second: float
    memory_leak_detected: bool
    error_breakdown: Dict[str, int]
    resource_usage_timeline: List[ResourceUsage]