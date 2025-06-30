from typing import List, Union
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, field_validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "FX Forecast API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/fx_forecast"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = ["http://localhost:3000", "http://localhost:8080"]
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # External APIs
    FOREX_API_KEY: str = ""
    FOREX_API_URL: str = "https://api.example.com/forex"
    
    # TraderMade API Configuration
    TRADERMADE_API_KEY: str = ""
    TRADERMADE_STREAMING_API_KEY: str = ""
    TRADERMADE_WEBSOCKET_URL: str = "wss://marketdata.tradermade.com/feedadv"
    TARGET_SYMBOL: str = "XAUUSD"
    
    # WebSocket Connection Settings
    RECONNECT_INTERVAL: int = 1
    MAX_RECONNECT_INTERVAL: int = 60
    HEARTBEAT_INTERVAL: int = 30
    
    # PostgreSQL settings (for docker-compose)
    POSTGRES_USER: str = "fx_user"
    POSTGRES_PASSWORD: str = "fx_password"
    POSTGRES_DB: str = "fx_forecast"
    
    # Slack settings
    SLACK_WEBHOOK_URL: str = ""
    SLACK_DEFAULT_CHANNEL: str = "#general"
    SLACK_BOT_TOKEN: str = ""
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Slack Error Notifications
    SLACK_ERROR_NOTIFICATION_ENABLED: bool = True
    SLACK_ERROR_NOTIFICATION_COOLDOWN: int = 300
    
    # Anthropic API Configuration
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()