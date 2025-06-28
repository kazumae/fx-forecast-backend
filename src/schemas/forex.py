from typing import Optional, Dict, List
from datetime import datetime
from pydantic import BaseModel

class ForexRateBase(BaseModel):
    currency_pair: str
    rate: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    timestamp: datetime

class ForexRateCreate(ForexRateBase):
    pass

class ForexRate(ForexRateBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ForecastRequest(BaseModel):
    currency_pair: str
    forecast_horizon: int = 1  # days
    model_type: Optional[str] = "arima"

class ForexForecast(BaseModel):
    id: int
    currency_pair: str
    forecast_date: datetime
    predicted_rate: float
    confidence_interval: Optional[Dict[str, float]] = None
    model_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ForexAnalysis(BaseModel):
    currency_pair: str
    current_rate: float
    daily_change: float
    weekly_change: float
    monthly_change: float
    volatility: float
    trend: str  # "bullish", "bearish", "neutral"