"""
Candlestick Generator
リアルタイムティックデータからローソク足を生成する
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from decimal import Decimal
from sqlalchemy.orm import Session

from src.db.redis_manager import RedisManager
from src.models.tick_data import TickData
from src.models.candlestick import CandlestickData
from src.repositories.candlestick_repository import CandlestickRepository


class CandlestickGenerator:
    """Generate candlesticks from tick data"""
    
    # Timeframe definitions (in minutes)
    TIMEFRAME_MINUTES = {
        '1m': 1,
        '15m': 15,
        '1h': 60,
        '4h': 240,
        '1d': 1440
    }
    
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        db_session: Session,
        redis_manager: RedisManager,
        candle_repo: CandlestickRepository,
        indicator_repo=None
    ):
        """Initialize candlestick generator
        
        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            timeframe: Timeframe ('1m', '15m', '1h', '4h')
            db_session: Database session
            redis_manager: Redis manager instance
            candle_repo: Candlestick repository
            indicator_repo: Technical indicator repository (optional)
        """
        self.logger = logging.getLogger(f"{__name__}.{symbol}.{timeframe}")
        self.symbol = symbol
        self.timeframe = timeframe
        self.db_session = db_session
        self.redis_manager = redis_manager
        self.candle_repo = candle_repo
        self.indicator_repo = indicator_repo
        
        # Timeframe in minutes
        self.minutes = self.TIMEFRAME_MINUTES.get(timeframe)
        if not self.minutes:
            raise ValueError(f"Invalid timeframe: {timeframe}")
        
        # Current candle being built
        self.current_candle: Optional[Dict] = None
        self._load_current_candle()
    
    def _load_current_candle(self):
        """Load current candle from Redis"""
        try:
            key = f"candle:{self.symbol}:{self.timeframe}:current"
            self.current_candle = self.redis_manager.redis_client.hgetall(key)
            
            if self.current_candle:
                # Convert Redis strings to appropriate types
                self.current_candle = {
                    'open_time': datetime.fromisoformat(self.current_candle['open_time']),
                    'open_price': Decimal(self.current_candle['open_price']),
                    'high_price': Decimal(self.current_candle['high_price']),
                    'low_price': Decimal(self.current_candle['low_price']),
                    'close_price': Decimal(self.current_candle['close_price']),
                    'tick_count': int(self.current_candle['tick_count'])
                }
                self.logger.debug(f"Loaded current candle from Redis: {self.current_candle['open_time']}")
                
        except Exception as e:
            self.logger.warning(f"Failed to load current candle from Redis: {e}")
            self.current_candle = None
    
    def update(self, tick: TickData) -> List[CandlestickData]:
        """Update candlestick with new tick data
        
        Args:
            tick: New tick data
            
        Returns:
            List of finalized candlesticks (empty if none finalized)
        """
        finalized_candles = []
        
        # Get candle period for this tick
        candle_time = self._get_candle_time(tick.timestamp)
        
        # Check if we need to finalize current candle
        if self.current_candle and self.current_candle['open_time'] != candle_time:
            # Finalize current candle
            finalized = self._finalize_candle()
            if finalized:
                finalized_candles.append(finalized)
            
            # Start new candle
            self._start_new_candle(tick, candle_time)
        
        elif not self.current_candle:
            # No current candle, start new one
            self._start_new_candle(tick, candle_time)
        
        else:
            # Update current candle
            self._update_current_candle(tick)
        
        return finalized_candles
    
    def _get_candle_time(self, timestamp: datetime) -> datetime:
        """Get the candle period start time for a given timestamp
        
        Args:
            timestamp: Tick timestamp
            
        Returns:
            Candle period start time
        """
        # Ensure UTC timezone
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        # Calculate period start based on timeframe
        if self.timeframe == '1m':
            # Round down to minute
            return timestamp.replace(second=0, microsecond=0)
        
        elif self.timeframe == '15m':
            # Round down to 15-minute interval
            minute = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        
        elif self.timeframe == '1h':
            # Round down to hour
            return timestamp.replace(minute=0, second=0, microsecond=0)
        
        elif self.timeframe == '4h':
            # Round down to 4-hour interval
            hour = (timestamp.hour // 4) * 4
            return timestamp.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        elif self.timeframe == '1d':
            # Round down to day (UTC)
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        
        else:
            raise ValueError(f"Unsupported timeframe: {self.timeframe}")
    
    def _start_new_candle(self, tick: TickData, open_time: datetime):
        """Start a new candle
        
        Args:
            tick: First tick of the new candle
            open_time: Candle open time
        """
        # Use average of bid/ask as price
        price = (tick.bid + tick.ask) / 2
        
        self.current_candle = {
            'open_time': open_time,
            'open_price': price,
            'high_price': price,
            'low_price': price,
            'close_price': price,
            'tick_count': 1
        }
        
        # Save to Redis
        self._save_current_to_redis()
        
        self.logger.debug(f"Started new {self.timeframe} candle at {open_time}")
    
    def _update_current_candle(self, tick: TickData):
        """Update current candle with new tick
        
        Args:
            tick: New tick data
        """
        if not self.current_candle:
            return
        
        # Use average of bid/ask as price
        price = (tick.bid + tick.ask) / 2
        
        # Update OHLC
        self.current_candle['high_price'] = max(self.current_candle['high_price'], price)
        self.current_candle['low_price'] = min(self.current_candle['low_price'], price)
        self.current_candle['close_price'] = price
        self.current_candle['tick_count'] += 1
        
        # Save to Redis
        self._save_current_to_redis()
    
    def _save_current_to_redis(self):
        """Save current candle to Redis"""
        if not self.current_candle:
            return
        
        try:
            key = f"candle:{self.symbol}:{self.timeframe}:current"
            
            # Convert to Redis-compatible format
            redis_data = {
                'open_time': self.current_candle['open_time'].isoformat(),
                'open_price': str(self.current_candle['open_price']),
                'high_price': str(self.current_candle['high_price']),
                'low_price': str(self.current_candle['low_price']),
                'close_price': str(self.current_candle['close_price']),
                'tick_count': str(self.current_candle['tick_count'])
            }
            
            # Save with expiration (2x timeframe duration)
            expire_seconds = self.minutes * 60 * 2
            self.redis_manager.redis_client.hset(key, mapping=redis_data)
            self.redis_manager.redis_client.expire(key, expire_seconds)
            
        except Exception as e:
            self.logger.error(f"Failed to save current candle to Redis: {e}")
    
    def _finalize_candle(self) -> Optional[CandlestickData]:
        """Finalize current candle and save to database
        
        Returns:
            Finalized candlestick data or None if failed
        """
        if not self.current_candle:
            return None
        
        try:
            # Calculate close time
            close_time = self.current_candle['open_time'] + timedelta(minutes=self.minutes) - timedelta(seconds=1)
            
            # Create CandlestickData instance
            candle = CandlestickData(
                symbol=self.symbol,
                timeframe=self.timeframe,
                open_time=self.current_candle['open_time'],
                close_time=close_time,
                open_price=self.current_candle['open_price'],
                high_price=self.current_candle['high_price'],
                low_price=self.current_candle['low_price'],
                close_price=self.current_candle['close_price'],
                tick_count=self.current_candle['tick_count']
            )
            
            # Save to database using repository
            saved_candle = self.candle_repo.upsert(candle)
            
            if saved_candle:
                # Update Redis with latest candle
                self.redis_manager.cache_candlestick(
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    candle_data={
                        'open_time': saved_candle.open_time.isoformat(),
                        'close_time': saved_candle.close_time.isoformat(),
                        'open': float(saved_candle.open_price),
                        'high': float(saved_candle.high_price),
                        'low': float(saved_candle.low_price),
                        'close': float(saved_candle.close_price),
                        'tick_count': saved_candle.tick_count
                    }
                )
                
                # Clear current candle from Redis
                key = f"candle:{self.symbol}:{self.timeframe}:current"
                self.redis_manager.redis_client.delete(key)
                
                self.logger.info(
                    f"Finalized {self.timeframe} candle: "
                    f"O={saved_candle.open_price} H={saved_candle.high_price} "
                    f"L={saved_candle.low_price} C={saved_candle.close_price} "
                    f"Ticks={saved_candle.tick_count}"
                )
                
                # Trigger aggregation to higher timeframes
                self._trigger_aggregation(saved_candle)
                
                return saved_candle
            
        except Exception as e:
            self.logger.error(f"Failed to finalize candle: {e}", exc_info=True)
        
        finally:
            # Clear current candle
            self.current_candle = None
        
        return None
    
    def _trigger_aggregation(self, candle: CandlestickData):
        """Trigger aggregation to higher timeframes
        
        Args:
            candle: Finalized candlestick
        """
        # Only aggregate from 1m candles
        if self.timeframe != '1m':
            return
        
        # Define target timeframes
        target_timeframes = ['15m', '1h', '4h']
        
        for target_tf in target_timeframes:
            try:
                # Check if this candle completes a period for the target timeframe
                if self._is_timeframe_boundary(candle.close_time, target_tf):
                    self._aggregate_to_timeframe(candle.close_time, target_tf)
                    
            except Exception as e:
                self.logger.error(f"Failed to aggregate to {target_tf}: {e}")
    
    def _is_timeframe_boundary(self, timestamp: datetime, timeframe: str) -> bool:
        """Check if timestamp is at a timeframe boundary
        
        Args:
            timestamp: Time to check
            timeframe: Target timeframe
            
        Returns:
            True if at boundary
        """
        # Add 1 second to check if we just completed a period
        next_second = timestamp + timedelta(seconds=1)
        
        if timeframe == '15m':
            return next_second.minute % 15 == 0
        elif timeframe == '1h':
            return next_second.minute == 0
        elif timeframe == '4h':
            return next_second.hour % 4 == 0 and next_second.minute == 0
        
        return False
    
    def _aggregate_to_timeframe(self, end_time: datetime, target_timeframe: str):
        """Aggregate 1m candles to a higher timeframe
        
        Args:
            end_time: End time of the period
            target_timeframe: Target timeframe ('15m', '1h', '4h')
        """
        # Calculate period boundaries
        minutes = self.TIMEFRAME_MINUTES[target_timeframe]
        
        # End time is already at second :59, add 1 second to get clean boundary
        period_end = end_time + timedelta(seconds=1)
        period_start = period_end - timedelta(minutes=minutes)
        
        # Fetch 1m candles for this period
        source_candles = self.candle_repo.get_candlesticks(
            symbol=self.symbol,
            timeframe='1m',
            start_time=period_start,
            end_time=end_time
        )
        
        if not source_candles:
            self.logger.warning(
                f"No 1m candles found for {target_timeframe} aggregation "
                f"from {period_start} to {end_time}"
            )
            return
        
        # Check if we have complete data
        expected_candles = minutes
        if len(source_candles) < expected_candles:
            self.logger.warning(
                f"Incomplete data for {target_timeframe}: "
                f"expected {expected_candles}, got {len(source_candles)}"
            )
            # Continue anyway with available data
        
        # Sort by open_time to ensure correct order
        source_candles.sort(key=lambda x: x.open_time)
        
        # Create aggregated candle
        aggregated_candle = CandlestickData(
            symbol=self.symbol,
            timeframe=target_timeframe,
            open_time=period_start,
            close_time=period_end - timedelta(seconds=1),
            open_price=source_candles[0].open_price,
            high_price=max(c.high_price for c in source_candles),
            low_price=min(c.low_price for c in source_candles),
            close_price=source_candles[-1].close_price,
            tick_count=sum(c.tick_count for c in source_candles)
        )
        
        # Save to database
        saved_candle = self.candle_repo.upsert(aggregated_candle)
        
        if saved_candle:
            # Update Redis cache
            self.redis_manager.cache_candlestick(
                symbol=self.symbol,
                timeframe=target_timeframe,
                candle_data={
                    'open_time': saved_candle.open_time.isoformat(),
                    'close_time': saved_candle.close_time.isoformat(),
                    'open': float(saved_candle.open_price),
                    'high': float(saved_candle.high_price),
                    'low': float(saved_candle.low_price),
                    'close': float(saved_candle.close_price),
                    'tick_count': saved_candle.tick_count
                }
            )
            
            self.logger.info(
                f"Aggregated {len(source_candles)} 1m candles to {target_timeframe}: "
                f"O={saved_candle.open_price} H={saved_candle.high_price} "
                f"L={saved_candle.low_price} C={saved_candle.close_price} "
                f"Ticks={saved_candle.tick_count}"
            )
            
            # Trigger indicator calculation for the new candle
            if self.indicator_repo:
                from .indicator_calculator import IndicatorCalculator
                
                indicator_calc = IndicatorCalculator(
                    symbol=self.symbol,
                    timeframe=target_timeframe,
                    db_session=self.db_session,
                    redis_manager=self.redis_manager,
                    candle_repo=self.candle_repo,
                    indicator_repo=self.indicator_repo
                )
                
                indicator_calc.calculate_for_candle(saved_candle)