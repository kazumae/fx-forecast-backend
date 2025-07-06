"""Schemas for forecast review/feedback"""
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from .forecast import ForecastImageResponse
from app.schemas.base import BaseSchema


class ReviewImageResponse(BaseSchema):
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


class ReviewRequest(BaseModel):
    """Request model for creating a review"""
    actual_outcome: Optional[str] = None  # "long_success", "short_success", "neutral", etc.
    accuracy_notes: Optional[str] = None


class ReviewResponse(BaseSchema):
    """Response model for a review"""
    id: int
    forecast_id: int
    review_timeframes: List[str]
    review_prompt: str
    review_response: str
    actual_outcome: Optional[str]
    accuracy_notes: Optional[str]
    review_metadata: Optional[dict]
    created_at: datetime
    review_images: List[ReviewImageResponse]
    
    class Config(BaseSchema.Config):
        from_attributes = True


class ForecastWithReviewsResponse(BaseSchema):
    """Forecast with all its reviews"""
    id: int
    currency_pair: str
    prompt: str
    response: str
    timeframes: Optional[List[str]]
    created_at: datetime
    updated_at: Optional[datetime]
    images: List[ForecastImageResponse]
    reviews: List[ReviewResponse]
    
    class Config(BaseSchema.Config):
        from_attributes = True