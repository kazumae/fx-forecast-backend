"""
Enhanced Data Processor with Database Storage
リアルタイムデータをTimescaleDBに保存し、ローソク足生成と技術指標計算を行う
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.db.session import SessionLocal
from src.db.redis_manager import RedisManager
from src.models.tick_data import TickData
from src.models.candlestick import CandlestickData
from src.models.technical_indicator import TechnicalIndicator
from src.repositories.candlestick_repository import CandlestickRepository
from src.repositories.technical_indicator_repository import TechnicalIndicatorRepository
from .data_processor import DataProcessor


class DataProcessorDB(DataProcessor):
    """Enhanced data processor with database storage capabilities"""
    
    def __init__(self, redis_url: str = "redis://localhost:6380", max_buffer_size: int = 1000):
        """Initialize data processor with DB support
        
        Args:
            redis_url: Redis connection URL
            max_buffer_size: Maximum size of price data buffer
        """
        super().__init__(max_buffer_size)
        
        # Database session
        self.db_session: Optional[Session] = None
        
        # Redis manager
        # Parse Redis URL to get host and port
        from urllib.parse import urlparse
        parsed_url = urlparse(redis_url)
        redis_host = parsed_url.hostname or 'localhost'
        redis_port = parsed_url.port or 6379
        
        self.redis_manager = RedisManager(host=redis_host, port=redis_port)
        
        # Repositories
        self.candle_repo: Optional[CandlestickRepository] = None
        self.indicator_repo: Optional[TechnicalIndicatorRepository] = None
        
        # Candlestick generators for each timeframe
        self.candle_generators = {}
        
        # Initialize components
        self._initialize_components()
        
    def _initialize_components(self):
        """Initialize database components"""
        try:
            # Create database session
            self.db_session = SessionLocal()
            
            # Initialize repositories
            self.candle_repo = CandlestickRepository(self.db_session)
            self.indicator_repo = TechnicalIndicatorRepository(self.db_session)
            
            # Test database connection
            from sqlalchemy import text
            self.db_session.execute(text("SELECT 1"))
            self.logger.info("Database connection established")
            
            # Test Redis connection
            self.redis_manager.redis_client.ping()
            self.logger.info("Redis connection established")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise
    
    def process_price_data(self, data: dict):
        """Process price data with database storage
        
        Args:
            data: Price data dictionary with symbol, bid, ask, timestamp
        """
        # First, display to console using parent method
        super().process_price_data(data)
        
        # Then, save to database
        try:
            tick = self._save_tick_data(data)
            if tick:
                # Update candlesticks
                self._update_candlesticks(tick)
                
                # Update Redis cache
                self._update_redis_cache(tick)
                
        except Exception as e:
            self.logger.error(f"Error saving data to database: {e}", exc_info=True)
    
    def _save_tick_data(self, data: dict) -> Optional[TickData]:
        """Save tick data to TimescaleDB
        
        Args:
            data: Price data dictionary
            
        Returns:
            TickData instance if saved successfully
        """
        try:
            symbol = data.get("symbol")
            bid = data.get("bid")
            ask = data.get("ask")
            timestamp = data.get("timestamp")
            
            # Convert timestamp to datetime with timezone
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            
            # Create TickData instance
            tick = TickData(
                symbol=symbol,
                timestamp=dt,
                bid=Decimal(str(bid)),
                ask=Decimal(str(ask)),
                source='tradermade'
            )
            
            # Use UPSERT pattern for composite primary key
            existing = self.db_session.query(TickData).filter(
                TickData.symbol == symbol,
                TickData.timestamp == dt
            ).first()
            
            if existing:
                # Update existing record
                existing.bid = tick.bid
                existing.ask = tick.ask
                existing.source = tick.source
                tick = existing
            else:
                # Add new record
                self.db_session.add(tick)
            
            # Commit transaction
            self.db_session.commit()
            
            self.logger.debug(f"Saved tick data: {symbol} at {dt}")
            return tick
            
        except IntegrityError:
            # Handle race condition for concurrent inserts
            self.db_session.rollback()
            self.logger.warning(f"Duplicate tick data for {symbol} at {timestamp}")
            return None
            
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(f"Failed to save tick data: {e}")
            raise
    
    def _update_candlesticks(self, tick: TickData):
        """Update candlesticks for all timeframes
        
        Args:
            tick: TickData instance
        """
        # Only update 1m candlesticks directly from ticks
        # Higher timeframes will be aggregated from 1m candles
        try:
            # Get or create candlestick generator for 1m timeframe
            key = f"{tick.symbol}:1m"
            if key not in self.candle_generators:
                from .candlestick_generator import CandlestickGenerator
                self.candle_generators[key] = CandlestickGenerator(
                    symbol=tick.symbol,
                    timeframe='1m',
                    db_session=self.db_session,
                    redis_manager=self.redis_manager,
                    candle_repo=self.candle_repo,
                    indicator_repo=self.indicator_repo
                )
            
            # Update 1m candlestick
            generator = self.candle_generators[key]
            finalized_candles = generator.update(tick)
            
            # If 1m candles were finalized, calculate indicators
            # The generator will automatically trigger aggregation to higher timeframes
            if finalized_candles:
                self._calculate_indicators(finalized_candles)
                
        except Exception as e:
            self.logger.error(f"Failed to update 1m candlestick: {e}")
    
    def _calculate_indicators(self, candles: List[CandlestickData]):
        """Calculate technical indicators for finalized candles
        
        Args:
            candles: List of finalized candlestick data
        """
        for candle in candles:
            try:
                from .indicator_calculator import IndicatorCalculator
                
                calculator = IndicatorCalculator(
                    db_session=self.db_session,
                    redis_manager=self.redis_manager,
                    indicator_repo=self.indicator_repo
                )
                
                # Calculate EMA indicators
                calculator.calculate_indicators(candle)
                
            except Exception as e:
                self.logger.error(
                    f"Failed to calculate indicators for {candle.symbol} "
                    f"{candle.timeframe}: {e}"
                )
    
    def _update_redis_cache(self, tick: TickData):
        """Update Redis cache with latest tick data
        
        Args:
            tick: TickData instance
        """
        try:
            # Use the RedisClient's set_latest_tick method
            from src.db.redis_manager import TickData as RedisTickData
            
            redis_tick = RedisTickData(
                symbol=tick.symbol,
                timestamp=tick.timestamp,
                bid=tick.bid,
                ask=tick.ask,
                spread=tick.spread if hasattr(tick, 'spread') and tick.spread else tick.ask - tick.bid,
                source=tick.source if hasattr(tick, 'source') else 'tradermade'
            )
            
            # Cache latest tick
            self.redis_manager.set_latest_tick(redis_tick)
            
            # Update tick history (last 100 ticks)
            history_key = f"tick:{tick.symbol}:history"
            tick_json = {
                "timestamp": tick.timestamp.isoformat(),
                "bid": str(tick.bid),
                "ask": str(tick.ask),
                "spread": str(tick.spread) if hasattr(tick, 'spread') and tick.spread else str(tick.ask - tick.bid)
            }
            
            # Use Redis list for history (FIFO)
            import json
            self.redis_manager.redis_client.lpush(history_key, json.dumps(tick_json))
            self.redis_manager.redis_client.ltrim(history_key, 0, 99)  # Keep last 100
            
        except Exception as e:
            self.logger.error(f"Failed to update Redis cache: {e}")
            # Don't raise - cache is best effort
    
    def close(self):
        """Clean up resources"""
        try:
            if self.db_session:
                self.db_session.close()
                self.logger.info("Database session closed")
                
            if self.redis_manager:
                self.redis_manager.close()
                self.logger.info("Redis connection closed")
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()