"""
TraderMade Stream Configuration Module
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class StreamConfig:
    """Configuration for TraderMade WebSocket streaming"""
    
    # API Configuration
    api_key: str
    websocket_url: str
    target_symbol: str
    
    # Logging Configuration
    log_level: str
    log_file_path: str
    
    # Connection Configuration
    reconnect_interval: int
    max_reconnect_interval: int
    heartbeat_interval: int
    
    @classmethod
    def from_env(cls) -> "StreamConfig":
        """Create configuration from environment variables"""
        # API key is required - prioritize streaming key
        api_key = os.getenv('TRADERMADE_STREAMING_API_KEY') or os.getenv('TRADERMADE_API_KEY')
        if not api_key:
            raise ValueError(
                "TRADERMADE_STREAMING_API_KEY or TRADERMADE_API_KEY is required. "
                "Please set it in your .env file."
            )
        
        return cls(
            # API Configuration
            api_key=api_key,
            websocket_url=os.getenv(
                'TRADERMADE_WEBSOCKET_URL', 
                'wss://marketdata.tradermade.com/feedadv'
            ),
            target_symbol=os.getenv('TARGET_SYMBOL', 'XAUUSD'),
            
            # Logging Configuration
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_file_path=os.getenv('LOG_FILE_PATH', '/app/logs'),
            
            # Connection Configuration
            reconnect_interval=int(os.getenv('RECONNECT_INTERVAL', '1')),
            max_reconnect_interval=int(os.getenv('MAX_RECONNECT_INTERVAL', '60')),
            heartbeat_interval=int(os.getenv('HEARTBEAT_INTERVAL', '30'))
        )
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if not self.api_key:
            raise ValueError("API key cannot be empty")
        
        if not self.websocket_url.startswith(('ws://', 'wss://')):
            raise ValueError(f"Invalid WebSocket URL: {self.websocket_url}")
        
        if self.reconnect_interval < 1:
            raise ValueError("Reconnect interval must be at least 1 second")
        
        if self.max_reconnect_interval < self.reconnect_interval:
            raise ValueError(
                "Max reconnect interval must be greater than or equal to reconnect interval"
            )
        
        if self.heartbeat_interval < 1:
            raise ValueError("Heartbeat interval must be at least 1 second")