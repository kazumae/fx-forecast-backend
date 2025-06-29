"""
Pattern domain models for entry point judgment
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional, Any, List


class PatternType(str, Enum):
    """Types of detectable patterns"""
    V_SHAPE_REVERSAL = "V_SHAPE_REVERSAL"
    EMA_SQUEEZE = "EMA_SQUEEZE"
    TREND_CONTINUATION = "TREND_CONTINUATION"
    FALSE_BREAKOUT = "FALSE_BREAKOUT"


@dataclass
class PatternSignal:
    """Detected pattern signal"""
    id: Optional[str]
    symbol: str
    timeframe: str
    pattern_type: PatternType
    detected_at: datetime
    price_level: Decimal
    confidence: float  # 0-100
    parameters: Dict[str, Any]
    zone_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate confidence range"""
        if not 0 <= self.confidence <= 100:
            raise ValueError(f"Confidence must be between 0 and 100, got {self.confidence}")
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high confidence signal"""
        return self.confidence >= 80
    
    @property
    def description(self) -> str:
        """Get human-readable description"""
        return f"{self.pattern_type.value} @ {self.price_level} ({self.confidence:.1f}% confidence)"


class PatternStrength(Enum):
    """パターン強度"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"