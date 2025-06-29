"""
Zone model for support/resistance areas
"""
from sqlalchemy import Column, String, DECIMAL, Integer, Boolean, CHAR, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from decimal import Decimal
from typing import List, Optional

from src.models.base import Base


class Zone(Base):
    """Zone (horizontal price area) model"""
    __tablename__ = "zones"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    symbol = Column(String(10), nullable=False)
    timeframe = Column(String(5), nullable=False)
    upper_bound = Column(DECIMAL(10, 5), nullable=False)
    lower_bound = Column(DECIMAL(10, 5), nullable=False)
    strength = Column(CHAR(1), nullable=False)  # S, A, B
    touch_count = Column(Integer, default=0)
    last_touch_time = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    zone_metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    @property
    def width(self) -> Decimal:
        """Calculate zone width in pips"""
        return self.upper_bound - self.lower_bound
    
    @property
    def role_history(self) -> List[str]:
        """Get role reversal history from metadata"""
        if self.zone_metadata and 'role_history' in self.zone_metadata:
            return self.zone_metadata['role_history']
        return []
    
    def contains_price(self, price: Decimal) -> bool:
        """Check if a price is within this zone"""
        return self.lower_bound <= price <= self.upper_bound
    
    def distance_to_price(self, price: Decimal) -> Decimal:
        """Calculate minimum distance from price to zone"""
        if self.contains_price(price):
            return Decimal('0')
        
        if price < self.lower_bound:
            return self.lower_bound - price
        else:
            return price - self.upper_bound
    
    def __repr__(self):
        return (
            f"<Zone {self.symbol} {self.timeframe} "
            f"[{self.lower_bound}-{self.upper_bound}] "
            f"strength={self.strength}>"
        )