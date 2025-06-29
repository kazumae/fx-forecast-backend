"""パフォーマンスメトリクス収集モジュール

システムのパフォーマンス情報を収集し、定期的にレポートする。
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None
    logging.warning("psutil not installed. System metrics will not be available.")


@dataclass
class Metrics:
    """パフォーマンスメトリクスデータ"""
    timestamp: datetime
    memory_usage_mb: float
    cpu_percent: float
    message_count: int
    messages_per_second: float
    average_latency_ms: float
    connection_uptime_seconds: float
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'memory_usage_mb': self.memory_usage_mb,
            'cpu_percent': self.cpu_percent,
            'message_count': self.message_count,
            'messages_per_second': self.messages_per_second,
            'average_latency_ms': self.average_latency_ms,
            'connection_uptime_seconds': self.connection_uptime_seconds
        }


class MetricsCollector:
    """メトリクス収集クラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        self.start_time = time.time()
        self.message_count = 0
        self.latency_samples = deque(maxlen=1000)
        self.last_report_time = time.time()
        self.last_message_count = 0
        self._lock = threading.Lock()
        
        # psutil process object
        self.process = None
        if psutil:
            try:
                self.process = psutil.Process()
            except Exception as e:
                self.logger.warning(f"Failed to initialize psutil process: {e}")
        
        # 履歴保持（最新100件）
        self.metrics_history = deque(maxlen=100)
        
    def record_message_received(self, timestamp: Optional[float] = None) -> None:
        """メッセージ受信を記録
        
        Args:
            timestamp: メッセージのタイムスタンプ（Unixタイム）
        """
        with self._lock:
            self.message_count += 1
            
            if timestamp:
                # レイテンシー計算（受信時刻 - データのタイムスタンプ）
                latency = (time.time() - timestamp) * 1000
                # 異常値除外（1秒以上の遅延は無視）
                if 0 <= latency <= 1000:
                    self.latency_samples.append(latency)
                else:
                    self.logger.debug(f"Ignoring abnormal latency: {latency}ms")
    
    def collect_metrics(self) -> Metrics:
        """現在のメトリクスを収集
        
        Returns:
            Metrics: 収集したメトリクス
        """
        current_time = time.time()
        
        with self._lock:
            elapsed = current_time - self.last_report_time
            
            # メモリ使用量とCPU使用率
            memory_mb = 0.0
            cpu_percent = 0.0
            
            if self.process and psutil:
                try:
                    memory_info = self.process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024
                    cpu_percent = self.process.cpu_percent(interval=0.1)
                except Exception as e:
                    self.logger.debug(f"Failed to get system metrics: {e}")
            
            # メッセージレート
            message_delta = self.message_count - self.last_message_count
            messages_per_second = message_delta / elapsed if elapsed > 0 else 0
            
            # 平均レイテンシー
            avg_latency = 0.0
            if self.latency_samples:
                avg_latency = sum(self.latency_samples) / len(self.latency_samples)
            
            # 稼働時間
            uptime = current_time - self.start_time
            
            metrics = Metrics(
                timestamp=datetime.now(),
                memory_usage_mb=round(memory_mb, 2),
                cpu_percent=round(cpu_percent, 2),
                message_count=self.message_count,
                messages_per_second=round(messages_per_second, 2),
                average_latency_ms=round(avg_latency, 2),
                connection_uptime_seconds=round(uptime, 2)
            )
            
            # カウンターをリセット
            self.last_report_time = current_time
            self.last_message_count = self.message_count
            
            # 履歴に追加
            self.metrics_history.append(metrics)
            
        return metrics
    
    def report_metrics(self) -> None:
        """メトリクスをログに出力"""
        metrics = self.collect_metrics()
        
        self.logger.info(
            f"Performance Metrics - "
            f"Memory: {metrics.memory_usage_mb}MB, "
            f"CPU: {metrics.cpu_percent}%, "
            f"Messages: {metrics.message_count} total "
            f"({metrics.messages_per_second}/sec), "
            f"Latency: {metrics.average_latency_ms}ms, "
            f"Uptime: {metrics.connection_uptime_seconds}s"
        )
        
        # 異常値チェック
        self.check_anomalies(metrics)
    
    def check_anomalies(self, metrics: Metrics) -> None:
        """異常値を検出
        
        Args:
            metrics: チェック対象のメトリクス
        """
        # メモリ使用量チェック（100MB以上）
        if metrics.memory_usage_mb > 100:
            self.logger.warning(
                f"High memory usage detected: {metrics.memory_usage_mb}MB"
            )
        
        # CPU使用率チェック（50%以上）
        if metrics.cpu_percent > 50:
            self.logger.warning(
                f"High CPU usage detected: {metrics.cpu_percent}%"
            )
        
        # レイテンシーチェック（100ms以上）
        if metrics.average_latency_ms > 100:
            self.logger.warning(
                f"High latency detected: {metrics.average_latency_ms}ms"
            )
        
        # メッセージレートチェック（0の場合）
        if metrics.messages_per_second == 0 and metrics.connection_uptime_seconds > 60:
            self.logger.warning(
                "No messages received in the last period"
            )
    
    def get_history(self) -> list:
        """メトリクス履歴を取得
        
        Returns:
            list: メトリクス履歴（辞書形式）
        """
        with self._lock:
            return [m.to_dict() for m in self.metrics_history]
    
    def reset(self) -> None:
        """メトリクスをリセット"""
        with self._lock:
            self.start_time = time.time()
            self.message_count = 0
            self.latency_samples.clear()
            self.last_report_time = time.time()
            self.last_message_count = 0
            self.metrics_history.clear()
        self.logger.info("Metrics collector reset")


class MetricsReporter:
    """定期的にメトリクスをレポートするクラス"""
    
    def __init__(self, metrics_collector: MetricsCollector, interval: int = 60):
        """初期化
        
        Args:
            metrics_collector: メトリクス収集インスタンス
            interval: レポート間隔（秒）
        """
        self.metrics_collector = metrics_collector
        self.interval = interval
        self.report_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.logger = logging.getLogger(__name__)
    
    def start_reporting(self) -> None:
        """定期レポートを開始"""
        if self.is_running:
            self.logger.warning("Metrics reporter already running")
            return
        
        self.is_running = True
        self.report_thread = threading.Thread(
            target=self.report_loop,
            daemon=True,
            name="MetricsReporterThread"
        )
        self.report_thread.start()
        self.logger.info(f"Metrics reporter started (interval: {self.interval}s)")
    
    def stop_reporting(self) -> None:
        """定期レポートを停止"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.report_thread:
            self.report_thread.join(timeout=5.0)
            if self.report_thread.is_alive():
                self.logger.warning("Metrics reporter thread did not stop cleanly")
        
        self.logger.info("Metrics reporter stopped")
    
    def report_loop(self) -> None:
        """レポートループ"""
        self.logger.debug("Metrics report loop started")
        
        # 初回は少し待ってから開始
        time.sleep(10)
        
        while self.is_running:
            try:
                self.metrics_collector.report_metrics()
                time.sleep(self.interval)
            except Exception as e:
                self.logger.error(f"Error in metrics report loop: {e}", exc_info=True)
                time.sleep(self.interval)
        
        self.logger.debug("Metrics report loop ended")