from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.sql import func

from src.models.base import Base

class ForexRate(Base):
    __tablename__ = "forex_rates"

    id = Column(Integer, primary_key=True, index=True)
    currency_pair = Column(String, index=True, nullable=False)
    rate = Column(Float, nullable=False)
    bid = Column(Float)
    ask = Column(Float)
    volume = Column(Float)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ForexForecast(Base):
    __tablename__ = "forex_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    currency_pair = Column(String, index=True, nullable=False)
    forecast_date = Column(DateTime(timezone=True), nullable=False)
    predicted_rate = Column(Float, nullable=False)
    confidence_interval = Column(JSON)
    model_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())