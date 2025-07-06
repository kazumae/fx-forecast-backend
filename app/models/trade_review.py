from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class TradeReview(Base):
    __tablename__ = "trade_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    currency_pair = Column(String(10), nullable=False)
    timeframe = Column(String(10), nullable=False)
    trade_direction = Column(String(10))  # "long", "short", or null
    
    # Review scores and analysis
    overall_score = Column(Float, nullable=False)
    entry_analysis = Column(Text, nullable=False)
    technical_analysis = Column(Text)
    risk_management = Column(Text)
    market_context = Column(Text)
    
    # Structured feedback
    good_points = Column(JSON)  # List of good points
    improvement_points = Column(JSON)  # List of improvement areas
    recommendations = Column(JSON)  # List of recommendations
    
    # Metadata
    confidence_level = Column(Float)
    raw_analysis = Column(Text)  # Full AI response
    additional_context = Column(Text)  # User-provided context
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    images = relationship("TradeReviewImage", back_populates="review", cascade="all, delete-orphan")
    comments = relationship("TradeReviewComment", back_populates="review", cascade="all, delete-orphan")


class TradeReviewImage(Base):
    __tablename__ = "trade_review_images"
    
    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("trade_reviews.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(50))
    image_type = Column(String(20))  # "chart", "result", etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    review = relationship("TradeReview", back_populates="images")


class TradeReviewComment(Base):
    __tablename__ = "trade_review_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("trade_reviews.id"), nullable=False)
    parent_comment_id = Column(Integer, ForeignKey("trade_review_comments.id"), nullable=True)
    comment_type = Column(String(20), nullable=False)  # "question", "answer", "note", "feedback"
    content = Column(Text, nullable=False)
    author = Column(String(100), default="User")
    is_ai_response = Column(Boolean, default=False)
    extra_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    review = relationship("TradeReview", back_populates="comments")
    parent_comment = relationship("TradeReviewComment", remote_side=[id], backref="replies")