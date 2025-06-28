from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.models.forex import ForexRate, ForexForecast
from src.schemas.forex import ForecastRequest

def get_forex_rates(
    db: Session, 
    currency_pair: str, 
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[ForexRate]:
    query = db.query(ForexRate).filter(ForexRate.currency_pair == currency_pair)
    
    if start_date:
        query = query.filter(ForexRate.timestamp >= start_date)
    if end_date:
        query = query.filter(ForexRate.timestamp <= end_date)
    
    return query.order_by(desc(ForexRate.timestamp)).all()

def get_latest_rate(db: Session, currency_pair: str) -> Optional[ForexRate]:
    return db.query(ForexRate)\
        .filter(ForexRate.currency_pair == currency_pair)\
        .order_by(desc(ForexRate.timestamp))\
        .first()

def create_forex_rate(db: Session, rate_data: dict) -> ForexRate:
    db_rate = ForexRate(**rate_data)
    db.add(db_rate)
    db.commit()
    db.refresh(db_rate)
    return db_rate

def generate_forecast(db: Session, forecast_request: ForecastRequest) -> ForexForecast:
    # This is a placeholder for actual forecasting logic
    # In production, this would call a machine learning model
    latest_rate = get_latest_rate(db, forecast_request.currency_pair)
    
    if not latest_rate:
        predicted_rate = 100.0  # Default value
    else:
        # Simple mock prediction (random walk)
        import random
        predicted_rate = latest_rate.rate * (1 + random.uniform(-0.02, 0.02))
    
    forecast_date = datetime.utcnow() + timedelta(days=forecast_request.forecast_horizon)
    
    db_forecast = ForexForecast(
        currency_pair=forecast_request.currency_pair,
        forecast_date=forecast_date,
        predicted_rate=predicted_rate,
        confidence_interval={"lower": predicted_rate * 0.98, "upper": predicted_rate * 1.02},
        model_name=forecast_request.model_type
    )
    
    db.add(db_forecast)
    db.commit()
    db.refresh(db_forecast)
    return db_forecast

def get_currency_analysis(db: Session, currency_pair: str) -> dict:
    # Get rates for different time periods
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    current_rate = get_latest_rate(db, currency_pair)
    if not current_rate:
        return None
    
    # Calculate changes (simplified)
    daily_change = 0.0  # Would calculate from historical data
    weekly_change = 0.0
    monthly_change = 0.0
    
    return {
        "currency_pair": currency_pair,
        "current_rate": current_rate.rate,
        "daily_change": daily_change,
        "weekly_change": weekly_change,
        "monthly_change": monthly_change,
        "volatility": 0.0,  # Would calculate from historical data
        "trend": "neutral"
    }