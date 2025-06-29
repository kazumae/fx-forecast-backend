"""リソース管理モジュール

長時間稼働のためのメモリ管理と最適化機能を提供する。
"""

import gc
import logging
import threading
import time
import weakref
from typing import Any, Dict, Optional


class ResourceManager:
    """リソース管理クラス
    
    メモリリークの防止と定期的なクリーンアップを行う。
    """
    
    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        self.resources: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self.gc_thread: Optional[threading.Thread] = None
        self.is_running = False
        self._lock = threading.Lock()
        
        # GC統計情報
        self.gc_stats = {
            'total_collections': 0,
            'total_objects_collected': 0,
            'last_collection_time': None
        }
        
    def register_resource(self, name: str, resource: Any) -> None:
        """リソースを登録
        
        Args:
            name: リソース名
            resource: 管理対象のリソース
        """
        with self._lock:
            self.resources[name] = resource
            self.logger.debug(f"Resource registered: {name}")
    
    def unregister_resource(self, name: str) -> None:
        """リソースの登録を解除
        
        Args:
            name: リソース名
        """
        with self._lock:
            if name in self.resources:
                del self.resources[name]
                self.logger.debug(f"Resource unregistered: {name}")
    
    def start_gc_cycle(self, interval: int = 3600) -> None:
        """定期的なガベージコレクションを開始
        
        Args:
            interval: GC実行間隔（秒）
        """
        if self.is_running:
            self.logger.warning("GC cycle already running")
            return
            
        self.is_running = True
        self.gc_thread = threading.Thread(
            target=self._gc_loop,
            args=(interval,),
            daemon=True,
            name="ResourceManagerGCThread"
        )
        self.gc_thread.start()
        self.logger.info(f"Garbage collection cycle started (interval: {interval}s)")
    
    def stop_gc_cycle(self) -> None:
        """ガベージコレクションサイクルを停止"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        if self.gc_thread:
            self.gc_thread.join(timeout=5.0)
            if self.gc_thread.is_alive():
                self.logger.warning("GC thread did not stop cleanly")
        
        self.logger.info("Garbage collection cycle stopped")
    
    def _gc_loop(self, interval: int) -> None:
        """ガベージコレクションループ
        
        Args:
            interval: GC実行間隔（秒）
        """
        self.logger.debug("GC loop started")
        
        # 初回は少し待ってから開始
        time.sleep(60)
        
        while self.is_running:
            try:
                self.perform_cleanup()
                time.sleep(interval)
            except Exception as e:
                self.logger.error(f"Error in GC loop: {e}", exc_info=True)
                time.sleep(interval)
        
        self.logger.debug("GC loop ended")
    
    def perform_cleanup(self) -> None:
        """クリーンアップ処理を実行"""
        self.logger.info("Performing resource cleanup")
        start_time = time.time()
        
        # リソースの状態確認
        self.check_resource_health()
        
        # 明示的なガベージコレクション
        gc.collect(2)  # 全世代を収集
        collected = gc.collect()
        
        with self._lock:
            self.gc_stats['total_collections'] += 1
            self.gc_stats['total_objects_collected'] += collected
            self.gc_stats['last_collection_time'] = time.time()
        
        self.logger.info(
            f"Garbage collected: {collected} objects "
            f"(total: {self.gc_stats['total_objects_collected']})"
        )
        
        # 循環参照のチェック
        self.check_circular_references()
        
        # クリーンアップ時間
        elapsed = time.time() - start_time
        self.logger.info(f"Cleanup completed in {elapsed:.2f} seconds")
    
    def check_circular_references(self) -> None:
        """循環参照をチェック"""
        # ガベージとして残っているオブジェクトを確認
        garbage_count = len(gc.garbage)
        if garbage_count > 0:
            self.logger.warning(
                f"Potential circular references detected: "
                f"{garbage_count} objects in gc.garbage"
            )
            
            # デバッグ情報を出力（最初の5個まで）
            for i, obj in enumerate(gc.garbage[:5]):
                try:
                    obj_type = type(obj).__name__
                    self.logger.debug(f"Garbage object {i}: {obj_type}")
                except Exception:
                    self.logger.debug(f"Garbage object {i}: <unknown>")
    
    def check_resource_health(self) -> None:
        """リソースの健全性チェック"""
        with self._lock:
            active_resources = []
            garbage_collected = []
            
            for name in list(self.resources.keys()):
                if name in self.resources:
                    active_resources.append(name)
                else:
                    garbage_collected.append(name)
            
            if active_resources:
                self.logger.debug(
                    f"Active resources ({len(active_resources)}): "
                    f"{', '.join(active_resources[:5])}"
                    f"{'...' if len(active_resources) > 5 else ''}"
                )
            
            if garbage_collected:
                self.logger.debug(
                    f"Garbage collected resources ({len(garbage_collected)}): "
                    f"{', '.join(garbage_collected[:5])}"
                    f"{'...' if len(garbage_collected) > 5 else ''}"
                )
    
    def get_stats(self) -> Dict[str, Any]:
        """GC統計情報を取得
        
        Returns:
            dict: 統計情報
        """
        with self._lock:
            stats = self.gc_stats.copy()
            stats['active_resources'] = len(self.resources)
            stats['gc_thresholds'] = gc.get_threshold()
            stats['gc_counts'] = gc.get_count()
            return stats
    
    def force_cleanup(self) -> int:
        """強制的にクリーンアップを実行
        
        Returns:
            int: 収集されたオブジェクト数
        """
        self.logger.info("Forcing immediate cleanup")
        gc.collect(2)
        collected = gc.collect()
        self.logger.info(f"Force cleanup collected: {collected} objects")
        return collected


class LongRunningOptimizations:
    """長時間稼働のための最適化設定"""
    
    @staticmethod
    def setup_optimizations() -> None:
        """長時間稼働用の最適化を設定"""
        logger = logging.getLogger(__name__)
        logger.info("Setting up long-running optimizations")
        
        # Pythonの最適化フラグ
        # より頻繁にGCを実行して、メモリ使用量を抑える
        gc.set_threshold(700, 10, 10)
        logger.debug(f"GC thresholds set to: {gc.get_threshold()}")
        
        # GCデバッグフラグを無効化（パフォーマンス向上）
        gc.set_debug(0)
        
        # 循環参照の自動検出を有効化
        gc.enable()
        
        logger.info("Long-running optimizations applied")
    
    @staticmethod
    def get_memory_info() -> Dict[str, Any]:
        """メモリ使用情報を取得
        
        Returns:
            dict: メモリ情報
        """
        import sys
        
        info = {
            'gc_enabled': gc.isenabled(),
            'gc_thresholds': gc.get_threshold(),
            'gc_counts': gc.get_count(),
            'garbage_count': len(gc.garbage)
        }
        
        # オブジェクト数の統計
        all_objects = gc.get_objects()
        type_counts = {}
        for obj in all_objects[:1000]:  # 最初の1000個のみチェック
            obj_type = type(obj).__name__
            type_counts[obj_type] = type_counts.get(obj_type, 0) + 1
        
        # 上位10種類を取得
        top_types = sorted(
            type_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        info['total_objects'] = len(all_objects)
        info['top_object_types'] = dict(top_types)
        
        return info