import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class TraderMadeConfig:
    """TraderMade WebSocket接続用の設定クラス"""
    api_key: str
    websocket_url: str
    target_symbol: str
    log_level: str
    log_file_path: str
    reconnect_interval: int
    max_reconnect_interval: int
    heartbeat_interval: int

    @classmethod
    def from_env(cls) -> "TraderMadeConfig":
        """環境変数から設定を読み込む"""
        api_key = os.getenv('TRADERMADE_STREAMING_API_KEY') or os.getenv('TRADERMADE_API_KEY')
        if not api_key:
            raise ValueError("TRADERMADE_STREAMING_API_KEY or TRADERMADE_API_KEY is required")
        
        return cls(
            api_key=api_key,
            websocket_url=os.getenv('TRADERMADE_WEBSOCKET_URL', 'wss://marketdata.tradermade.com/feedadv'),
            target_symbol=os.getenv('TARGET_SYMBOL', 'XAUUSD'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_file_path=os.getenv('LOG_FILE_PATH', '/app/logs'),
            reconnect_interval=int(os.getenv('RECONNECT_INTERVAL', '1')),
            max_reconnect_interval=int(os.getenv('MAX_RECONNECT_INTERVAL', '60')),
            heartbeat_interval=int(os.getenv('HEARTBEAT_INTERVAL', '30'))
        )
    
    def validate(self) -> None:
        """設定値のバリデーション"""
        if not self.api_key:
            raise ValueError("API key cannot be empty")
        
        if not self.websocket_url.startswith(('ws://', 'wss://')):
            raise ValueError("Invalid WebSocket URL format")
        
        if self.reconnect_interval < 1:
            raise ValueError("Reconnect interval must be at least 1 second")
        
        if self.max_reconnect_interval < self.reconnect_interval:
            raise ValueError("Max reconnect interval must be greater than or equal to reconnect interval")
        
        if self.heartbeat_interval < 1:
            raise ValueError("Heartbeat interval must be at least 1 second")
        
        if self.log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            raise ValueError(f"Invalid log level: {self.log_level}")
    
    def get_masked_api_key(self) -> str:
        """APIキーをマスク化して返す（ログ出力用）"""
        if len(self.api_key) <= 8:
            return "***"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"