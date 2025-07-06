"""Schemas for forecast history"""
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from app.schemas.base import BaseSchema


class ForecastImageResponse(BaseSchema):
    id: int
    timeframe: str
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    created_at: datetime
    url: Optional[str] = None
    
    class Config(BaseSchema.Config):
        from_attributes = True


class ForecastHistoryItem(BaseSchema):
    id: int
    currency_pair: str
    prompt: str
    response: str
    timeframes: Optional[List[str]]
    created_at: datetime
    updated_at: Optional[datetime]
    images: List[ForecastImageResponse]
    
    class Config(BaseSchema.Config):
        from_attributes = True


class ForecastHistoryResponse(BaseModel):
    items: List[ForecastHistoryItem]
    total: int
    page: int
    per_page: int
    total_pages: int