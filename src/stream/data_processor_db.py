"""
Data Processor with Database Storage for TraderMade Stream
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import redis
import json
import os

from src.models.forex import ForexRate
from src.core.config import settings
from src.stream.candlestick_generator import CandlestickGenerator
from src.stream.indicator_calculator import IndicatorCalculator


class DataProcessorDB:
    """Process and store price data to database"""
    
    def __init__(self):
        """Initialize data processor with database connection"""
        self.logger = logging.getLogger(__name__)
        
        # Database setup (sync for forex_rates)
        self.engine = create_engine(settings.DATABASE_URL)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Async database setup (for candlestick and indicators)
        self.async_engine = create_async_engine(settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'))
        self.AsyncSessionLocal = async_sessionmaker(
            bind=self.async_engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
        
        # Initialize processors
        self.candlestick_generator = None
        self.indicator_calculator = None
        self._init_processors_task = None
        self._candlestick_lock = asyncio.Lock()
        
        # Redis setup
        try:
            self.redis_client = redis.from_url(
                os.getenv("REDIS_URL", "redis://redis:6379"),
                decode_responses=True
            )
            self.redis_client.ping()
            self.redis_enabled = True
            self.logger.info("Redis connection established")
        except Exception as e:
            self.logger.warning(f"Redis connection failed: {e}. Running without cache.")
            self.redis_client = None
            self.redis_enabled = False
        
        # Buffer for batch processing
        self.data_buffer = []
        self.buffer_size = 10
        self.last_flush_time = datetime.utcnow()
        self.flush_interval = 1  # seconds
        
        # Indicator calculation tracking
        self.last_indicator_calc = {}
        self.indicator_calc_interval = 60  # seconds
        
    def process_price_data(self, data: dict):
        """Process price data and store to database
        
        Args:
            data: Price data dictionary with symbol, bid, ask, timestamp
        """
        symbol = data.get("symbol")
        bid = data.get("bid")
        ask = data.get("ask")
        timestamp = data.get("timestamp")
        
        # Validate data
        if not all([symbol, bid is not None, ask is not None, timestamp]):
            self.logger.warning("Incomplete price data received")
            return
            
        try:
            # Ensure bid and ask are floats
            bid = float(bid)
            ask = float(ask)
            
            # Calculate mid price
            mid_price = (bid + ask) / 2
            
            # Convert timestamp to datetime if it's a Unix timestamp
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.utcfromtimestamp(timestamp)
            elif not isinstance(timestamp, datetime):
                # If it's a string, try to parse it
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    self.logger.warning(f"Could not parse timestamp: {timestamp}")
                    timestamp = datetime.utcnow()
            
            # Prepare data for storage
            price_data = {
                "currency_pair": symbol,
                "bid": bid,
                "ask": ask,
                "rate": mid_price,
                "timestamp": timestamp,
                "created_at": datetime.utcnow()
            }
            
            # Add to buffer
            self.data_buffer.append(price_data)
            
            # Update Redis cache (latest tick)
            if self.redis_enabled:
                self._update_redis_cache(price_data)
            
            # Check if we should flush
            if self._should_flush():
                self._flush_to_database()
                
            # Process candlestick and indicators in background
            # Use asyncio.create_task if we're in an async context
            # Otherwise, schedule it to run later
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, create a task
                asyncio.create_task(self._process_candlestick_async(price_data.copy()))
            except RuntimeError:
                # No running loop, we're in a sync context
                # Use asyncio.run in a thread with proper isolation
                import threading
                threading.Thread(
                    target=self._run_async_process_candlestick,
                    args=(price_data.copy(),),
                    daemon=True
                ).start()
                
        except Exception as e:
            self.logger.error(f"Error processing price data: {e}")
            
    def _update_redis_cache(self, price_data: dict):
        """Update Redis cache with latest tick data"""
        try:
            symbol = price_data["currency_pair"]
            
            # Store latest tick as hash
            key = f"tick:{symbol}:latest"
            self.redis_client.hset(key, mapping={
                "bid": price_data["bid"],
                "ask": price_data["ask"],
                "rate": price_data["rate"],
                "timestamp": price_data["timestamp"].isoformat() if isinstance(price_data["timestamp"], datetime) else str(price_data["timestamp"]),
                "updated_at": datetime.utcnow().isoformat()
            })
            
            # Set TTL of 24 hours
            self.redis_client.expire(key, 86400)
            
            # Store in history list (keep last 100 ticks)
            history_key = f"tick:{symbol}:history"
            tick_json = json.dumps({
                "bid": price_data["bid"],
                "ask": price_data["ask"],
                "rate": price_data["rate"],
                "timestamp": price_data["timestamp"].isoformat() if isinstance(price_data["timestamp"], datetime) else str(price_data["timestamp"])
            })
            
            self.redis_client.lpush(history_key, tick_json)
            self.redis_client.ltrim(history_key, 0, 99)  # Keep only last 100
            self.redis_client.expire(history_key, 86400)
            
        except Exception as e:
            self.logger.error(f"Error updating Redis cache: {e}")
            
    def _should_flush(self) -> bool:
        """Check if buffer should be flushed"""
        # Flush if buffer is full
        if len(self.data_buffer) >= self.buffer_size:
            return True
            
        # Flush if time interval has passed
        if (datetime.utcnow() - self.last_flush_time).total_seconds() >= self.flush_interval:
            return True
            
        return False
        
    def _flush_to_database(self):
        """Flush buffer to database"""
        if not self.data_buffer:
            return
            
        db: Session = self.SessionLocal()
        try:
            for data in self.data_buffer:
                # Create ForexRate object
                forex_rate = ForexRate(
                    currency_pair=data["currency_pair"],
                    bid=data["bid"],
                    ask=data["ask"],
                    rate=data["rate"],
                    timestamp=data["timestamp"],
                    created_at=data["created_at"]
                )
                
                # Use merge for upsert behavior
                db.merge(forex_rate)
            
            # Commit all changes
            db.commit()
            
            self.logger.debug(f"Flushed {len(self.data_buffer)} records to database")
            
            # Clear buffer
            self.data_buffer.clear()
            self.last_flush_time = datetime.utcnow()
            
        except SQLAlchemyError as e:
            self.logger.error(f"Database error: {e}")
            db.rollback()
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            db.rollback()
        finally:
            db.close()
            
    def _run_async_process_candlestick(self, price_data: dict):
        """Run async candlestick processing in a new event loop"""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._process_candlestick_async(price_data))
            finally:
                loop.close()
        except Exception as e:
            self.logger.error(f"Error in candlestick processing thread: {e}")
            
    async def _init_processors(self):
        """Initialize async processors"""
        if not self.candlestick_generator:
            async with self.AsyncSessionLocal() as session:
                self.candlestick_generator = CandlestickGenerator(session)
                self.indicator_calculator = IndicatorCalculator(session)
                self.logger.info("Initialized candlestick and indicator processors")
                
    async def _process_candlestick_async(self, data: dict):
        """Process candlestick data asynchronously"""
        # Create a new lock for each event loop to avoid cross-loop issues
        lock = asyncio.Lock()
            
        async with lock:
            try:
                # Initialize processors if not done
                if not self.candlestick_generator:
                    await self._init_processors()
                    
                async with self.AsyncSessionLocal() as session:
                    # Create new instances with the session
                    candlestick_gen = CandlestickGenerator(session)
                    indicator_calc = IndicatorCalculator(session)
                    
                    # Process tick for candlestick
                    tick_data = {
                        'symbol': data.get('currency_pair'),  # Fix: use currency_pair instead of symbol
                        'timestamp': data.get('timestamp', datetime.utcnow()).timestamp() * 1000 if isinstance(data.get('timestamp'), datetime) else data.get('timestamp', datetime.utcnow().timestamp()) * 1000,
                        'mid': (data.get('bid', 0) + data.get('ask', 0)) / 2
                    }
                    
                    await candlestick_gen.process_tick(tick_data)
                    
                    # Check if we should calculate indicators
                    symbol = data.get('currency_pair')  # Fix: use currency_pair
                    now = datetime.utcnow()
                    last_calc = self.last_indicator_calc.get(symbol)
                    
                    if not last_calc or (now - last_calc).total_seconds() >= self.indicator_calc_interval:
                        # Calculate indicators for 1m timeframe
                        await indicator_calc.calculate_indicators(symbol, '1m')
                        self.last_indicator_calc[symbol] = now
                        self.logger.debug(f"Calculated indicators for {symbol}")
                        
            except Exception as e:
                self.logger.error(f"Error in async processing: {e}")
            
    async def generate_historical_candlesticks(self, symbol: str, start_date: datetime, end_date: datetime):
        """Generate candlesticks from historical forex_rates data"""
        async with self.AsyncSessionLocal() as session:
            candlestick_gen = CandlestickGenerator(session)
            await candlestick_gen.generate_from_historical_data(symbol, start_date, end_date)
            
    async def calculate_historical_indicators(self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime):
        """Calculate indicators for historical candlestick data"""
        async with self.AsyncSessionLocal() as session:
            indicator_calc = IndicatorCalculator(session)
            await indicator_calc.batch_calculate_historical(symbol, timeframe, start_date, end_date)

    def close(self):
        """Clean up resources"""
        # Flush any remaining data
        if self.data_buffer:
            self._flush_to_database()
            
        # Close connections
        if self.redis_client:
            self.redis_client.close()
            
        # Close async engine
        if hasattr(self, 'async_engine'):
            asyncio.create_task(self.async_engine.dispose())