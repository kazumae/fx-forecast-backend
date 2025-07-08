from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ForecastRequest(Base):
    __tablename__ = "forecast_requests"

    id = Column(Integer, primary_key=True, index=True)
    currency_pair = Column(String(10), nullable=False)
    prompt = Column(Text, nullable=False)
    response = Column(Text)
    timeframes = Column(JSON)  # Store list of timeframes used
    extra_metadata = Column(JSON)  # Store additional metadata including revision history
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    images = relationship("ForecastImage", back_populates="forecast", cascade="all, delete-orphan")
    reviews = relationship("ForecastReview", back_populates="forecast", cascade="all, delete-orphan")
    comments = relationship("ForecastComment", back_populates="forecast", cascade="all, delete-orphan")


class ForecastImage(Base):
    __tablename__ = "forecast_images"
    
    id = Column(Integer, primary_key=True, index=True)
    forecast_id = Column(Integer, ForeignKey("forecast_requests.id"), nullable=False)
    timeframe = Column(String(10), nullable=False)  # e.g., "1m", "5m", "1h"
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    forecast = relationship("ForecastRequest", back_populates="images")


class ForecastReview(Base):
    __tablename__ = "forecast_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    forecast_id = Column(Integer, ForeignKey("forecast_requests.id"), nullable=False)
    review_timeframes = Column(JSON)  # Timeframes used in the review
    review_prompt = Column(Text, nullable=False)
    review_response = Column(Text, nullable=False)
    actual_outcome = Column(String(50))  # e.g., "long_success", "short_success", "neutral"
    accuracy_notes = Column(Text)
    review_metadata = Column(JSON)  # Extracted metadata for future use
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    forecast = relationship("ForecastRequest", back_populates="reviews")
    review_images = relationship("ForecastReviewImage", back_populates="review", cascade="all, delete-orphan")
    comments = relationship("ForecastReviewComment", back_populates="review", cascade="all, delete-orphan")


class ForecastReviewImage(Base):
    __tablename__ = "forecast_review_images"
    
    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("forecast_reviews.id"), nullable=False)
    timeframe = Column(String(10), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    review = relationship("ForecastReview", back_populates="review_images")


class ForecastComment(Base):
    __tablename__ = "forecast_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    forecast_id = Column(Integer, ForeignKey("forecast_requests.id"), nullable=False)
    parent_comment_id = Column(Integer, ForeignKey("forecast_comments.id"), nullable=True)
    comment_type = Column(String(20), nullable=False)  # "question", "answer", "note"
    content = Column(Text, nullable=False)
    author = Column(String(100), default="User")  # Can be "User" or "AI"
    is_ai_response = Column(Boolean, default=False)
    extra_metadata = Column(JSON)  # Extra data like related chart sections, confidence level, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    forecast = relationship("ForecastRequest", back_populates="comments")
    parent_comment = relationship("ForecastComment", remote_side=[id], backref="replies")


class ForecastReviewComment(Base):
    __tablename__ = "forecast_review_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("forecast_reviews.id"), nullable=False)
    parent_comment_id = Column(Integer, ForeignKey("forecast_review_comments.id"), nullable=True)
    comment_type = Column(String(20), nullable=False)  # "question", "answer", "note"
    content = Column(Text, nullable=False)
    author = Column(String(100), default="User")  # Can be "User" or "AI"
    is_ai_response = Column(Boolean, default=False)
    extra_metadata = Column(JSON)  # Extra data like analysis details, confidence level, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    review = relationship("ForecastReview", back_populates="comments")
    parent_comment = relationship("ForecastReviewComment", remote_side=[id], backref="replies")