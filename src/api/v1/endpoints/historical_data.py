"""
Historical Data API Endpoints for US-014

Provides REST API for querying historical forex data
"""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.services.data_persistence.forex_persistence_service import ForexPersistenceService
from src.schemas.historical_data import (
    HistoricalDataResponse, DataStatisticsResponse, ArchivalResponse,
    DataIntegrityResponse, ForexRateSchema
)


router = APIRouter()


def get_persistence_service(db: Session = Depends(get_db)) -> ForexPersistenceService:
    """Dependency to get persistence service"""
    return ForexPersistenceService(db)


@router.get("/rates/{symbol}", response_model=HistoricalDataResponse)
async def get_historical_rates(
    symbol: str,
    start_time: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    end_time: Optional[datetime] = Query(None, description="End time (ISO format)"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of records"),
    service: ForexPersistenceService = Depends(get_persistence_service)
):
    """
    Retrieve historical forex rates for a specific symbol
    
    - **symbol**: Currency pair symbol (e.g., XAUUSD)
    - **start_time**: Optional start time filter
    - **end_time**: Optional end time filter  
    - **limit**: Maximum records to return (1-10000)
    """
    try:
        # Set default time range if not provided (last 24 hours)
        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=1)
        if not end_time:
            end_time = datetime.utcnow()
        
        # Validate time range
        if start_time >= end_time:
            raise HTTPException(
                status_code=400, 
                detail="start_time must be before end_time"
            )
        
        # Get historical data
        rates = await service.get_historical_data(
            symbol=symbol.upper(),
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        return HistoricalDataResponse(
            symbol=symbol.upper(),
            start_time=start_time,
            end_time=end_time,
            count=len(rates),
            rates=[ForexRateSchema.from_orm(rate) for rate in rates]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rates/{symbol}/latest", response_model=ForexRateSchema)
async def get_latest_rate(
    symbol: str,
    service: ForexPersistenceService = Depends(get_persistence_service)
):
    """
    Get the most recent rate for a symbol
    
    - **symbol**: Currency pair symbol (e.g., XAUUSD)
    """
    try:
        rate = await service.get_latest_rate(symbol.upper())
        
        if not rate:
            raise HTTPException(
                status_code=404, 
                detail=f"No data found for symbol {symbol.upper()}"
            )
        
        return ForexRateSchema.from_orm(rate)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=HistoricalDataResponse)
async def search_rates(
    symbol: Optional[str] = Query(None, description="Currency pair symbol"),
    min_spread: Optional[float] = Query(None, ge=0, description="Minimum spread filter"),
    max_spread: Optional[float] = Query(None, ge=0, description="Maximum spread filter"),
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    service: ForexPersistenceService = Depends(get_persistence_service)
):
    """
    Advanced search for forex rates with multiple criteria
    
    - **symbol**: Optional currency pair filter
    - **min_spread**: Minimum spread filter (in price units)
    - **max_spread**: Maximum spread filter (in price units)
    - **start_time**: Optional start time filter
    - **end_time**: Optional end time filter
    - **limit**: Maximum records to return (1-1000)
    """
    try:
        # Validate spread filters
        if min_spread is not None and max_spread is not None:
            if min_spread > max_spread:
                raise HTTPException(
                    status_code=400,
                    detail="min_spread cannot be greater than max_spread"
                )
        
        # Validate time range
        if start_time and end_time and start_time >= end_time:
            raise HTTPException(
                status_code=400,
                detail="start_time must be before end_time"
            )
        
        # Search rates
        rates = await service.search_rates_by_criteria(
            symbol=symbol.upper() if symbol else None,
            min_spread=min_spread,
            max_spread=max_spread,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        return HistoricalDataResponse(
            symbol=symbol.upper() if symbol else "ALL",
            start_time=start_time,
            end_time=end_time,
            count=len(rates),
            rates=[ForexRateSchema.from_orm(rate) for rate in rates]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=DataStatisticsResponse)
async def get_data_statistics(
    symbol: Optional[str] = Query(None, description="Optional symbol filter"),
    service: ForexPersistenceService = Depends(get_persistence_service)
):
    """
    Get statistics about stored forex data
    
    - **symbol**: Optional symbol to get statistics for specific currency pair
    """
    try:
        stats = await service.get_data_statistics(
            symbol=symbol.upper() if symbol else None
        )
        
        return DataStatisticsResponse(**stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/archive", response_model=ArchivalResponse)
async def archive_old_data(
    days_old: int = Query(90, ge=1, le=3650, description="Archive data older than X days"),
    batch_size: int = Query(1000, ge=100, le=10000, description="Batch size for archival"),
    service: ForexPersistenceService = Depends(get_persistence_service)
):
    """
    Archive old forex data to separate archive table
    
    - **days_old**: Archive data older than this many days (1-3650)
    - **batch_size**: Number of records to process per batch (100-10000)
    
    **Note**: This operation may take a long time for large datasets
    """
    try:
        result = await service.archive_old_data(
            days_old=days_old,
            batch_size=batch_size
        )
        
        return ArchivalResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/archive/cleanup")
async def cleanup_old_archives(
    days_old: int = Query(365, ge=30, le=3650, description="Delete archives older than X days"),
    service: ForexPersistenceService = Depends(get_persistence_service)
):
    """
    Delete archived data older than specified days
    
    - **days_old**: Delete archived data older than this many days (30-3650)
    
    **Warning**: This permanently deletes data and cannot be undone
    """
    try:
        deleted_count = await service.cleanup_old_archives(days_old=days_old)
        
        return {
            "deleted_count": deleted_count,
            "days_old": days_old,
            "deleted_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/integrity/validate", response_model=DataIntegrityResponse)
async def validate_data_integrity(
    service: ForexPersistenceService = Depends(get_persistence_service)
):
    """
    Validate data integrity and return report
    
    Checks for:
    - Negative spreads (ask < bid)
    - Future timestamps
    - Zero or negative prices
    - Unusually large spreads
    """
    try:
        integrity_report = await service.validate_data_integrity()
        
        return DataIntegrityResponse(**integrity_report)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))