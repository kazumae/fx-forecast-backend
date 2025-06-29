"""
Technical Indicator Calculator
ローソク足データから技術指標（EMA）を計算する
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict
from decimal import Decimal
from sqlalchemy.orm import Session

from src.db.redis_manager import RedisManager
from src.models.candlestick import CandlestickData
from src.models.technical_indicator import TechnicalIndicator
from src.repositories.technical_indicator_repository import TechnicalIndicatorRepository


class IndicatorCalculator:
    """Calculate technical indicators from candlestick data"""
    
    # EMA periods
    EMA_PERIODS = [20, 75, 200]
    
    def __init__(
        self,
        db_session: Session,
        redis_manager: RedisManager,
        indicator_repo: TechnicalIndicatorRepository
    ):
        """Initialize indicator calculator
        
        Args:
            db_session: Database session
            redis_manager: Redis manager instance
            indicator_repo: Technical indicator repository
        """
        self.logger = logging.getLogger(__name__)
        self.db_session = db_session
        self.redis_manager = redis_manager
        self.indicator_repo = indicator_repo
    
    def calculate_indicators(self, candle: CandlestickData) -> List[TechnicalIndicator]:
        """Calculate all indicators for a candlestick
        
        Args:
            candle: Candlestick data
            
        Returns:
            List of calculated indicators
        """
        calculated_indicators = []
        
        # Calculate EMAs
        for period in self.EMA_PERIODS:
            indicator = self._calculate_ema(candle, period)
            if indicator:
                calculated_indicators.append(indicator)
        
        return calculated_indicators
    
    def _calculate_ema(self, candle: CandlestickData, period: int) -> Optional[TechnicalIndicator]:
        """Calculate EMA for a specific period
        
        Args:
            candle: Candlestick data
            period: EMA period (20, 75, or 200)
            
        Returns:
            TechnicalIndicator instance or None if not enough data
        """
        try:
            indicator_type = f"ema_{period}"
            
            # Get previous EMA value
            previous_ema = self._get_previous_ema(
                candle.symbol,
                candle.timeframe,
                candle.open_time,
                indicator_type
            )
            
            # Count available candles
            candle_count = self._count_candles(
                candle.symbol,
                candle.timeframe,
                candle.open_time
            )
            
            # Calculate EMA
            if candle_count < period:
                # Not enough data
                self.logger.debug(
                    f"Not enough data for {indicator_type}: "
                    f"{candle_count}/{period} candles"
                )
                return None
            
            elif candle_count == period:
                # First EMA - use SMA
                ema_value = self._calculate_initial_ema(
                    candle.symbol,
                    candle.timeframe,
                    candle.open_time,
                    period
                )
                
            else:
                # Calculate EMA using previous value
                if previous_ema is None:
                    self.logger.warning(
                        f"Missing previous EMA for {indicator_type} "
                        f"at {candle.open_time}"
                    )
                    return None
                
                ema_value = self._calculate_ema_value(
                    candle.close_price,
                    previous_ema,
                    period
                )
            
            if ema_value is None:
                return None
            
            # Create indicator instance
            indicator = TechnicalIndicator(
                symbol=candle.symbol,
                timeframe=candle.timeframe,
                timestamp=candle.open_time,
                indicator_type=indicator_type,
                value=ema_value
            )
            
            # Save to database
            saved = self.indicator_repo.save_indicator(indicator)
            
            if saved:
                # Update Redis cache
                from src.db.redis_manager import TechnicalIndicator as RedisTechnicalIndicator
                redis_indicator = RedisTechnicalIndicator(
                    symbol=candle.symbol,
                    timeframe=candle.timeframe,
                    timestamp=candle.open_time,
                    indicator_type=indicator_type,
                    value=ema_value,
                    metadata=None
                )
                self.redis_manager.set_technical_indicator(redis_indicator)
                
                self.logger.info(
                    f"Calculated {indicator_type} for {candle.symbol} "
                    f"{candle.timeframe}: {ema_value:.6f}"
                )
                
                return saved
            
        except Exception as e:
            self.logger.error(
                f"Failed to calculate {indicator_type} for "
                f"{candle.symbol} {candle.timeframe}: {e}",
                exc_info=True
            )
        
        return None
    
    def _get_previous_ema(
        self,
        symbol: str,
        timeframe: str,
        current_time: datetime,
        indicator_type: str
    ) -> Optional[Decimal]:
        """Get previous EMA value
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            current_time: Current candle time
            indicator_type: Indicator type (e.g., 'ema_20')
            
        Returns:
            Previous EMA value or None
        """
        try:
            # Try Redis first
            cached = self.redis_manager.get_technical_indicator(
                symbol=symbol,
                timeframe=timeframe,
                indicator_type=indicator_type
            )
            
            if cached and cached.get('value') is not None:
                # Verify it's actually previous (not current)
                cached_time = datetime.fromisoformat(cached['timestamp'])
                if cached_time < current_time:
                    return Decimal(str(cached['value']))
            
            # Fall back to database
            previous = self.indicator_repo.get_latest_indicator(
                symbol=symbol,
                timeframe=timeframe,
                indicator_type=indicator_type,
                before_timestamp=current_time
            )
            
            return previous.value if previous else None
            
        except Exception as e:
            self.logger.error(f"Failed to get previous EMA: {e}")
            return None
    
    def _count_candles(
        self,
        symbol: str,
        timeframe: str,
        before_time: datetime
    ) -> int:
        """Count available candles before a specific time
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            before_time: Count candles before this time
            
        Returns:
            Number of candles
        """
        try:
            from src.models.candlestick import CandlestickData
            
            count = self.db_session.query(CandlestickData).filter(
                CandlestickData.symbol == symbol,
                CandlestickData.timeframe == timeframe,
                CandlestickData.open_time <= before_time
            ).count()
            
            return count
            
        except Exception as e:
            self.logger.error(f"Failed to count candles: {e}")
            return 0
    
    def _calculate_initial_ema(
        self,
        symbol: str,
        timeframe: str,
        current_time: datetime,
        period: int
    ) -> Optional[Decimal]:
        """Calculate initial EMA using SMA
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            current_time: Current time
            period: EMA period
            
        Returns:
            Initial EMA value (SMA) or None
        """
        try:
            from src.models.candlestick import CandlestickData
            
            # Get last N candles
            candles = self.db_session.query(CandlestickData).filter(
                CandlestickData.symbol == symbol,
                CandlestickData.timeframe == timeframe,
                CandlestickData.open_time <= current_time
            ).order_by(
                CandlestickData.open_time.desc()
            ).limit(period).all()
            
            if len(candles) < period:
                return None
            
            # Calculate SMA
            sma = sum(c.close_price for c in candles) / period
            
            return sma
            
        except Exception as e:
            self.logger.error(f"Failed to calculate initial EMA: {e}")
            return None
    
    def _calculate_ema_value(
        self,
        current_price: Decimal,
        previous_ema: Decimal,
        period: int
    ) -> Decimal:
        """Calculate EMA using the standard formula
        
        Args:
            current_price: Current closing price
            previous_ema: Previous EMA value
            period: EMA period
            
        Returns:
            Calculated EMA value
        """
        # EMA = (Price - Previous_EMA) × (2 / (Period + 1)) + Previous_EMA
        multiplier = Decimal(2) / (period + 1)
        ema = (current_price - previous_ema) * multiplier + previous_ema
        
        return ema.quantize(Decimal('0.000001'))  # 6 decimal places
    
    def backfill_indicators(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Backfill indicators for historical data
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_time: Start time (optional)
            end_time: End time (optional)
            
        Returns:
            Dictionary with count of indicators created per type
        """
        try:
            from src.models.candlestick import CandlestickData
            
            # Get candles to process
            query = self.db_session.query(CandlestickData).filter(
                CandlestickData.symbol == symbol,
                CandlestickData.timeframe == timeframe
            )
            
            if start_time:
                query = query.filter(CandlestickData.open_time >= start_time)
            if end_time:
                query = query.filter(CandlestickData.open_time <= end_time)
            
            candles = query.order_by(CandlestickData.open_time).all()
            
            # Calculate indicators for each candle
            indicator_counts = {f"ema_{p}": 0 for p in self.EMA_PERIODS}
            
            for candle in candles:
                indicators = self.calculate_indicators(candle)
                for indicator in indicators:
                    if indicator.indicator_type in indicator_counts:
                        indicator_counts[indicator.indicator_type] += 1
            
            self.logger.info(
                f"Backfilled indicators for {symbol} {timeframe}: "
                f"{indicator_counts}"
            )
            
            return indicator_counts
            
        except Exception as e:
            self.logger.error(f"Failed to backfill indicators: {e}", exc_info=True)
            return {}