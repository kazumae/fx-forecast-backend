"""
Base class for pattern detectors
"""
from abc import ABC, abstractmethod
from typing import List, Optional
import logging

from src.domain.models.pattern import PatternSignal
from src.domain.models.market import MarketContext


class BasePatternDetector(ABC):
    """Abstract base class for all pattern detectors"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def detect(self, context: MarketContext) -> List[PatternSignal]:
        """
        Detect patterns in the given market context
        
        Args:
            context: Current market context with candles, indicators, zones
            
        Returns:
            List of detected pattern signals
        """
        pass
    
    def _log_detection(self, pattern: Optional[PatternSignal], context: MarketContext) -> None:
        """Log pattern detection result"""
        if pattern:
            self.logger.info(
                f"Pattern detected: {pattern.pattern_type.value} "
                f"for {context.symbol} at {pattern.price_level} "
                f"with {pattern.confidence:.1f}% confidence"
            )
        else:
            self.logger.debug(
                f"No pattern detected for {context.symbol} "
                f"at {context.timestamp}"
            )