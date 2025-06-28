from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from src.schemas import forex as forex_schema
from src.services import forex as forex_service
from src.api.deps import get_db

router = APIRouter()

@router.get("/rates", response_model=List[forex_schema.ForexRate])
def get_forex_rates(
    currency_pair: str = Query(..., description="Currency pair (e.g., USD/JPY)"),
    start_date: datetime = Query(None, description="Start date for historical data"),
    end_date: datetime = Query(None, description="End date for historical data"),
    db: Session = Depends(get_db)
):
    rates = forex_service.get_forex_rates(
        db, 
        currency_pair=currency_pair,
        start_date=start_date,
        end_date=end_date
    )
    return rates

@router.get("/rates/latest", response_model=forex_schema.ForexRate)
def get_latest_rate(
    currency_pair: str = Query(..., description="Currency pair (e.g., USD/JPY)"),
    db: Session = Depends(get_db)
):
    rate = forex_service.get_latest_rate(db, currency_pair=currency_pair)
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    return rate

@router.post("/forecast", response_model=forex_schema.ForexForecast)
def create_forecast(
    forecast_request: forex_schema.ForecastRequest,
    db: Session = Depends(get_db)
):
    forecast = forex_service.generate_forecast(db, forecast_request=forecast_request)
    return forecast