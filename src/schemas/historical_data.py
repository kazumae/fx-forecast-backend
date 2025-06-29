"""
Pydantic schemas for historical data API endpoints
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ForexRateSchema(BaseModel):
    """Schema for forex rate data"""
    id: int
    symbol: str = Field(..., description="Currency pair symbol")
    bid: Decimal = Field(..., description="Bid price")
    ask: Decimal = Field(..., description="Ask price")
    spread: Decimal = Field(..., description="Bid-ask spread")
    mid_price: Decimal = Field(..., description="Mid price (bid+ask)/2")
    timestamp: datetime = Field(..., description="Data timestamp")
    created_at: datetime = Field(..., description="Record creation timestamp")

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }


class HistoricalDataResponse(BaseModel):
    """Response schema for historical data queries"""
    symbol: str = Field(..., description="Currency pair symbol or 'ALL' for multi-symbol queries")
    start_time: Optional[datetime] = Field(None, description="Query start time")
    end_time: Optional[datetime] = Field(None, description="Query end time")
    count: int = Field(..., description="Number of records returned")
    rates: List[ForexRateSchema] = Field(..., description="Forex rate data")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class DataStatisticsResponse(BaseModel):
    """Response schema for data statistics"""
    total_records: int = Field(..., description="Total number of records")
    symbols: List[str] = Field(..., description="Available currency pair symbols")
    symbols_count: int = Field(..., description="Number of unique symbols")
    date_range: Optional[Dict[str, str]] = Field(None, description="Date range of data")
    latest_update: Optional[str] = Field(None, description="Timestamp of latest update")


class ArchivalResponse(BaseModel):
    """Response schema for data archival operations"""
    archived: int = Field(..., description="Number of records archived")
    total_found: int = Field(..., description="Total records found for archival")
    cutoff_date: str = Field(..., description="Cutoff date for archival")


class DataIntegrityResponse(BaseModel):
    """Response schema for data integrity validation"""
    total_issues: int = Field(..., description="Total number of issues found")
    issues: List[str] = Field(..., description="List of integrity issues")
    validated_at: str = Field(..., description="Validation timestamp")


class PersistenceStatsSchema(BaseModel):
    """Schema for persistence operation statistics"""
    saved: int = Field(..., description="Number of records successfully saved")
    duplicates: int = Field(..., description="Number of duplicate records skipped")
    errors: int = Field(..., description="Number of errors encountered")


class BulkSaveRequest(BaseModel):
    """Request schema for bulk save operations"""
    rates: List[Dict[str, Any]] = Field(..., description="List of forex rate data to save")
    
    class Config:
        schema_extra = {
            "example": {
                "rates": [
                    {
                        "symbol": "XAUUSD",
                        "bid": 2034.50,
                        "ask": 2034.80,
                        "timestamp": "2024-06-29T10:30:00Z"
                    },
                    {
                        "symbol": "EURUSD",
                        "bid": 1.0735,
                        "ask": 1.0737,
                        "timestamp": "2024-06-29T10:30:01Z"
                    }
                ]
            }
        }


class BulkSaveResponse(BaseModel):
    """Response schema for bulk save operations"""
    statistics: PersistenceStatsSchema = Field(..., description="Save operation statistics")
    processed_at: str = Field(..., description="Processing timestamp")


# Request schemas for data queries
class HistoricalDataRequest(BaseModel):
    """Request schema for historical data queries"""
    symbol: str = Field(..., description="Currency pair symbol")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter") 
    limit: int = Field(1000, ge=1, le=10000, description="Maximum records to return")


class AdvancedSearchRequest(BaseModel):
    """Request schema for advanced search queries"""
    symbol: Optional[str] = Field(None, description="Currency pair symbol")
    min_spread: Optional[float] = Field(None, ge=0, description="Minimum spread filter")
    max_spread: Optional[float] = Field(None, ge=0, description="Maximum spread filter")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")
    limit: int = Field(100, ge=1, le=1000, description="Maximum records to return")


class ArchivalRequest(BaseModel):
    """Request schema for data archival"""
    days_old: int = Field(90, ge=1, le=3650, description="Archive data older than X days")
    batch_size: int = Field(1000, ge=100, le=10000, description="Batch size for processing")


class CleanupRequest(BaseModel):
    """Request schema for archive cleanup"""
    days_old: int = Field(365, ge=30, le=3650, description="Delete archives older than X days")