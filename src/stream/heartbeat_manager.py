"""ハートビート管理モジュール

WebSocket接続の健全性を監視し、必要に応じて再接続を行う。
websocket-clientの組み込みping/pong機能を活用する。
"""

import logging
import threading
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .websocket_manager import WebSocketManager


class HeartbeatManager:
    """ハートビート管理クラス
    
    WebSocket接続の健全性を監視し、必要に応じて再接続をトリガーする。
    注: ping/pongはwebsocket-clientライブラリが自動的に処理する。
    """
    
    def __init__(self, websocket_manager: 'WebSocketManager', config):
        """初期化
        
        Args:
            websocket_manager: WebSocket管理インスタンス
            config: 設定インスタンス
        """
        self.websocket_manager = websocket_manager
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.monitor_thread: Optional[threading.Thread] = None
        self.last_activity_time: float = time.time()
        self.is_running: bool = False
        self._lock = threading.Lock()
        
    def start_heartbeat(self) -> None:
        """ハートビート監視を開始"""
        with self._lock:
            if self.is_running:
                self.logger.warning("Heartbeat monitor already running")
                return
                
            self.is_running = True
            self.last_activity_time = time.time()
            self.monitor_thread = threading.Thread(
                target=self.monitor_loop,
                daemon=True,
                name="HeartbeatMonitorThread"
            )
            self.monitor_thread.start()
            self.logger.info("Heartbeat monitor started (ping interval: {}s)".format(
                self.config.heartbeat_interval
            ))
        
    def stop_heartbeat(self) -> None:
        """ハートビート監視を停止"""
        with self._lock:
            if not self.is_running:
                return
                
            self.is_running = False
            
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
            if self.monitor_thread.is_alive():
                self.logger.warning("Heartbeat monitor thread did not stop cleanly")
            
        self.logger.info("Heartbeat monitor stopped")
        
    def monitor_loop(self) -> None:
        """接続健全性監視ループ"""
        self.logger.debug("Heartbeat monitor loop started")
        
        while self.is_running:
            try:
                # 接続状態をチェック
                if self.websocket_manager.is_connected:
                    # タイムアウトチェック
                    if self.check_activity_timeout():
                        self.handle_timeout()
                    else:
                        self.logger.debug(
                            f"Connection healthy - last activity: "
                            f"{time.time() - self.last_activity_time:.1f}s ago"
                        )
                else:
                    self.logger.debug("WebSocket not connected, skipping heartbeat check")
                    
                # 監視間隔（heartbeat_intervalと同じ間隔でチェック）
                time.sleep(self.config.heartbeat_interval)
                
            except Exception as e:
                self.logger.error(f"Heartbeat monitor error: {e}", exc_info=True)
                time.sleep(self.config.heartbeat_interval)
                
        self.logger.debug("Heartbeat monitor loop ended")
        
    def update_activity(self) -> None:
        """アクティビティ時刻を更新（データ受信時などに呼ばれる）"""
        with self._lock:
            self.last_activity_time = time.time()
        
    def check_activity_timeout(self) -> bool:
        """アクティビティタイムアウトチェック
        
        Returns:
            bool: タイムアウトした場合True
        """
        # タイムアウト閾値（heartbeat_intervalの2倍）
        # websocket-clientのping/pongメカニズムが正常に動作していれば、
        # この時間内に必ずアクティビティがあるはず
        timeout_threshold = self.config.heartbeat_interval * 2
        
        with self._lock:
            elapsed = time.time() - self.last_activity_time
        
        if elapsed > timeout_threshold:
            self.logger.warning(
                f"Activity timeout: {elapsed:.1f}s since last activity "
                f"(threshold: {timeout_threshold}s)"
            )
            return True
        return False
        
    def handle_timeout(self) -> None:
        """タイムアウト処理"""
        self.logger.error("Connection health check failed, initiating reconnection")
        
        # WebSocketManagerの再接続をトリガー
        # 別スレッドで実行して、監視ループをブロックしない
        threading.Thread(
            target=self.websocket_manager.reconnect,
            daemon=True,
            name="HeartbeatReconnectThread"
        ).start()
        
    def reset_activity_time(self) -> None:
        """アクティビティ時刻をリセット（接続直後などに使用）"""
        with self._lock:
            self.last_activity_time = time.time()
        self.logger.debug("Activity time reset")
        
    def on_pong(self, ws, message) -> None:
        """Pong受信時の処理（websocket-clientから呼ばれる）
        
        Args:
            ws: WebSocketインスタンス
            message: Pongメッセージ
        """
        self.update_activity()
        self.logger.debug("Pong received - activity updated")