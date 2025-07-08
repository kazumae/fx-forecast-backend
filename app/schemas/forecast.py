"""Schemas for forecast history"""
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Dict, Any
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


# Review Comment Schemas
class ReviewCommentBase(BaseSchema):
    comment_type: str  # "question", "answer", "note"
    content: str
    parent_comment_id: Optional[int] = None


class ReviewCommentCreate(ReviewCommentBase):
    pass


class ReviewCommentUpdate(BaseSchema):
    content: Optional[str] = None


class ReviewCommentResponse(ReviewCommentBase):
    id: int
    review_id: int
    author: str
    is_ai_response: bool
    extra_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    replies: List['ReviewCommentResponse'] = []

    class Config(BaseSchema.Config):
        from_attributes = True


# Update ReviewCommentResponse model to allow forward references
ReviewCommentResponse.model_rebuild()