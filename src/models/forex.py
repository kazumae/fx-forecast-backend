from sqlalchemy import Column, BigInteger, Integer, String, Float, DECIMAL, DateTime, JSON, UniqueConstraint
from sqlalchemy.sql import func
from decimal import Decimal

from src.models.base import Base

class ForexRate(Base):
    __tablename__ = "forex_rates"

    id = Column(BigInteger, primary_key=True, index=True)
    symbol = Column(String(10), index=True, nullable=False)
    bid = Column(DECIMAL(10, 5), nullable=False)
    ask = Column(DECIMAL(10, 5), nullable=False)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Add unique constraint for deduplication
    __table_args__ = (
        UniqueConstraint('symbol', 'timestamp', name='uq_symbol_timestamp'),
    )
    
    @property
    def spread(self) -> Decimal:
        """Calculate bid-ask spread"""
        return self.ask - self.bid
    
    @property
    def mid_price(self) -> Decimal:
        """Calculate mid price"""
        return (self.bid + self.ask) / 2
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'bid': float(self.bid),
            'ask': float(self.ask),
            'spread': float(self.spread),
            'mid_price': float(self.mid_price),
            'timestamp': self.timestamp,
            'created_at': self.created_at
        }
    
    def __repr__(self) -> str:
        return f"<ForexRate(symbol={self.symbol}, bid={self.bid}, ask={self.ask}, timestamp={self.timestamp})>"


class ForexRateArchive(Base):
    __tablename__ = "forex_rates_archive"

    id = Column(BigInteger, primary_key=True, index=True)
    symbol = Column(String(10), index=True, nullable=False)
    bid = Column(DECIMAL(10, 5), nullable=False)
    ask = Column(DECIMAL(10, 5), nullable=False)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    archived_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self) -> str:
        return f"<ForexRateArchive(symbol={self.symbol}, bid={self.bid}, ask={self.ask}, archived_at={self.archived_at})>"

class ForexForecast(Base):
    __tablename__ = "forex_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    currency_pair = Column(String, index=True, nullable=False)
    forecast_date = Column(DateTime(timezone=True), nullable=False)
    predicted_rate = Column(Float, nullable=False)
    confidence_interval = Column(JSON)
    model_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())