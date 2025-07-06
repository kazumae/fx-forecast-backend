from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from app.schemas.base import BaseSchema


class TradeDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class TradeReviewCreate(BaseModel):
    currency_pair: str = Field(..., max_length=10, description="通貨ペア（例：USDJPY）")
    timeframe: str = Field(..., max_length=10, description="時間足（例：5m、1h）")
    trade_direction: Optional[TradeDirection] = Field(None, description="トレード方向")
    additional_context: Optional[str] = Field(None, description="レビューの追加コンテキスト")


class TradeReviewBase(BaseModel):
    currency_pair: str
    timeframe: str
    trade_direction: Optional[str]
    overall_score: float
    entry_analysis: str
    technical_analysis: Optional[str]
    risk_management: Optional[str]
    market_context: Optional[str]
    good_points: List[str]
    improvement_points: List[str]
    recommendations: List[str]
    confidence_level: Optional[float]
    additional_context: Optional[str]


class TradeReviewResponse(TradeReviewBase, BaseSchema):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    images: List[Dict[str, Any]] = []
    comments_count: int = 0
    
    class Config(BaseSchema.Config):
        from_attributes = True


class TradeReviewDetail(TradeReviewResponse):
    raw_analysis: Optional[str]
    comments: List[Dict[str, Any]] = []


class TradeReviewListResponse(BaseModel):
    reviews: List[TradeReviewResponse]
    total: int
    skip: int
    limit: int


class TradeReviewCommentCreate(BaseModel):
    review_id: int = Field(..., description="トレードレビューのID")
    content: str = Field(..., min_length=1, description="コメント内容")
    comment_type: str = Field(..., description="コメントの種類")
    parent_comment_id: Optional[int] = Field(None, description="返信の親コメントID")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="追加メタデータ")


class TradeReviewCommentResponse(BaseSchema):
    id: int
    review_id: int
    parent_comment_id: Optional[int]
    comment_type: str
    content: str
    author: str
    is_ai_response: bool
    extra_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]
    replies: List['TradeReviewCommentResponse'] = []
    # 質問タイプの場合、紐づく回答を含める
    answer: Optional['TradeReviewCommentResponse'] = None
    
    class Config(BaseSchema.Config):
        from_attributes = True




# Update forward references
TradeReviewCommentResponse.model_rebuild()