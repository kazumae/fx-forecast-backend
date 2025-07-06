from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "FX予測API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "sqlite:///./fx_forecast.db"
    
    # Anthropic API
    ANTHROPIC_API_KEY: Optional[str] = None
    
    # Slack Configuration
    SLACK_WEBHOOK_URL: Optional[str] = None
    SLACK_CHANNEL: str = "#fx-analysis"
    SLACK_USERNAME: str = "FX Analysis Bot"
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields


settings = Settings()